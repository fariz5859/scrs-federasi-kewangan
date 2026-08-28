"""SSPS Models — Shariah Compliance Review System v2.0."""
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timezone

db = SQLAlchemy()


# ── User ─────────────────────────────────────────────────────────────────────
class User(db.Model, UserMixin):
    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role     = db.Column(db.String(20), nullable=False)   # fedkew | koseri | admin
    name     = db.Column(db.String(120), default='')
    active   = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


# ── Koperasi Review (top-level review container) ─────────────────────────────
class KoperasiReview(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # ── Koperasi identity (input by FedKew) ──
    koperasi_name  = db.Column(db.String(200), nullable=False)
    no_pendaftaran = db.Column(db.String(50), nullable=False)

    # ── Review metadata ──
    review_date  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    reference_no = db.Column(db.String(30), unique=True)   # SSPS-2026-0001
    status       = db.Column(db.String(30), default='draft')
    # Status flow:
    #   draft → submitted → ai_processed → koseri_review
    #   → resubmit → submitted  (loop)
    #   → koseri_done → fedkew_review → report_generated

    # ── FedKew (visible in reports) ──
    created_by     = db.Column(db.Integer, db.ForeignKey('user.id'))
    fedkew_summary = db.Column(db.Text, default='')   # Optional feedback before report

    # ── KoSERI (SHADOW — never in reports) ──
    reviewed_by = db.Column(db.Integer, db.ForeignKey('user.id'))

    # ── Timestamps ──
    submitted_at        = db.Column(db.DateTime)
    ai_processed_at     = db.Column(db.DateTime)
    koseri_done_at      = db.Column(db.DateTime)
    report_generated_at = db.Column(db.DateTime)

    # ── Resubmission ──
    resubmission_reason = db.Column(db.Text, default='')
    resubmission_count  = db.Column(db.Integer, default=0)
    resubmitted_at      = db.Column(db.DateTime, nullable=True)

    # ── Relationships ──
    cases   = db.relationship('Case', backref='review', lazy=True,
                              cascade='all, delete-orphan')
    creator = db.relationship('User', foreign_keys=[created_by])

    def generate_reference_no(self):
        """Auto-generate reference: SSPS-YYYY-NNNN."""
        year = datetime.now(timezone.utc).strftime('%Y')
        count = KoperasiReview.query.filter(
            KoperasiReview.reference_no.like(f'SSPS-{year}-%')
        ).count()
        self.reference_no = f'SSPS-{year}-{str(count + 1).zfill(4)}'

    @property
    def case_count(self):
        return len(self.cases)

    @property
    def compliant_count(self):
        return sum(1 for c in self.cases if c.final_decision == 'compliant')

    @property
    def non_compliant_count(self):
        return sum(1 for c in self.cases if c.final_decision == 'non_compliant')

    @property
    def needs_review_count(self):
        return sum(1 for c in self.cases if c.final_decision is None and c.ai_processed)

    @property
    def overall_opinion(self):
        """Three-tier opinion for report."""
        if self.case_count == 0:
            return 'NO_CASES'
        nc = self.non_compliant_count
        pct = (nc / self.case_count) * 100 if self.case_count > 0 else 0
        if nc == 0:
            return 'PATUH_SYARIAH'
        elif pct < 50:
            return 'PATUH_SECARA_AMNYA'
        else:
            return 'TIDAK_PATUH_SYARIAH'


# ── Case (individual financing case within a review) ──────────────────────────
class Case(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('koperasi_review.id'))

    # ── Classification ──
    process_type = db.Column(db.String(20))   # 'tawaruk' | 'opsyen' | 'early_settlement'
    product_type = db.Column(db.String(50))   # 'peribadi' | 'kenderaan' | 'peralatan_rumah'

    # ── Common fields ──
    account_no    = db.Column(db.String(50), nullable=False)
    member_name   = db.Column(db.String(200), default='')
    fin_amount    = db.Column(db.Float)
    date_appli    = db.Column(db.Date)
    tenure_period = db.Column(db.Integer)     # months

    # ── Tawaruk-specific ──
    purchase_request_date   = db.Column(db.Date)
    murabahah_contract_date = db.Column(db.Date)
    wakalah_date            = db.Column(db.Date)
    wakalah_time            = db.Column(db.String(5))    # "14:30"

    # ── Opsyen / Bai'nah-specific ──
    surat_opsyen_date         = db.Column(db.Date)
    perjanjian_pembelian_date = db.Column(db.Date)
    wakil_pembelian_date      = db.Column(db.Date)
    perjanjian_jualan_date    = db.Column(db.Date)
    wakil_penjualan_date      = db.Column(db.Date)

    # ── Shared date fields ──
    disbursement_date          = db.Column(db.Date)
    disbursement_time          = db.Column(db.String(5))  # "14:30"
    surat_tawaran_date         = db.Column(db.Date)
    perjanjian_pembiayaan_date = db.Column(db.Date)

    # ── Early Settlement (Ibra') ──
    klausa_early_settlement = db.Column(db.Boolean)
    amount_rebate           = db.Column(db.Float)
    fee_rebate              = db.Column(db.Float)
    settlement_date         = db.Column(db.Date)

    # ── Document uploads ──
    doc_msc                    = db.Column(db.String(300))  # Tawaruk: MSC filename
    doc_perjanjian_pembelian   = db.Column(db.String(300))  # Opsyen: Perjanjian Pembelian filename

    # ── AI results ──
    ai_result_json = db.Column(db.Text)       # Full JSON findings
    ai_processed   = db.Column(db.Boolean, default=False)
    ai_conclusion  = db.Column(db.String(30)) # SHARIAH_COMPLIANT | NON_SHARIAH_COMPLIANT | NEEDS_REVIEW

    # ── KoSERI decision (SHADOW — internal only, never in reports) ──
    koseri_decision   = db.Column(db.String(30))  # compliant | non_compliant
    koseri_notes      = db.Column(db.Text)
    koseri_decided_at = db.Column(db.DateTime)

    # ── Per-case flagging (resubmission workflow) ──
    koseri_flag          = db.Column(db.String(20))   # None | 'flagged' | 'override'
    koseri_flag_reason   = db.Column(db.Text)         # Why KoSERI flagged this case
    fedkew_response      = db.Column(db.String(20))   # None | 'fixed' | 'cannot_fix'
    fedkew_response_note = db.Column(db.Text)         # FedKew explanation (if cannot fix)

    @property
    def final_decision(self):
        """KoSERI decision overrides AI conclusion."""
        return self.koseri_decision

    @property
    def findings(self):
        """Parse AI findings from JSON."""
        import json
        if not self.ai_result_json:
            return []
        try:
            data = json.loads(self.ai_result_json)
            return data.get('findings', [])
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def high_count(self):
        return sum(1 for f in self.findings if f.get('severity') == 'HIGH')

    @property
    def medium_count(self):
        return sum(1 for f in self.findings if f.get('severity') == 'MEDIUM')

    @property
    def total_findings(self):
        return len(self.findings)


# ── Audit Log ────────────────────────────────────────────────────────────────
class AuditLog(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    user_id   = db.Column(db.Integer, db.ForeignKey('user.id'))
    action    = db.Column(db.String(200))
    detail    = db.Column(db.Text, default='')
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    ip_addr   = db.Column(db.String(45))

    user = db.relationship('User')
