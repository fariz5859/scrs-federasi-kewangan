"""FedKew routes — Data entry, review management, report generation."""
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, send_file
from flask_login import login_required, current_user
from models import db, KoperasiReview, Case, AuditLog, User
from datetime import datetime, timezone, date
from werkzeug.utils import secure_filename
from functools import wraps
import json
import os

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

fedkew_bp = Blueprint('fedkew', __name__)


def fedkew_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != 'fedkew':
            flash('Akses ditolak — FedKew sahaja.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


# ── Dashboard ────────────────────────────────────────────────────────────────

@fedkew_bp.route('/dashboard')
@fedkew_required
def dashboard():
    reviews = KoperasiReview.query.order_by(KoperasiReview.review_date.desc()).all()
    stats = {
        'total': len(reviews),
        'draft': sum(1 for r in reviews if r.status == 'draft'),
        'in_progress': sum(1 for r in reviews if r.status in ('submitted','ai_processed','koseri_review','resubmit','koseri_done','fedkew_review')),
        'completed': sum(1 for r in reviews if r.status == 'report_generated'),
    }
    return render_template('fedkew/dashboard.html', reviews=reviews, stats=stats)


# ── New Review ───────────────────────────────────────────────────────────────

@fedkew_bp.route('/review/new')
@fedkew_required
def new_review():
    return render_template('fedkew/new_review.html')


@fedkew_bp.route('/review/create', methods=['POST'])
@fedkew_required
def create_review():
    name = request.form.get('koperasi_name', '').strip()
    no_reg = request.form.get('no_pendaftaran', '').strip()

    if not name or not no_reg:
        flash('Sila isi nama koperasi dan no. pendaftaran.', 'warning')
        return redirect(url_for('fedkew.new_review'))

    review = KoperasiReview(
        koperasi_name=name,
        no_pendaftaran=no_reg,
        created_by=current_user.id,
        status='draft'
    )
    review.generate_reference_no()
    db.session.add(review)
    db.session.commit()

    AuditLog(user_id=current_user.id, action='create_review',
             detail=f'Created review {review.reference_no} for {name}',
             ip_addr=request.remote_addr)
    db.session.add(AuditLog(user_id=current_user.id, action='create_review',
                            detail=f'Review {review.reference_no} for {name}',
                            ip_addr=request.remote_addr))
    db.session.commit()

    flash(f'Semakan {review.reference_no} berjaya dicipta.', 'success')
    return redirect(url_for('fedkew.data_entry', rid=review.id))


# ── Data Entry ───────────────────────────────────────────────────────────────

@fedkew_bp.route('/review/<int:rid>/entry')
@fedkew_required
def data_entry(rid):
    review = KoperasiReview.query.get_or_404(rid)
    readonly = review.status not in ('draft', 'resubmit')
    can_append = review.status in ('draft', 'resubmit', 'submitted', 'ai_processed', 'koseri_review')
    # Group cases by process type
    cases_by_type = {'tawaruk': [], 'opsyen': [], 'early_settlement': []}
    for c in review.cases:
        if c.process_type in cases_by_type:
            cases_by_type[c.process_type].append(c)
    return render_template('fedkew/data_entry.html', review=review,
                           cases_by_type=cases_by_type, readonly=readonly,
                           can_append=can_append)


def _parse_date(val):
    """Parse DD/MM/YYYY or YYYY-MM-DD date string."""
    if not val or not val.strip():
        return None
    val = val.strip()
    for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None


@fedkew_bp.route('/review/<int:rid>/case/add', methods=['POST'])
@fedkew_required
def add_case(rid):
    review = KoperasiReview.query.get_or_404(rid)
    allowed = ('draft', 'resubmit', 'submitted', 'ai_processed', 'koseri_review')
    if review.status not in allowed:
        return jsonify({'error': 'Review is locked'}), 400

    is_append = review.status not in ('draft', 'resubmit')

    data = request.form
    ptype = data.get('process_type', 'tawaruk')

    case = Case(
        review_id=rid,
        process_type=ptype,
        product_type=data.get('product_type', ''),
        account_no=data.get('account_no', ''),
        member_name=data.get('member_name', ''),
        fin_amount=float(data.get('fin_amount', 0) or 0),
        date_appli=_parse_date(data.get('date_appli')),
        tenure_period=int(data.get('tenure_period', 0) or 0),
    )

    # Tawaruk fields
    if ptype == 'tawaruk':
        case.purchase_request_date   = _parse_date(data.get('purchase_request_date'))
        case.murabahah_contract_date = _parse_date(data.get('murabahah_contract_date'))
        case.wakalah_date            = _parse_date(data.get('wakalah_date'))
        case.wakalah_time            = data.get('wakalah_time', '')
        case.disbursement_date       = _parse_date(data.get('disbursement_date'))
        case.disbursement_time       = data.get('disbursement_time', '')
        case.surat_tawaran_date      = _parse_date(data.get('surat_tawaran_date'))
        case.perjanjian_pembiayaan_date = _parse_date(data.get('perjanjian_pembiayaan_date'))

    # Opsyen fields
    elif ptype == 'opsyen':
        case.surat_opsyen_date         = _parse_date(data.get('surat_opsyen_date'))
        case.perjanjian_pembelian_date = _parse_date(data.get('perjanjian_pembelian_date'))
        case.wakil_pembelian_date      = _parse_date(data.get('wakil_pembelian_date'))
        case.perjanjian_jualan_date    = _parse_date(data.get('perjanjian_jualan_date'))
        case.wakil_penjualan_date      = _parse_date(data.get('wakil_penjualan_date'))
        case.disbursement_date         = _parse_date(data.get('disbursement_date'))
        case.disbursement_time         = data.get('disbursement_time', '')
        case.surat_tawaran_date        = _parse_date(data.get('surat_tawaran_date'))
        case.perjanjian_pembiayaan_date = _parse_date(data.get('perjanjian_pembiayaan_date'))

    # Early Settlement fields
    elif ptype == 'early_settlement':
        klausa = data.get('klausa_early_settlement', '')
        case.klausa_early_settlement = True if klausa.lower() in ('yes','ya','true','1') else False
        case.amount_rebate  = float(data.get('amount_rebate', 0) or 0)
        case.fee_rebate     = float(data.get('fee_rebate', 0) or 0)
        case.settlement_date = _parse_date(data.get('settlement_date'))

    db.session.add(case)
    db.session.commit()

    # ── Handle document upload ──
    _save_case_doc(case, ptype, request.files)

    # If appending to an already-submitted review, run AI on the new case immediately
    if is_append:
        from ai_engine import process_case
        process_case(case)
        db.session.commit()
        db.session.add(AuditLog(user_id=current_user.id, action='append_case',
                                detail=f'{review.reference_no}: Added case {case.account_no} '
                                       f'({ptype}) — AI: {case.ai_conclusion}',
                                ip_addr=request.remote_addr))
        db.session.commit()
        flash(f'Kes {case.account_no} ditambah dan diproses AI — {case.ai_conclusion}.', 'success')
    else:
        flash(f'Kes {case.account_no} berjaya ditambah.', 'success')

    return redirect(url_for('fedkew.data_entry', rid=rid))


def _save_case_doc(case, ptype, files):
    """Save uploaded document for a case if present."""
    field_map = {'tawaruk': 'doc_msc', 'opsyen': 'doc_perjanjian_pembelian'}
    if ptype not in field_map:
        return
    f = files.get('case_document')
    if not f or f.filename == '':
        return
    ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        return
    safe_name = secure_filename(f.filename)
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                              'uploads', 'cases', str(case.id))
    os.makedirs(upload_dir, exist_ok=True)
    f.save(os.path.join(upload_dir, safe_name))
    setattr(case, field_map[ptype], safe_name)
    db.session.commit()


