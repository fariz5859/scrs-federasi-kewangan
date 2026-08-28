"""API routes — AJAX endpoints for AI processing, status checks, and document downloads."""
from flask import Blueprint, jsonify, request, send_file, abort
from flask_login import login_required, current_user
from models import db, Case, Finding, Document, AuditLog
from datetime import datetime, timezone
import os
import io
import zipfile

api_bp = Blueprint('api', __name__)


@api_bp.route('/case/<int:cid>/status')
def case_status(cid):
    case = Case.query.get_or_404(cid)
    return jsonify({
        'id': case.id,
        'member_name': case.member_name,
        'ai_processed': case.ai_processed,
        'l1_verdict': case.l1_verdict,
        'compliance_score': case.compliance_score,
        'severity_counts': case.severity_counts,
        'doc_count': case.documents.count()
    })


@api_bp.route('/case/<int:cid>/findings')
@login_required
def case_findings(cid):
    case = Case.query.get_or_404(cid)
    findings = []
    for f in case.findings:
        findings.append({
            'id': f.id, 'severity': f.severity, 'category': f.category,
            'description_bm': f.description_bm, 'description_en': f.description_en,
            'evidence': f.evidence, 'rule_reference': f.rule_reference,
            'source': f.source, 'ai_confidence': f.ai_confidence
        })
    return jsonify({'findings': findings, 'score': case.compliance_score})


@api_bp.route('/finding/<int:fid>/delete', methods=['POST'])
@login_required
def delete_finding(fid):
    f = Finding.query.get_or_404(fid)
    db.session.add(AuditLog(
        user_id=current_user.id, user_role=current_user.role,
        action='delete_finding', target=f'Finding {fid}',
        details=f'Deleted: {f.description_bm[:100]}',
        ip_address=request.remote_addr
    ))
    db.session.delete(f)
    db.session.commit()
    return jsonify({'ok': True})


# ═══════════════════ DOCUMENT DOWNLOAD ROUTES ═══════════════════

@api_bp.route('/doc/<int:did>/download')
def download_document(did):
    """Download a single document by ID."""
    doc = Document.query.get_or_404(did)
    if not os.path.exists(doc.file_path):
        abort(404, description='Fail tidak ditemui di server.')
    return send_file(
        doc.file_path,
        as_attachment=True,
        download_name=doc.original_filename
    )


@api_bp.route('/doc/<int:did>/view')
def view_document(did):
    """View/preview a document inline (PDF, images)."""
    doc = Document.query.get_or_404(did)
    if not os.path.exists(doc.file_path):
        abort(404, description='Fail tidak ditemui di server.')
    return send_file(doc.file_path, as_attachment=False)


@api_bp.route('/case/<int:cid>/documents')
def list_documents(cid):
    """API: list all documents for a case."""
    case = Case.query.get_or_404(cid)
    docs = []
    for d in case.documents:
        docs.append({
            'id': d.id,
            'filename': d.original_filename,
            'doc_type': d.doc_type,
            'uploaded_at': d.uploaded_at.isoformat() if d.uploaded_at else None,
            'download_url': f'/api/doc/{d.id}/download',
            'view_url': f'/api/doc/{d.id}/view',
            'exists': os.path.exists(d.file_path) if d.file_path else False
        })
    return jsonify({'documents': docs, 'count': len(docs)})


@api_bp.route('/case/<int:cid>/download-all')
def download_all_documents(cid):
    """Download all documents for a case as a ZIP file."""
    case = Case.query.get_or_404(cid)
    documents = case.documents.all()
    if not documents:
        abort(404, description='Tiada dokumen untuk dimuat turun.')

    # Create in-memory ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for doc in documents:
            if doc.file_path and os.path.exists(doc.file_path):
                zf.write(doc.file_path, doc.original_filename)
    zip_buffer.seek(0)

    safe_name = case.member_name.replace(' ', '_') if case.member_name else f'case_{cid}'
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'{safe_name}_dokumen.zip'
    )


@api_bp.route('/case/<int:cid>/download-selected', methods=['POST'])
def download_selected_documents(cid):
    """Download selected documents as ZIP. Body: {"doc_ids": [1,2,3]}"""
    case = Case.query.get_or_404(cid)
    data = request.get_json(silent=True) or {}
    doc_ids = data.get('doc_ids', [])

    if not doc_ids:
        abort(400, description='Tiada dokumen dipilih.')

    documents = Document.query.filter(
        Document.id.in_(doc_ids),
        Document.case_id == cid
    ).all()

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for doc in documents:
            if doc.file_path and os.path.exists(doc.file_path):
                zf.write(doc.file_path, doc.original_filename)
    zip_buffer.seek(0)

    safe_name = case.member_name.replace(' ', '_') if case.member_name else f'case_{cid}'
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'{safe_name}_selected.zip'
    )


# ═══════════════════ AI PROCESSING ROUTES ═══════════════════

@api_bp.route('/case/<int:cid>/ai-process', methods=['POST'])
@login_required
def ai_process_case(cid):
    """On-demand AI processing for a single case. Can be re-run."""
    from flask import current_app
    case = Case.query.get_or_404(cid)

    # Reset AI status to allow re-processing
    case.ai_processed = False
    db.session.commit()

    try:
        from ai_engine import process_case
        result = process_case(case, current_app.config)
        db.session.add(AuditLog(
            user_id=current_user.id, user_role=current_user.role,
            action='ai_process', target=f'Case {cid} - {case.member_name}',
            details=f'AI processed: {result["total_findings"]} findings',
            ip_address=request.remote_addr
        ))
        db.session.commit()
        return jsonify({
            'ok': True,
            'status': result['status'],
            'findings_added': result['total_findings'],
            'steps': result['steps'],
            'gemini_summary': result.get('gemini_summary', ''),
            'errors': result.get('errors', []),
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@api_bp.route('/case/<int:cid>/ai-result')
@login_required
def ai_result(cid):
    """View the AI analysis result JSON for a case."""
    import json
    case = Case.query.get_or_404(cid)
    result_json = {}
    if case.ai_result_json:
        try:
            result_json = json.loads(case.ai_result_json)
        except Exception:
            result_json = {'raw': case.ai_result_json}

    return jsonify({
        'ai_processed': case.ai_processed,
        'ai_processed_at': case.ai_processed_at.isoformat() if case.ai_processed_at else None,
        'result': result_json,
        'compliance_score': case.compliance_score,
        'severity_counts': case.severity_counts,
    })
