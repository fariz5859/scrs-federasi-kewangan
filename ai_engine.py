"""
AI Engine — Shariah Compliance Rule-Based Analysis Engine v2.0
═══════════════════════════════════════════════════════════════

Pure Python. No external API. No document parsing.
Operates on structured date/value inputs from FedKew.

Rules:
  T0-T5 : Tawaruk (6 checks)
  O0-O4 : Opsyen / Bai'nah (5 checks)
  E1-E3 : Early Settlement / Ibra' (3 checks)

Sources: SKM GP7B, GP28, BNM SAC Resolution 51, Shariah Tartib
"""
import json
from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════════════════════════════
#  FIELD LABELS (Malay)
# ═══════════════════════════════════════════════════════════════════════════════

FIELD_LABELS = {
    'purchase_request_date':   'Tarikh Permohonan Belian Komoditi',
    'murabahah_contract_date': 'Tarikh Kontrak Murabahah',
    'wakalah_date':            'Tarikh Wakalah',
    'wakalah_time':            'Masa Wakalah',
    'disbursement_date':       'Tarikh Pengeluaran Wang',
    'disbursement_time':       'Masa Pengeluaran Wang',
    'surat_tawaran_date':      'Tarikh Surat Tawaran',
    'perjanjian_pembiayaan_date': 'Tarikh Perjanjian Pembiayaan',
    'date_appli':              'Tarikh Proses Permohonan',
    'surat_opsyen_date':       'Tarikh Surat Opsyen',
    'perjanjian_pembelian_date': 'Tarikh Perjanjian Pembelian',
    'wakil_pembelian_date':    'Tarikh Wakil Pembelian',
    'perjanjian_jualan_date':  'Tarikh Perjanjian Jualan',
    'wakil_penjualan_date':    'Tarikh Wakil Penjualan',
}


def _fmt_date(d):
    """Format date for display."""
    if d is None:
        return 'TIADA'
    return d.strftime('%d/%m/%Y')


# ═══════════════════════════════════════════════════════════════════════════════
#  TAWARUK RULES (T0-T5)
# ═══════════════════════════════════════════════════════════════════════════════