@fedkew_bp.route('/case/<int:cid>/document/<field>')
@login_required
def serve_case_doc(cid, field):
    """Serve a case document for preview/download. FedKew + KoSERI access."""
    case = Case.query.get_or_404(cid)
    allowed_fields = {'doc_msc', 'doc_perjanjian_pembelian'}
    if field not in allowed_fields:
        return 'Not found', 404
    filename = getattr(case, field, None)
    if not filename:
        return 'No document', 404
    file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                             'uploads', 'cases', str(case.id), filename)
    if not os.path.exists(file_path):
        return 'File missing', 404
    return send_file(file_path)


@fedkew_bp.route('/review/<int:rid>/case/<int:cid>/delete', methods=['POST'])
@fedkew_required
def delete_case(rid, cid):
    case = Case.query.get_or_404(cid)
    review = KoperasiReview.query.get_or_404(rid)
    if review.status not in ('draft', 'resubmit'):
        flash('Tidak boleh padam — semakan telah dihantar.', 'warning')
        return redirect(url_for('fedkew.data_entry', rid=rid))
    db.session.delete(case)
    db.session.commit()
    flash(f'Kes {case.account_no} dipadam.', 'success')
    return redirect(url_for('fedkew.data_entry', rid=rid))


# ── Submit Review → Triggers AI ──────────────────────────────────────────────

