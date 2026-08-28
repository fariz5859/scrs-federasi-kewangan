"""Append 1 new case to each of the 3 existing reviews, then AI-process them."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from models import db, KoperasiReview, Case, AuditLog
from ai_engine import process_case
from datetime import date, datetime, timezone

app = create_app()

with app.app_context():
    reviews = KoperasiReview.query.filter(
        KoperasiReview.status == 'koseri_review'
    ).order_by(KoperasiReview.id).all()

    if len(reviews) < 3:
        print('❌ Expected 3 reviews in koseri_review status')
        exit(1)

    r1, r2, r3 = reviews[0], reviews[1], reviews[2]

    # ── Append to Review 1 (Tawaruk) — NON-COMPLIANT: missing murabahah date
    c1 = Case(
        review_id=r1.id, process_type='tawaruk', product_type='peribadi',
        account_no='TWK-004', member_name='Kamal bin Zakaria',
        fin_amount=42000.00, date_appli=date(2026, 2, 10), tenure_period=48,
        surat_tawaran_date=date(2026, 2, 8),
        perjanjian_pembiayaan_date=date(2026, 2, 9),
        wakalah_date=date(2026, 2, 12), wakalah_time='10:30',
        purchase_request_date=date(2026, 2, 13),
        murabahah_contract_date=None,  # ❌ MISSING
        disbursement_date=date(2026, 2, 18), disbursement_time='14:00',
    )
    db.session.add(c1)
    db.session.commit()
    process_case(c1)
    db.session.commit()
    print(f'✅ {r1.reference_no} → TWK-004 appended → AI: {c1.ai_conclusion}')

    # ── Append to Review 2 (Opsyen) — COMPLIANT: perfect sequence
    c2 = Case(
        review_id=r2.id, process_type='opsyen', product_type='peribadi',
        account_no='OPS-004', member_name='Rohani binti Iskandar',
        fin_amount=28000.00, date_appli=date(2026, 2, 5), tenure_period=36,
        surat_tawaran_date=date(2026, 2, 3),
        perjanjian_pembiayaan_date=date(2026, 2, 4),
        surat_opsyen_date=date(2026, 2, 7),
        perjanjian_pembelian_date=date(2026, 2, 10),
        wakil_pembelian_date=date(2026, 2, 11),
        perjanjian_jualan_date=date(2026, 2, 12),
        wakil_penjualan_date=date(2026, 2, 13),
        disbursement_date=date(2026, 2, 15), disbursement_time='11:00',
    )
    db.session.add(c2)
    db.session.commit()
    process_case(c2)
    db.session.commit()
    print(f'✅ {r2.reference_no} → OPS-004 appended → AI: {c2.ai_conclusion}')

    # ── Append to Review 3 (Early Settlement) — COMPLIANT: proper ibra'
    c3 = Case(
        review_id=r3.id, process_type='early_settlement', product_type='kenderaan',
        account_no='ES-004', member_name='Wan Ahmad bin Wan Hussin',
        fin_amount=55000.00, date_appli=date(2025, 8, 15), tenure_period=72,
        klausa_early_settlement=True,
        amount_rebate=8500.00,
        fee_rebate=1200.00,
        settlement_date=date(2026, 2, 10),
    )
    db.session.add(c3)
    db.session.commit()
    process_case(c3)
    db.session.commit()
    print(f'✅ {r3.reference_no} → ES-004 appended → AI: {c3.ai_conclusion}')

    print()
    print('═' * 60)
    print('  3 NEW CASES APPENDED — each review now has 4 cases')
    print('  Login as koseri/koseri123 to see them')
    print('═' * 60)