def run_tawaruk_checks(case):
    """Run all Tawaruk compliance checks. Returns list of finding dicts."""
    findings = []

    # ── T0: Missing Date Detection ──────────────────────────────────────
    required = [
        'purchase_request_date', 'murabahah_contract_date',
        'wakalah_date', 'wakalah_time',
        'disbursement_date', 'disbursement_time',
        'surat_tawaran_date', 'perjanjian_pembiayaan_date'
    ]
    missing = []
    for field in required:
        val = getattr(case, field, None)
        if val is None or val == '':
            missing.append(FIELD_LABELS.get(field, field))

    if missing:
        is_resubmit = (case.review and case.review.resubmission_count > 0)
        severity = 'HIGH' if is_resubmit else 'MEDIUM'
        findings.append({
            'rule_id': 'T0',
            'rule_name': 'Semakan Kelengkapan Data',
            'severity': severity,
            'finding': f"Tarikh berikut tidak diisi: {', '.join(missing)}",
            'effect': 'Data tidak lengkap — semakan Syariah tidak dapat dilaksanakan sepenuhnya'
                      if not is_resubmit else
                      'Dokumen masih tidak lengkap selepas penghantaran semula — dianggap tidak patuh Syariah',
            'rectification': 'Sila kemaskini tarikh yang hilang dan hantar semula'
                             if not is_resubmit else
                             'Koperasi perlu mendapatkan dokumen yang hilang atau melaksanakan kontrak baharu',
            'source': 'Prinsip Audit Syariah SKM'
        })

    # ── T1: Purchase Request Date ───────────────────────────────────────
    if not case.purchase_request_date:
        findings.append({
            'rule_id': 'T1',
            'rule_name': 'Permohonan Belian Komoditi',
            'severity': 'MEDIUM',
            'finding': 'Tarikh Permohonan Belian Komoditi tiada',
            'effect': 'Pembelian komoditi tidak dapat disahkan',
            'rectification': 'Dapatkan dokumen permohonan belian komoditi',
            'source': 'Proses Tawaruk — Permohonan Belian'
        })

    # ── T2: Murabahah Contract Date ─────────────────────────────────────
    if not case.murabahah_contract_date:
        findings.append({
            'rule_id': 'T2',
            'rule_name': 'Kontrak Murabahah',
            'severity': 'HIGH',
            'finding': 'Tarikh Kontrak Murabahah tiada',
            'effect': 'Tanpa Kontrak Murabahah, tiada jualan sah berlaku — '
                      'pembiayaan tidak sah dari segi Syariah',
            'rectification': 'Kontrak Murabahah wajib ada — jika tiada, '
                             'pembiayaan perlu dibatalkan dan dilaksanakan semula',
            'source': 'Prinsip Murabahah — Kontrak Jualan Wajib'
        })

    # ── T3: Full Date Sequence Check (Tartib) ───────────────────────────
    sequence = [
        ('wakalah_date',            'Wakalah'),
        ('purchase_request_date',   'Permohonan Belian'),
        ('murabahah_contract_date', 'Kontrak Murabahah'),
        ('disbursement_date',       'Pengeluaran Wang'),
    ]
    for i in range(len(sequence) - 1):
        d1 = getattr(case, sequence[i][0], None)
        d2 = getattr(case, sequence[i + 1][0], None)
        if d1 and d2 and d1 > d2:
            findings.append({
                'rule_id': 'T3',
                'rule_name': 'Semakan Urutan Tarikh (Tartib)',
                'severity': 'HIGH',
                'finding': f"{sequence[i][1]} ({_fmt_date(d1)}) berlaku SELEPAS "
                           f"{sequence[i + 1][1]} ({_fmt_date(d2)})",
                'effect': 'Tartib tidak dipatuhi — urutan proses Syariah terbalik. '
                          'Transaksi mungkin tidak sah.',
                'rectification': 'Batalkan kontrak dan laksanakan semula mengikut '
                                 'urutan yang betul',
                'source': 'Prinsip Tartib Syariah — Urutan Kontrak'
            })

    # ── T4: Same-Day Time Check ─────────────────────────────────────────
    if (case.wakalah_date and case.disbursement_date
            and case.wakalah_date == case.disbursement_date):
        wt = case.wakalah_time or ''
        dt = case.disbursement_time or ''
        if wt and dt and wt >= dt:
            findings.append({
                'rule_id': 'T4',
                'rule_name': 'Semakan Masa Hari Sama',
                'severity': 'HIGH',
                'finding': f"Wakalah ({wt}) berlaku pada/selepas Pengeluaran Wang "
                           f"({dt}) pada hari yang sama ({_fmt_date(case.wakalah_date)})",
                'effect': 'Wang dikeluarkan sebelum pelantikan wakil — Tartib tidak sah',
                'rectification': 'Pastikan Wakalah dilaksanakan SEBELUM pengeluaran wang '
                                 'pada hari yang sama',
                'source': 'Prinsip Tartib Syariah — Masa Pelaksanaan'
            })

    # ── T5: Document Prep Before Application ────────────────────────────
    if case.surat_tawaran_date and case.date_appli:
        if case.surat_tawaran_date > case.date_appli:
            findings.append({
                'rule_id': 'T5',
                'rule_name': 'Dokumen Sebelum Proses Permohonan',
                'severity': 'MEDIUM',
                'finding': f"Surat Tawaran ({_fmt_date(case.surat_tawaran_date)}) "
                           f"dikeluarkan SELEPAS tarikh proses permohonan "
                           f"({_fmt_date(case.date_appli)})",
                'effect': 'Proses permohonan berjalan tanpa surat tawaran rasmi',
                'rectification': 'Pastikan surat tawaran ditandatangani sebelum '
                                 'proses permohonan bermula',
                'source': 'SKM GP28 — Tadbir Urus Syariah'
            })

    if case.perjanjian_pembiayaan_date and case.date_appli:
        if case.perjanjian_pembiayaan_date > case.date_appli:
            findings.append({
                'rule_id': 'T5',
                'rule_name': 'Dokumen Sebelum Proses Permohonan',
                'severity': 'MEDIUM',
                'finding': f"Perjanjian Pembiayaan ({_fmt_date(case.perjanjian_pembiayaan_date)}) "
                           f"ditandatangani SELEPAS tarikh proses permohonan "
                           f"({_fmt_date(case.date_appli)})",
                'effect': 'Proses permohonan berjalan tanpa perjanjian pembiayaan',
                'rectification': 'Pastikan perjanjian pembiayaan ditandatangani sebelum '
                                 'proses permohonan bermula',
                'source': 'SKM GP28 — Tadbir Urus Syariah'
            })

    return findings


# ═══════════════════════════════════════════════════════════════════════════════
#  OPSYEN / BAI'NAH RULES (O0-O4)
# ═══════════════════════════════════════════════════════════════════════════════