@fedkew_bp.route('/review/<int:rid>/submit', methods=['POST'])
@fedkew_required
def submit_review(rid):
    review = KoperasiReview.query.get_or_404(rid)
    if review.status not in ('draft', 'resubmit'):
        flash('Semakan tidak dalam status yang betul.', 'warning')
        return redirect(url_for('fedkew.dashboard'))
    if len(review.cases) == 0:
        flash('Tiada kes — sila tambah sekurang-kurangnya satu kes.', 'warning')
        return redirect(url_for('fedkew.data_entry', rid=rid))

    review.status = 'submitted'
    review.submitted_at = datetime.now(timezone.utc)
    db.session.commit()

    # Run AI engine
    from ai_engine import process_review
    summary = process_review(review)

    # Move to koseri_review
    review.status = 'koseri_review'
    db.session.commit()

    db.session.add(AuditLog(user_id=current_user.id, action='submit_review',
                            detail=f'{review.reference_no}: {summary["total_cases"]} cases, '
                                   f'{summary["non_compliant"]} non-compliant',
                            ip_addr=request.remote_addr))
    db.session.commit()

    flash(f'Semakan dihantar — AI memproses {summary["total_cases"]} kes. '
          f'{summary["non_compliant"]} tidak patuh, {summary["compliant"]} patuh.', 'success')
    return redirect(url_for('fedkew.dashboard'))


# ── Resubmit corrected data ─────────────────────────────────────────────────

@fedkew_bp.route('/review/<int:rid>/case/<int:cid>/fix', methods=['POST'])
@fedkew_required
def fix_flagged_case(rid, cid):
    """FedKew updates a flagged case with missing data."""
    review = KoperasiReview.query.get_or_404(rid)
    case = Case.query.get_or_404(cid)

    if review.status != 'resubmit' or case.review_id != rid:
        flash('Tindakan tidak sah.', 'danger')
        return redirect(url_for('fedkew.data_entry', rid=rid))

    if case.koseri_flag != 'flagged':
        flash('Kes ini tidak ditandakan untuk pembetulan.', 'warning')
        return redirect(url_for('fedkew.data_entry', rid=rid))

    # Update fields from form — only process fields that were submitted
    ptype = case.process_type
    updated_fields = []

    # Date fields
    date_fields = {
        'tawaruk': ['purchase_request_date', 'murabahah_contract_date', 'wakalah_date',
                     'disbursement_date', 'surat_tawaran_date', 'perjanjian_pembiayaan_date'],
        'opsyen': ['surat_opsyen_date', 'perjanjian_pembelian_date', 'wakil_pembelian_date',
                   'perjanjian_jualan_date', 'wakil_penjualan_date',
                   'disbursement_date', 'surat_tawaran_date', 'perjanjian_pembiayaan_date'],
    }
    for field_name in date_fields.get(ptype, []):
        val = request.form.get(field_name, '').strip()
        if val:
            parsed = _parse_date(val)
            if parsed:
                setattr(case, field_name, parsed)
                updated_fields.append(field_name)

    # Time fields
    for field_name in ['wakalah_time', 'disbursement_time']:
        val = request.form.get(field_name, '').strip()
        if val:
            setattr(case, field_name, val)
            updated_fields.append(field_name)

    # Document upload
    _save_case_doc(case, ptype, request.files)
    if ptype == 'tawaruk' and case.doc_msc:
        updated_fields.append('doc_msc')
    elif ptype == 'opsyen' and case.doc_perjanjian_pembelian:
        updated_fields.append('doc_perjanjian_pembelian')

    # Mark as fixed
    case.fedkew_response = 'fixed'
    case.fedkew_response_note = f'Dikemaskini: {", ".join(updated_fields)}'
    db.session.commit()

    db.session.add(AuditLog(
        user_id=current_user.id, action='fix_flagged_case',
        detail=f'{review.reference_no} Case {case.account_no}: Fixed — {", ".join(updated_fields)}',
        ip_addr=request.remote_addr
    ))
    db.session.commit()

    flash(f'✅ {case.account_no} dikemaskini. {len(updated_fields)} medan diperbaharui.', 'success')
    return redirect(url_for('fedkew.data_entry', rid=rid))


