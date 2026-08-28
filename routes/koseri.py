"""KoSERI routes — Shadow mode reviewer workbench."""
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from models import db, KoperasiReview, Case, AuditLog
from datetime import datetime, timezone
from functools import wraps

koseri_bp = Blueprint('koseri', __name__)


def koseri_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role not in ('koseri', 'admin'):
            flash('Akses ditolak — KoSERI sahaja.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


# ── Dashboard ────────────────────────────────────────────────────────────────

@koseri_bp.route('/dashboard')
@koseri_required
def dashboard():
    # Reviews awaiting KoSERI review
    pending = KoperasiReview.query.filter(
        KoperasiReview.status.in_(['koseri_review', 'ai_processed'])
    ).order_by(KoperasiReview.submitted_at.desc()).all()

    completed = KoperasiReview.query.filter(
        KoperasiReview.status.in_(['koseri_done', 'fedkew_review', 'report_generated'])
    ).order_by(KoperasiReview.koseri_done_at.desc()).limit(20).all()

    stats = {
        'pending': len(pending),
        'completed': len(completed),
        'total_cases_pending': sum(r.case_count for r in pending),
    }
    return render_template('koseri/dashboard.html', pending=pending,
                           completed=completed, stats=stats)


# ── Workbench ────────────────────────────────────────────────────────────────

@koseri_bp.route('/review/<int:rid>')
@koseri_required
def workbench(rid):
    review = KoperasiReview.query.get_or_404(rid)

    # Active review = editable, completed = read-only
    active_statuses = ('koseri_review', 'ai_processed')
    completed_statuses = ('koseri_done', 'fedkew_review', 'report_generated')
    readonly = review.status in completed_statuses

    if review.status not in active_statuses and not readonly:
        flash('Semakan ini bukan dalam status untuk disemak.', 'warning')
        return redirect(url_for('koseri.dashboard'))

    # Mark reviewer (shadow — never in reports)
    if not readonly and not review.reviewed_by:
        review.reviewed_by = current_user.id
        db.session.commit()

    # Analytics from stored AI results
    total = review.case_count
    decided = sum(1 for c in review.cases if c.koseri_decision is not None)
    undecided = total - decided
    flagged = sum(1 for c in review.cases if c.koseri_flag == 'flagged')
    all_findings = []
    for c in review.cases:
        all_findings.extend(c.findings)

    analytics = {
        'total': total,
        'decided': decided,
        'undecided': undecided,
        'flagged': flagged,
        'total_findings': len(all_findings),
        'high_count': sum(1 for f in all_findings if f.get('severity') == 'HIGH'),
        'medium_count': sum(1 for f in all_findings if f.get('severity') == 'MEDIUM'),
    }

    return render_template('koseri/workbench_new.html', review=review,
                           analytics=analytics, readonly=readonly)


# ── Per-Case Decision ────────────────────────────────────────────────────────

@koseri_bp.route('/review/<int:rid>/case/<int:cid>/decide', methods=['POST'])
@koseri_required
def decide_case(rid, cid):
    review = KoperasiReview.query.get_or_404(rid)
    case = Case.query.get_or_404(cid)

    if case.review_id != rid:
        flash('Kes tidak sah.', 'danger')
        return redirect(url_for('koseri.workbench', rid=rid))

    # Block decision on actively flagged cases (must override or wait for FedKew)
    if case.koseri_flag == 'flagged' and case.fedkew_response is None:
        flash('Kes ini ditandakan untuk pembetulan. Sila tunggu respons FedKew atau gunakan Override.', 'warning')
        return redirect(url_for('koseri.workbench', rid=rid))

    decision = request.form.get('decision', '')
    notes = request.form.get('notes', '').strip()

    if decision not in ('compliant', 'non_compliant'):
        flash('Keputusan tidak sah.', 'danger')
        return redirect(url_for('koseri.workbench', rid=rid))

    case.koseri_decision = decision
    case.koseri_notes = notes
    case.koseri_decided_at = datetime.now(timezone.utc)

    # Clear flag lifecycle — decision resolves the flag
    if case.koseri_flag:
        case.koseri_flag = None
        case.koseri_flag_reason = None
        case.fedkew_response = None
        case.fedkew_response_note = None

    db.session.commit()

    db.session.add(AuditLog(
        user_id=current_user.id,
        action='koseri_decision',
        detail=f'{review.reference_no} Case {case.account_no}: {decision}',
        ip_addr=request.remote_addr
    ))
    db.session.commit()

    flash(f'Keputusan untuk {case.account_no}: {decision.replace("_", " ").title()}', 'success')
    return redirect(url_for('koseri.workbench', rid=rid))


# ── Flag Case for Resubmission ──────────────────────────────────────────────

@koseri_bp.route('/review/<int:rid>/case/<int:cid>/flag', methods=['POST'])
@koseri_required
def flag_case(rid, cid):
    review = KoperasiReview.query.get_or_404(rid)
    case = Case.query.get_or_404(cid)

    if case.review_id != rid:
        flash('Kes tidak sah.', 'danger')
        return redirect(url_for('koseri.workbench', rid=rid))

    reason = request.form.get('flag_reason', '').strip()
    if not reason:
        flash('Sila nyatakan sebab penandaan.', 'warning')
        return redirect(url_for('koseri.workbench', rid=rid))

    case.koseri_flag = 'flagged'
    case.koseri_flag_reason = reason
    # Clear any existing decision — case needs fixing first
    case.koseri_decision = None
    case.koseri_notes = None
    case.koseri_decided_at = None
    db.session.commit()

    db.session.add(AuditLog(
        user_id=current_user.id,
        action='flag_case',
        detail=f'{review.reference_no} Case {case.account_no}: Flagged — {reason}',
        ip_addr=request.remote_addr
    ))
    db.session.commit()

    flash(f'🚩 {case.account_no} ditandakan untuk pembetulan.', 'warning')
    return redirect(url_for('koseri.workbench', rid=rid))


# ── Override — Decide Despite Incomplete Data ────────────────────────────────

@koseri_bp.route('/review/<int:rid>/case/<int:cid>/override', methods=['POST'])
@koseri_required
def override_case(rid, cid):
    review = KoperasiReview.query.get_or_404(rid)
    case = Case.query.get_or_404(cid)

    if case.review_id != rid:
        flash('Kes tidak sah.', 'danger')
        return redirect(url_for('koseri.workbench', rid=rid))

    decision = request.form.get('decision', '')
    notes = request.form.get('notes', '').strip()

    if decision not in ('compliant', 'non_compliant'):
        flash('Keputusan tidak sah.', 'danger')
        return redirect(url_for('koseri.workbench', rid=rid))

    if not notes:
        flash('Catatan wajib untuk override. Sila nyatakan justifikasi.', 'warning')
        return redirect(url_for('koseri.workbench', rid=rid))

    case.koseri_flag = 'override'
    case.koseri_flag_reason = case.koseri_flag_reason or ''
    case.koseri_decision = decision
    case.koseri_notes = f'[OVERRIDE] {notes}'
    case.koseri_decided_at = datetime.now(timezone.utc)
    db.session.commit()

    db.session.add(AuditLog(
        user_id=current_user.id,
        action='override_case',
        detail=f'{review.reference_no} Case {case.account_no}: Override → {decision} — {notes}',
        ip_addr=request.remote_addr
    ))
    db.session.commit()

    flash(f'🔓 {case.account_no}: Override — {decision.replace("_", " ").title()}', 'info')
    return redirect(url_for('koseri.workbench', rid=rid))


# ── Return to FedKew (Resubmission) ─────────────────────────────────────────

@koseri_bp.route('/review/<int:rid>/return', methods=['POST'])
@koseri_required
def return_review(rid):
    review = KoperasiReview.query.get_or_404(rid)

    # Auto-build reason from flagged cases
    flagged_cases = [c for c in review.cases if c.koseri_flag == 'flagged']
    if not flagged_cases:
        reason = request.form.get('reason', '').strip()
        if not reason:
            flash('Tiada kes ditandakan untuk pembetulan. Sila tandakan kes terlebih dahulu.', 'warning')
            return redirect(url_for('koseri.workbench', rid=rid))
    else:
        # Auto-generate reason from flagged cases
        lines = [f'{c.account_no}: {c.koseri_flag_reason}' for c in flagged_cases]
        reason = request.form.get('reason', '').strip()
        if reason:
            lines.insert(0, reason)
        reason = '\n'.join(lines)

    review.status = 'resubmit'
    review.resubmission_reason = reason
    review.resubmission_count += 1
    review.resubmitted_at = None  # Will be set when FedKew resubmits

    # ONLY reset AI on flagged cases — preserve decided cases
    for case in review.cases:
        if case.koseri_flag == 'flagged':
            case.ai_processed = False
            case.ai_result_json = None
            case.ai_conclusion = None
            # Keep flag and reason — FedKew needs to see them

    db.session.commit()

    db.session.add(AuditLog(
        user_id=current_user.id,
        action='return_review',
        detail=f'{review.reference_no}: Returned — {len(flagged_cases)} cases flagged',
        ip_addr=request.remote_addr
    ))
    db.session.commit()

    flash(f'{review.reference_no} dikembalikan kepada FedKew ({len(flagged_cases)} kes ditandakan).', 'success')
    return redirect(url_for('koseri.dashboard'))


# ── Complete Review (Forward to FedKew) ──────────────────────────────────────

@koseri_bp.route('/review/<int:rid>/complete', methods=['POST'])
@koseri_required
def complete_review(rid):
    review = KoperasiReview.query.get_or_404(rid)

    # Block if any case is flagged without a decision
    flagged_no_decision = [c for c in review.cases
                           if c.koseri_flag == 'flagged' and c.koseri_decision is None]
    if flagged_no_decision:
        flash(f'{len(flagged_no_decision)} kes masih ditandakan tanpa keputusan. '
              f'Sila selesaikan semua kes dahulu.', 'warning')
        return redirect(url_for('koseri.workbench', rid=rid))

    # Ensure all cases have decisions
    undecided = [c for c in review.cases if c.koseri_decision is None]
    if undecided:
        flash(f'{len(undecided)} kes belum diputuskan. Sila putuskan semua kes dahulu.', 'warning')
        return redirect(url_for('koseri.workbench', rid=rid))

    review.status = 'fedkew_review'
    review.koseri_done_at = datetime.now(timezone.utc)
    db.session.commit()

    db.session.add(AuditLog(
        user_id=current_user.id,
        action='complete_review',
        detail=f'{review.reference_no}: Review completed, forwarded to FedKew',
        ip_addr=request.remote_addr
    ))
    db.session.commit()

    flash(f'{review.reference_no} selesai — dihantar kepada FedKew untuk laporan.', 'success')
    return redirect(url_for('koseri.dashboard'))