def run_opsyen_checks(case):
    """Run all Opsyen/Bai'nah compliance checks."""
    findings = []

    # ── O0: Missing Date Detection ──────────────────────────────────────
    required = [
        'surat_opsyen_date', 'perjanjian_pembelian_date',
        'wakil_pembelian_date', 'perjanjian_jualan_date',
        'wakil_penjualan_date', 'disbursement_date',
        'surat_tawaran_date', 'perjanjian_pembiayaan_date'
    ]
    missing = []
    for field in required:
        val = getattr(case, field, None)
        if val is None or val == '':
            missing.append(FIELD_LABELS.get(field, field))

    if missing:
        is_resubmit = (case.review and case.review.resubmission_count > 0)
        severity = 'HIGH' if is_resubmit else 'MEDIUM'
        findings.append({
            'rule_id': 'O0',
            'rule_name': 'Semakan Kelengkapan Data',
            'severity': severity,
            'finding': f"Tarikh berikut tidak diisi: {', '.join(missing)}",
            'effect': 'Data tidak lengkap — semakan Syariah tidak dapat dilaksanakan sepenuhnya'
                      if not is_resubmit else
                      'Dokumen masih tidak lengkap selepas penghantaran semula — dianggap tidak patuh Syariah',
            'rectification': 'Sila kemaskini tarikh yang hilang dan hantar semula'
                             if not is_resubmit else
                             'Koperasi perlu mendapatkan dokumen yang hilang',
            'source': 'Prinsip Audit Syariah SKM'
        })

    # ── O1: Surat Opsyen ────────────────────────────────────────────────
    if not case.surat_opsyen_date:
        findings.append({
            'rule_id': 'O1',
            'rule_name': 'Surat Opsyen',
            'severity': 'MEDIUM',
            'finding': 'Tarikh Surat Opsyen tiada',
            'effect': 'Pilihan anggota terhadap aset tidak didokumenkan',
            'rectification': 'Dapatkan Surat Opsyen yang ditandatangani',
            'source': 'Proses Bai\'nah — Surat Opsyen'
        })

    # ── O2: Perjanjian Pembelian ────────────────────────────────────────
    if not case.perjanjian_pembelian_date:
        findings.append({
            'rule_id': 'O2',
            'rule_name': 'Perjanjian Pembelian',
            'severity': 'HIGH',
            'finding': 'Tarikh Perjanjian Pembelian tiada — kontrak Bai\'nah tidak sah',
            'effect': 'Tanpa perjanjian pembelian, tiada transaksi belian yang sah berlaku. '
                      'Kontrak Bai\'nah tidak boleh diteruskan.',
            'rectification': 'Perjanjian pembelian wajib ada — jika tiada, '
                             'pembiayaan perlu dibatalkan dan dilaksanakan semula',
            'source': 'Prinsip Bai\'nah — Kontrak Pembelian Wajib'
        })

    # ── O3: Full Bai'nah Sequence Check ─────────────────────────────────
    sequence = [
        ('perjanjian_pembelian_date', 'Perjanjian Pembelian'),
        ('wakil_pembelian_date',     'Wakil Pembelian'),
        ('perjanjian_jualan_date',   'Perjanjian Jualan'),
        ('wakil_penjualan_date',     'Wakil Penjualan'),
        ('disbursement_date',        'Pengeluaran Wang'),
    ]
    for i in range(len(sequence) - 1):
        d1 = getattr(case, sequence[i][0], None)
        d2 = getattr(case, sequence[i + 1][0], None)
        if d1 and d2 and d1 > d2:
            findings.append({
                'rule_id': 'O3',
                'rule_name': 'Semakan Urutan Tarikh Bai\'nah (Tartib)',
                'severity': 'HIGH',
                'finding': f"{sequence[i][1]} ({_fmt_date(d1)}) berlaku SELEPAS "
                           f"{sequence[i + 1][1]} ({_fmt_date(d2)})",
                'effect': 'Urutan Bai\'nah tidak dipatuhi — pembelian mesti berlaku '
                          'sebelum penjualan semula. Transaksi mungkin tidak sah.',
                'rectification': 'Batalkan kontrak dan laksanakan semula mengikut '
                                 'urutan yang betul: Pembelian → Jualan → Pengeluaran',
                'source': 'Prinsip Tartib Syariah — Urutan Bai\'nah'
            })

    # ── O4: Document Prep Before Application ─────────────────────────────
    if case.surat_tawaran_date and case.date_appli:
        if case.surat_tawaran_date > case.date_appli:
            findings.append({
                'rule_id': 'O4',
                'rule_name': 'Dokumen Sebelum Proses Permohonan',
                'severity': 'MEDIUM',
                'finding': f"Surat Tawaran ({_fmt_date(case.surat_tawaran_date)}) "
                           f"dikeluarkan SELEPAS tarikh proses permohonan "
                           f"({_fmt_date(case.date_appli)})",
                'effect': 'Proses permohonan berjalan tanpa surat tawaran rasmi',
                'rectification': 'Pastikan surat tawaran ditandatangani sebelum proses bermula',
                'source': 'SKM GP28 — Tadbir Urus Syariah'
            })

    if case.perjanjian_pembiayaan_date and case.date_appli:
        if case.perjanjian_pembiayaan_date > case.date_appli:
            findings.append({
                'rule_id': 'O4',
                'rule_name': 'Dokumen Sebelum Proses Permohonan',
                'severity': 'MEDIUM',
                'finding': f"Perjanjian Pembiayaan ({_fmt_date(case.perjanjian_pembiayaan_date)}) "
                           f"ditandatangani SELEPAS tarikh proses permohonan "
                           f"({_fmt_date(case.date_appli)})",
                'effect': 'Proses permohonan berjalan tanpa perjanjian pembiayaan',
                'rectification': 'Pastikan perjanjian pembiayaan ditandatangani sebelum proses bermula',
                'source': 'SKM GP28 — Tadbir Urus Syariah'
            })

    return findings


