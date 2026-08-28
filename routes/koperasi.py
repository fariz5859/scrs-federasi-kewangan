"""Koperasi routes — portal access via link + PIN."""
from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from models import db, KoperasiReview, ReviewSession, Case, Document, AuditLog, ProductVerdict
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
import os

koperasi_bp = Blueprint('koperasi', __name__)

PRODUCT_TYPES = {
    'peralatan_rumah': {'name': 'Pembiayaan Peralatan Rumah', 'icon': '🏠', 'docs': [
        'Borang Permohonan Pembiayaan', 'Terma dan Syarat',
        'Kebenaran Penzahiran Maklumat Peribadi', 'Borang Kebenaran Potongan Gaji',
        'Senarai Semakan Dokumen', 'Sebutharga Peralatan',
        'Penyata Pendapatan', 'Pengesahan Majikan',
        'Penyata KWSP', 'Penyata Bank',
        'Perjanjian Jualan Komoditi Murabahah', 'Sijil Pemilikan Komoditi (Beli)',
        'Sijil Pemilikan Komoditi (Jual)', 'Surat Aku Janji (Wa\'ad)',
        'Resit/Invois Peralatan'
    ]},
    'kenderaan': {'name': 'Pembiayaan Kenderaan', 'icon': '🚗', 'docs': [
        'Borang Permohonan Pembiayaan', 'Perjanjian Jualan Komoditi Murabahah',
        'Sijil Pemilikan Komoditi (Beli)', 'Sijil Pemilikan Komoditi (Jual)',
        'Dokumen Kenderaan', 'Surat Aku Janji (Wa\'ad)', 'Penyata Pendapatan'
    ]},
    'peribadi': {'name': 'Pembiayaan Peribadi', 'icon': '💰', 'docs': [
        'Borang Permohonan Pembiayaan', 'Perjanjian Jualan Komoditi Murabahah',
        'Sijil Pemilikan Komoditi (Beli)', 'Sijil Pemilikan Komoditi (Jual)',
        'Surat Aku Janji (Wa\'ad)', 'Penyata Pendapatan'
    ]},
    'saham': {'name': 'Pembiayaan Saham', 'icon': '📈', 'docs': [
        'Borang Permohonan', 'Perjanjian Jualan Komoditi Murabahah',
        'Sijil Pemilikan Komoditi (Beli)', 'Sijil Pemilikan Komoditi (Jual)'
    ]},
    'bertindih': {'name': 'Pembiayaan Bertindih (Overlap)', 'icon': '🔄', 'docs': [
        'Borang Permohonan Pembiayaan Baru', 'Perjanjian Lama',
        'Perjanjian Jualan Komoditi Murabahah Baru',
        'Sijil Pemilikan Komoditi (Beli)', 'Sijil Pemilikan Komoditi (Jual)',
        'Pengiraan Baki Prinsipal', 'Pengesahan Pegawai Syariah'
    ]},
    'pendidikan': {'name': 'Pembiayaan Pendidikan', 'icon': '📚', 'docs': [
        'Borang Permohonan', 'Perjanjian Jualan Komoditi Murabahah',
        'Sijil Pemilikan Komoditi (Beli)', 'Sijil Pemilikan Komoditi (Jual)',
        'Surat Tawaran Pengajian', 'Penyata Pendapatan'
    ]},
    'kecemasan': {'name': 'Pembiayaan Kecemasan', 'icon': '🆘', 'docs': [
        'Borang Permohonan', 'Perjanjian Jualan Komoditi Murabahah',
        'Sijil Pemilikan Komoditi (Beli)', 'Sijil Pemilikan Komoditi (Jual)',
        'Dokumen Sokongan Kecemasan'
    ]},
}


def get_koperasi_review(token):
    """Validate token and session status."""
    kr = KoperasiReview.query.filter_by(link_token=token).first()
    if not kr:
        return None, 'Pautan tidak sah.'
    if kr.session.status == 'closed':
        return None, 'Sesi semakan telah ditutup.'
    return kr, None


@koperasi_bp.route('/<token>', methods=['GET', 'POST'])
def portal(token):
    kr, error = get_koperasi_review(token)
    if error:
        return render_template('koperasi/error.html', message=error), 404

    # Check if already authenticated in session
    if session.get(f'kop_{token}'):
        return redirect(url_for('koperasi.product_select', token=token))

    if request.method == 'POST':
        pin = request.form.get('pin', '')
        if kr.check_pin(pin):
            session[f'kop_{token}'] = True
            db.session.add(AuditLog(
                action='koperasi_login', target=kr.koperasi_name,
                details=f'PIN verified for {kr.koperasi_name}',
                ip_address=request.remote_addr
            ))
            db.session.commit()
            return redirect(url_for('koperasi.product_select', token=token))
        flash('PIN tidak sah. Sila cuba lagi.', 'danger')

    return render_template('koperasi/pin_entry.html', kr=kr, token=token)