@fedkew_bp.route('/review/<int:rid>/case/<int:cid>/cannot-fix', methods=['POST'])
@fedkew_required
def cannot_fix_case(rid, cid):
    """FedKew marks a flagged case as unfixable."""
    review = KoperasiReview.query.get_or_404(rid)
    case = Case.query.get_or_404(cid)

    if review.status != 'resubmit' or case.review_id != rid:
        flash('Tindakan tidak sah.', 'danger')
        return redirect(url_for('fedkew.data_entry', rid=rid))

    reason = request.form.get('reason', '').strip()
    if not reason:
        flash('Sila nyatakan sebab data tidak dapat dilengkapkan.', 'warning')
        return redirect(url_for('fedkew.data_entry', rid=rid))

    case.fedkew_response = 'cannot_fix'
    case.fedkew_response_note = reason
    db.session.commit()

    db.session.add(AuditLog(
        user_id=current_user.id, action='cannot_fix_case',
        detail=f'{review.reference_no} Case {case.account_no}: Cannot fix — {reason}',
        ip_addr=request.remote_addr
    ))
    db.session.commit()

    flash(f'🏳️ {case.account_no} ditandakan sebagai tidak dapat dilengkapkan.', 'info')
    return redirect(url_for('fedkew.data_entry', rid=rid))


@fedkew_bp.route('/review/<int:rid>/resubmit', methods=['POST'])
@fedkew_required
def resubmit_review(rid):
    """FedKew resubmits the review after addressing flagged cases."""
    review = KoperasiReview.query.get_or_404(rid)
    if review.status != 'resubmit':
        flash('Semakan tidak dalam status penghantaran semula.', 'warning')
        return redirect(url_for('fedkew.dashboard'))

    # Check all flagged cases have been responded to
    unresolved = [c for c in review.cases
                  if c.koseri_flag == 'flagged' and c.fedkew_response is None]
    if unresolved:
        flash(f'{len(unresolved)} kes belum ditindaklanjuti. Sila selesaikan semua kes yang ditandakan.', 'warning')
        return redirect(url_for('fedkew.data_entry', rid=rid))

    # Re-run AI only on fixed cases
    from ai_engine import process_case
    fixed_count = 0
    for case in review.cases:
        if case.fedkew_response == 'fixed':
            case.koseri_flag = None
            case.koseri_flag_reason = None
            case.fedkew_response = None
            case.fedkew_response_note = None
            process_case(case)
            fixed_count += 1
        elif case.fedkew_response == 'cannot_fix':
            # Keep flag info — KoSERI will see FedKew's response
            pass

    review.status = 'koseri_review'
    review.resubmitted_at = datetime.now(timezone.utc)
    db.session.commit()

    db.session.add(AuditLog(
        user_id=current_user.id, action='resubmit_review',
        detail=f'{review.reference_no}: Resubmitted — {fixed_count} cases fixed',
        ip_addr=request.remote_addr
    ))
    db.session.commit()

    flash(f'{review.reference_no} dihantar semula ke KoSERI. {fixed_count} kes diperbaharui.', 'success')
    return redirect(url_for('fedkew.dashboard'))


# ── Report Preview + Summary ────────────────────────────────────────────────