# ═══════════════════════════════════════════════════════════════════════════════
#  EARLY SETTLEMENT / IBRA' RULES (E1-E3)
# ═══════════════════════════════════════════════════════════════════════════════

def run_early_settlement_checks(case):
    """Run Early Settlement / Ibra' compliance checks per SKM GP7B."""
    findings = []

    # ── E1: Klausa Ibra' Must Exist ─────────────────────────────────────
    if case.klausa_early_settlement is False or case.klausa_early_settlement is None:
        findings.append({
            'rule_id': 'E1',
            'rule_name': 'Klausa Ibra\' Dalam Perjanjian',
            'severity': 'HIGH',
            'finding': 'Tiada klausa Ibra\' (penyelesaian awal) dalam perjanjian pembiayaan',
            'effect': 'Melanggar GP7B Para 10 — koperasi wajib menyatakan komitmen '
                      'pemberian Ibra\' dalam surat tawaran dan dokumen perundangan',
            'rectification': 'Masukkan klausa Ibra\' dalam semua perjanjian pembiayaan. '
                             'Pinda dokumen sedia ada untuk memasukkan klausa ini.',
            'source': 'SKM GP7B Para 10 — Klausa Ibra\' Wajib'
        })

    # ── E2: Ibra' Was Actually Given ────────────────────────────────────
    if case.amount_rebate is None or case.amount_rebate <= 0:
        findings.append({
            'rule_id': 'E2',
            'rule_name': 'Pemberian Ibra\' (Rebat)',
            'severity': 'HIGH',
            'finding': 'Ibra\' (rebat keuntungan belum diperolehi) tidak diberikan '
                       'kepada anggota yang membuat penyelesaian awal',
            'effect': 'Melanggar GP7B Para 7 — koperasi WAJIB memberi Ibra\' kepada '
                      'SEMUA pelanggan penyelesaian awal tanpa pengecualian',
            'rectification': 'Kira dan berikan Ibra\' kepada anggota mengikut formula: '
                             'Ibra\' = Keuntungan Belum Akru – Caj Penyelesaian Awal. '
                             'Bayar balik perbezaan kepada anggota.',
            'source': 'SKM GP7B Para 7 — Pemberian Ibra\' Wajib'
        })

    # ── E3: Fee Must Not Wipe Out Rebate ────────────────────────────────
    if (case.fee_rebate is not None and case.amount_rebate is not None
            and case.amount_rebate > 0 and case.fee_rebate >= case.amount_rebate):
        findings.append({
            'rule_id': 'E3',
            'rule_name': 'Caj Penyelesaian Awal vs Ibra\'',
            'severity': 'HIGH',
            'finding': f"Caj penyelesaian awal (RM {case.fee_rebate:,.2f}) melebihi atau "
                       f"menyamai jumlah Ibra' (RM {case.amount_rebate:,.2f})",
            'effect': 'Anggota tidak mendapat sebarang manfaat Ibra\' — caj bersifat penalti '
                      'dan melanggar larangan caj penalti dalam GP7B',
            'rectification': 'Hapuskan atau kurangkan caj penyelesaian awal — hanya kos '
                             'sebenar yang benar-benar ditanggung oleh koperasi boleh dicaj. '
                             'Bayar balik lebihan caj kepada anggota.',
            'source': 'SKM GP7B Muka Surat 8 — Larangan Caj Penalti'
        })

    return findings