@koperasi_bp.route('/<token>/products')
def product_select(token):
    kr, error = get_koperasi_review(token)
    if error:
        return render_template('koperasi/error.html', message=error), 404
    if not session.get(f'kop_{token}'):
        return redirect(url_for('koperasi.portal', token=token))

    existing_cases = kr.cases.all()
    products_with_cases = {}
    for c in existing_cases:
        products_with_cases.setdefault(c.product_type, []).append(c)

    return render_template('koperasi/product_select.html',
                           kr=kr, token=token, product_types=PRODUCT_TYPES,
                           products_with_cases=products_with_cases)


@koperasi_bp.route('/<token>/upload/<product_type>', methods=['GET', 'POST'])
def upload(token, product_type):
    kr, error = get_koperasi_review(token)
    if error:
        return render_template('koperasi/error.html', message=error), 404
    if not session.get(f'kop_{token}'):
        return redirect(url_for('koperasi.portal', token=token))
    if product_type not in PRODUCT_TYPES:
        flash('Jenis produk tidak sah.', 'danger')
        return redirect(url_for('koperasi.product_select', token=token))

    product = PRODUCT_TYPES[product_type]

    if request.method == 'POST':
        member_name = request.form.get('member_name', '').strip()
        member_ic = request.form.get('member_ic', '').strip()
        amount = request.form.get('financing_amount', 0, type=float)

        # Create case
        case = Case(
            review_id=kr.id,
            product_type=product_type,
            member_name=member_name,
            member_ic=member_ic,
            financing_amount=amount
        )
        db.session.add(case)
        db.session.commit()

        # Handle file uploads
        upload_dir = os.path.join(os.path.dirname(__file__), '..', 'uploads', str(case.id))
        os.makedirs(upload_dir, exist_ok=True)

        files = request.files.getlist('documents')
        for f in files:
            if f and f.filename:
                filename = secure_filename(f.filename)
                filepath = os.path.join(upload_dir, filename)
                f.save(filepath)
                doc = Document(
                    case_id=case.id,
                    original_filename=f.filename,
                    file_path=filepath,
                    doc_type='pending_classification'
                )
                db.session.add(doc)

        # Update status
        if kr.status == 'link_sent':
            kr.status = 'docs_uploaded'

        db.session.add(AuditLog(
            action='upload_case', target=kr.koperasi_name,
            details=f'Case: {member_name} | Product: {product_type} | Files: {len(files)}',
            ip_address=request.remote_addr
        ))
        db.session.commit()

        flash(f'Kes {member_name} berjaya dimuat naik ({len(files)} dokumen).', 'success')
        return redirect(url_for('koperasi.product_select', token=token))

    return render_template('koperasi/upload.html',
                           kr=kr, token=token, product=product, product_type=product_type)


@koperasi_bp.route('/<token>/status')
def status(token):
    kr, error = get_koperasi_review(token)
    if error:
        return render_template('koperasi/error.html', message=error), 404
    if not session.get(f'kop_{token}'):
        return redirect(url_for('koperasi.portal', token=token))

    cases = kr.cases.all()
    products = {}
    for c in cases:
        products.setdefault(c.product_type, []).append(c)

    # Product verdicts
    product_verdict_map = {}
    for pt in products:
        pv = ProductVerdict.query.filter_by(review_id=kr.id, product_type=pt).first()
        if pv:
            product_verdict_map[pt] = pv

    # Status timeline
    timeline = [
        ('Pautan Dihantar', kr.status != 'link_sent', True),
        ('Dokumen Dimuat Naik', kr.status not in ['link_sent'], kr.case_count > 0),
        ('Semakan Pegawai Syariah (Layer 1)', kr.status in ['l1_review', 'l1_done', 'l2_review', 'l2_done', 'completed'], kr.status in ['l1_done', 'l2_review', 'l2_done', 'completed']),
        ('Semakan Pegawai Syariah (Layer 2)', kr.status in ['l2_review', 'l2_done', 'completed'], kr.status in ['l2_done', 'completed']),
        ('Keputusan Muktamad', kr.status == 'completed', kr.status == 'completed'),
    ]

    return render_template('koperasi/status.html',
                           kr=kr, token=token, products=products, timeline=timeline,
                           product_types=PRODUCT_TYPES, product_verdicts=product_verdict_map)