@fedkew_bp.route('/review/<int:rid>/report')
@fedkew_required
def report_preview(rid):
    review = KoperasiReview.query.get_or_404(rid)
    if review.status not in ('fedkew_review', 'report_generated'):
        flash('Laporan belum sedia.', 'warning')
        return redirect(url_for('fedkew.dashboard'))

    # Build analytics from stored AI results
    analytics = _build_analytics(review)
    return render_template('fedkew/report_preview_new.html', review=review,
                           analytics=analytics)


@fedkew_bp.route('/review/<int:rid>/summary', methods=['POST'])
@fedkew_required
def save_summary(rid):
    review = KoperasiReview.query.get_or_404(rid)
    review.fedkew_summary = request.form.get('fedkew_summary', '').strip()
    db.session.commit()
    flash('Ulasan disimpan.', 'success')
    return redirect(url_for('fedkew.report_preview', rid=rid))


# ── Generate PDF ─────────────────────────────────────────────────────────────

@fedkew_bp.route('/review/<int:rid>/generate-report', methods=['POST'])
@fedkew_required
def generate_report(rid):
    review = KoperasiReview.query.get_or_404(rid)
    if review.status not in ('fedkew_review', 'report_generated'):
        flash('Laporan tidak boleh dijana pada status ini.', 'warning')
        return redirect(url_for('fedkew.dashboard'))

    from services.report_generator import generate_report_pdf
    filepath = generate_report_pdf(review)
    review.status = 'report_generated'
    review.report_generated_at = datetime.now(timezone.utc)
    db.session.commit()

    db.session.add(AuditLog(user_id=current_user.id, action='generate_report',
                            detail=f'{review.reference_no}: Report generated',
                            ip_addr=request.remote_addr))
    db.session.commit()

    return send_file(filepath, as_attachment=True,
                     download_name=f'{review.reference_no}_Laporan.pdf')


# ── Audit Log ────────────────────────────────────────────────────────────────

@fedkew_bp.route('/audit-log')
@fedkew_required
def audit_log():
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(200).all()
    return render_template('fedkew/audit_log.html', logs=logs)


# ── Helper: Build Analytics from stored results ─────────────────────────────

def _build_analytics(review):
    """Build compliance scoring overlay from existing AI results. No new logic."""
    all_findings = []
    for c in review.cases:
        for f in c.findings:
            f['_product_type'] = c.product_type or 'N/A'
            f['_account_no'] = c.account_no
            all_findings.append(f)

    by_severity = {}
    for f in all_findings:
        sev = f.get('severity', 'UNKNOWN')
        by_severity[sev] = by_severity.get(sev, 0) + 1

    by_rule = {}
    for f in all_findings:
        rid = f.get('rule_id', 'UNKNOWN')
        if rid not in by_rule:
            by_rule[rid] = {'name': f.get('rule_name', ''), 'count': 0}
        by_rule[rid]['count'] += 1

    by_product = {}
    for c in review.cases:
        pt = c.product_type or 'N/A'
        if pt not in by_product:
            by_product[pt] = {'total': 0, 'compliant': 0, 'non_compliant': 0, 'needs_review': 0, 'findings': 0}
        by_product[pt]['total'] += 1
        if c.koseri_decision == 'compliant' or (not c.koseri_decision and c.ai_conclusion == 'SHARIAH_COMPLIANT'):
            by_product[pt]['compliant'] += 1
        elif c.koseri_decision == 'non_compliant' or (not c.koseri_decision and c.ai_conclusion == 'NON_SHARIAH_COMPLIANT'):
            by_product[pt]['non_compliant'] += 1
        else:
            by_product[pt]['needs_review'] += 1
        by_product[pt]['findings'] += c.total_findings

    total = review.case_count
    affected = sum(1 for c in review.cases if c.total_findings > 0)

    return {
        'total_findings': len(all_findings),
        'by_severity': by_severity,
        'by_rule': by_rule,
        'by_product': by_product,
        'cases_affected': affected,
        'cases_affected_pct': round(affected / total * 100, 1) if total else 0,
        'repeat_violations': {rid: d for rid, d in by_rule.items() if d['count'] > 1},
    }