# ═══════════════════════════════════════════════════════════════════════════════
#  CONCLUSION LOGIC
# ═══════════════════════════════════════════════════════════════════════════════

def determine_conclusion(findings):
    """
    Determine AI conclusion from findings.
    Returns: SHARIAH_COMPLIANT | NON_SHARIAH_COMPLIANT | NEEDS_REVIEW
    """
    high   = sum(1 for f in findings if f.get('severity') == 'HIGH')
    medium = sum(1 for f in findings if f.get('severity') == 'MEDIUM')

    if high > 0:
        return 'NON_SHARIAH_COMPLIANT'
    elif medium > 0:
        return 'NEEDS_REVIEW'
    else:
        return 'SHARIAH_COMPLIANT'


# ═══════════════════════════════════════════════════════════════════════════════
#  PROCESS SINGLE CASE
# ═══════════════════════════════════════════════════════════════════════════════

def process_case(case):
    """
    Run the appropriate rule engine on a single Case object.
    Returns dict with full results (stored as ai_result_json).
    """
    findings = []

    if case.process_type == 'tawaruk':
        findings = run_tawaruk_checks(case)
    elif case.process_type == 'opsyen':
        findings = run_opsyen_checks(case)
    elif case.process_type == 'early_settlement':
        findings = run_early_settlement_checks(case)

    conclusion = determine_conclusion(findings)

    result = {
        'case_id': case.id,
        'account_no': case.account_no,
        'process_type': case.process_type,
        'product_type': case.product_type,
        'findings': findings,
        'total_findings': len(findings),
        'high_count': sum(1 for f in findings if f.get('severity') == 'HIGH'),
        'medium_count': sum(1 for f in findings if f.get('severity') == 'MEDIUM'),
        'ai_conclusion': conclusion,
        'processed_at': datetime.now(timezone.utc).isoformat()
    }

    # Update case in DB
    case.ai_result_json = json.dumps(result, ensure_ascii=False, default=str)
    case.ai_processed = True
    case.ai_conclusion = conclusion

    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  PROCESS ENTIRE REVIEW
# ═══════════════════════════════════════════════════════════════════════════════

def process_review(review):
    """
    Process ALL cases in a KoperasiReview.
    Returns summary dict with aggregate statistics.
    """
    from models import db

    results = []
    for case in review.cases:
        if not case.ai_processed:
            result = process_case(case)
            results.append(result)

    # Update review status
    review.status = 'ai_processed'
    review.ai_processed_at = datetime.now(timezone.utc)
    db.session.commit()

    # Aggregate summary
    total   = len(review.cases)
    processed = sum(1 for c in review.cases if c.ai_processed)
    compliant = sum(1 for c in review.cases
                    if c.ai_conclusion == 'SHARIAH_COMPLIANT')
    non_compliant = sum(1 for c in review.cases
                        if c.ai_conclusion == 'NON_SHARIAH_COMPLIANT')
    needs_review = sum(1 for c in review.cases
                       if c.ai_conclusion == 'NEEDS_REVIEW')

    all_findings = []
    for c in review.cases:
        all_findings.extend(c.findings)

    # Findings by severity
    by_severity = {}
    for f in all_findings:
        sev = f.get('severity', 'UNKNOWN')
        by_severity[sev] = by_severity.get(sev, 0) + 1

    # Findings by rule_id
    by_rule = {}
    for f in all_findings:
        rid = f.get('rule_id', 'UNKNOWN')
        by_rule[rid] = by_rule.get(rid, 0) + 1

    # Findings by product_type
    by_product = {}
    for c in review.cases:
        pt = c.product_type or 'Tidak Dinyatakan'
        if pt not in by_product:
            by_product[pt] = {'total': 0, 'compliant': 0, 'non_compliant': 0, 'needs_review': 0}
        by_product[pt]['total'] += 1
        if c.ai_conclusion == 'SHARIAH_COMPLIANT':
            by_product[pt]['compliant'] += 1
        elif c.ai_conclusion == 'NON_SHARIAH_COMPLIANT':
            by_product[pt]['non_compliant'] += 1
        else:
            by_product[pt]['needs_review'] += 1

    summary = {
        'review_id': review.id,
        'reference_no': review.reference_no,
        'total_cases': total,
        'processed': processed,
        'compliant': compliant,
        'non_compliant': non_compliant,
        'needs_review': needs_review,
        'total_findings': len(all_findings),
        'by_severity': by_severity,
        'by_rule': by_rule,
        'by_product': by_product,
        'cases_affected_pct': round(
            ((non_compliant + needs_review) / total * 100) if total > 0 else 0, 1
        ),
    }

    return summary
