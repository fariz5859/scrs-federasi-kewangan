"""
Seed script — Generate 3 reviews (Tawaruk, Opsyen, Early Settlement)
Each with 3 cases: 1 compliant + 2 non-compliant
Then run AI engine and push to koseri_review status.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from models import db, User, KoperasiReview, Case, AuditLog
from ai_engine import process_review
from datetime import datetime, date, timezone
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    db.create_all()

    # Ensure users exist
    fedkew_user = User.query.filter_by(username='fedkew').first()
    if not fedkew_user:
        fedkew_user = User(username='fedkew', password=generate_password_hash('fedkew123'),
                           role='fedkew', name='Pegawai FedKew')
        db.session.add(fedkew_user)
    koseri_user = User.query.filter_by(username='koseri').first()
    if not koseri_user:
        koseri_user = User(username='koseri', password=generate_password_hash('koseri123'),
                           role='koseri', name='Penasihat Syariah')
        db.session.add(koseri_user)
    db.session.commit()

    # ═══════════════════════════════════════════════════════════
    #  REVIEW 1 — TAWARUK (3 cases: 1 compliant, 2 non-compliant)
    # ═══════════════════════════════════════════════════════════
    r1 = KoperasiReview(
        koperasi_name='Koperasi Getah Asli Berhad',
        no_pendaftaran='W-6-0396',
        created_by=fedkew_user.id,
        status='draft'
    )
    r1.generate_reference_no()
    db.session.add(r1)
    db.session.flush()

    # Case T1 — COMPLIANT: Perfect sequence, all dates present, correct order
    db.session.add(Case(
        review_id=r1.id, process_type='tawaruk', product_type='peribadi',
        account_no='TWK-001', member_name='Ahmad bin Ibrahim',
        fin_amount=50000.00, date_appli=date(2026, 1, 5), tenure_period=60,
        surat_tawaran_date=date(2026, 1, 3),        # Before application ✓
        perjanjian_pembiayaan_date=date(2026, 1, 4), # Before application ✓
        wakalah_date=date(2026, 1, 10), wakalah_time='09:00',           # Step 1 ✓
        purchase_request_date=date(2026, 1, 11),                        # Step 2 ✓
        murabahah_contract_date=date(2026, 1, 12),                      # Step 3 ✓
        disbursement_date=date(2026, 1, 15), disbursement_time='14:00', # Step 4 ✓
    ))

    # Case T2 — NON-COMPLIANT: Disbursement BEFORE Murabahah (T3 violation)
    db.session.add(Case(
        review_id=r1.id, process_type='tawaruk', product_type='kenderaan',
        account_no='TWK-002', member_name='Fatimah binti Hassan',
        fin_amount=85000.00, date_appli=date(2026, 1, 6), tenure_period=84,
        surat_tawaran_date=date(2026, 1, 4),
        perjanjian_pembiayaan_date=date(2026, 1, 5),
        wakalah_date=date(2026, 1, 10), wakalah_time='10:00',
        purchase_request_date=date(2026, 1, 11),
        murabahah_contract_date=date(2026, 1, 20),   # ❌ AFTER disbursement
        disbursement_date=date(2026, 1, 14), disbursement_time='11:00', # ❌ Before murabahah
    ))

    # Case T3 — NON-COMPLIANT: Same day wakalah + disbursement, bad time order (T4 violation)
    db.session.add(Case(
        review_id=r1.id, process_type='tawaruk', product_type='peralatan_rumah',
        account_no='TWK-003', member_name='Razak bin Ali',
        fin_amount=15000.00, date_appli=date(2026, 2, 1), tenure_period=36,
        surat_tawaran_date=date(2026, 1, 28),
        perjanjian_pembiayaan_date=date(2026, 1, 29),
        wakalah_date=date(2026, 2, 5), wakalah_time='15:00',           # ❌ AFTER disbursement time
        purchase_request_date=date(2026, 2, 4),                        # ❌ Before wakalah too
        murabahah_contract_date=date(2026, 2, 6),
        disbursement_date=date(2026, 2, 5), disbursement_time='09:00', # ❌ Same day, earlier time
    ))
    db.session.commit()
    print(f'✅ Review 1 (Tawaruk): {r1.reference_no} — 3 cases created')

    # ═══════════════════════════════════════════════════════════
    #  REVIEW 2 — OPSYEN/BAI'NAH (3 cases: 1 compliant, 2 non-compliant)
    # ═══════════════════════════════════════════════════════════
    r2 = KoperasiReview(
        koperasi_name='Koperasi Sawit Jaya Berhad',
        no_pendaftaran='W-8-1234',
        created_by=fedkew_user.id,
        status='draft'
    )
    r2.generate_reference_no()
    db.session.add(r2)
    db.session.flush()

    # Case O1 — COMPLIANT: Perfect Bai'nah sequence
    db.session.add(Case(
        review_id=r2.id, process_type='opsyen', product_type='peribadi',
        account_no='OPS-001', member_name='Siti Aminah binti Yusof',
        fin_amount=30000.00, date_appli=date(2026, 1, 10), tenure_period=48,
        surat_tawaran_date=date(2026, 1, 8),
        perjanjian_pembiayaan_date=date(2026, 1, 9),
        surat_opsyen_date=date(2026, 1, 12),
        perjanjian_pembelian_date=date(2026, 1, 14),    # Step 1 ✓
        wakil_pembelian_date=date(2026, 1, 15),         # Step 2 ✓
        perjanjian_jualan_date=date(2026, 1, 16),       # Step 3 ✓
        wakil_penjualan_date=date(2026, 1, 17),         # Step 4 ✓
        disbursement_date=date(2026, 1, 20), disbursement_time='10:00', # Step 5 ✓
    ))

    # Case O2 — NON-COMPLIANT: Sale agreement BEFORE purchase agreement (O3 violation)
    db.session.add(Case(
        review_id=r2.id, process_type='opsyen', product_type='kenderaan',
        account_no='OPS-002', member_name='Muhammad Hafiz bin Razali',
        fin_amount=65000.00, date_appli=date(2026, 1, 15), tenure_period=72,
        surat_tawaran_date=date(2026, 1, 12),
        perjanjian_pembiayaan_date=date(2026, 1, 14),
        surat_opsyen_date=date(2026, 1, 16),
        perjanjian_pembelian_date=date(2026, 1, 25),    # ❌ AFTER sale agreement
        wakil_pembelian_date=date(2026, 1, 26),
        perjanjian_jualan_date=date(2026, 1, 20),       # ❌ Before purchase!
        wakil_penjualan_date=date(2026, 1, 21),
        disbursement_date=date(2026, 1, 28), disbursement_time='11:00',
    ))

    # Case O3 — NON-COMPLIANT: Missing perjanjian pembelian entirely (O2 HIGH violation)
    db.session.add(Case(
        review_id=r2.id, process_type='opsyen', product_type='peralatan_rumah',
        account_no='OPS-003', member_name='Noraini binti Abdullah',
        fin_amount=12000.00, date_appli=date(2026, 2, 1), tenure_period=24,
        surat_tawaran_date=date(2026, 1, 28),
        perjanjian_pembiayaan_date=date(2026, 1, 30),
        surat_opsyen_date=date(2026, 2, 2),
        perjanjian_pembelian_date=None,                  # ❌ MISSING — mandatory
        wakil_pembelian_date=None,                       # ❌ Also missing
        perjanjian_jualan_date=date(2026, 2, 5),
        wakil_penjualan_date=date(2026, 2, 6),
        disbursement_date=date(2026, 2, 8), disbursement_time='14:30',
    ))
    db.session.commit()
    print(f'✅ Review 2 (Opsyen): {r2.reference_no} — 3 cases created')

    # ═══════════════════════════════════════════════════════════
    #  REVIEW 3 — EARLY SETTLEMENT (3 cases: 1 compliant, 2 non-compliant)
    # ═══════════════════════════════════════════════════════════
    r3 = KoperasiReview(
        koperasi_name='Koperasi Nelayan Pantai Timur',
        no_pendaftaran='W-12-5678',
        created_by=fedkew_user.id,
        status='draft'
    )
    r3.generate_reference_no()
    db.session.add(r3)
    db.session.flush()

    # Case E1 — COMPLIANT: Has klausa, good rebate, fee < rebate
    db.session.add(Case(
        review_id=r3.id, process_type='early_settlement', product_type='peribadi',
        account_no='ES-001', member_name='Zainab binti Osman',
        fin_amount=40000.00, date_appli=date(2025, 6, 1), tenure_period=60,
        klausa_early_settlement=True,           # ✓ Has clause
        amount_rebate=5200.00,                  # ✓ Rebate given
        fee_rebate=800.00,                      # ✓ Fee < rebate
        settlement_date=date(2026, 1, 15),
    ))

    # Case E2 — NON-COMPLIANT: No klausa Ibra' (E1 violation) + no rebate (E2 violation)
    db.session.add(Case(
        review_id=r3.id, process_type='early_settlement', product_type='kenderaan',
        account_no='ES-002', member_name='Ismail bin Mohd Noor',
        fin_amount=70000.00, date_appli=date(2025, 3, 10), tenure_period=84,
        klausa_early_settlement=False,          # ❌ No clause
        amount_rebate=None,                     # ❌ No rebate given
        fee_rebate=1500.00,
        settlement_date=date(2026, 2, 1),
    ))

    # Case E3 — NON-COMPLIANT: Fee >= Rebate (E3 violation — penalty disguised as fee)
    db.session.add(Case(
        review_id=r3.id, process_type='early_settlement', product_type='peribadi',
        account_no='ES-003', member_name='Hasnah binti Karim',
        fin_amount=25000.00, date_appli=date(2025, 9, 20), tenure_period=48,
        klausa_early_settlement=True,           # ✓ Has clause
        amount_rebate=3000.00,                  # ✓ Rebate given
        fee_rebate=3500.00,                     # ❌ Fee EXCEEDS rebate!
        settlement_date=date(2026, 1, 25),
    ))
    db.session.commit()
    print(f'✅ Review 3 (Early Settlement): {r3.reference_no} — 3 cases created')

    # ═══════════════════════════════════════════════════════════
    #  SUBMIT & AI PROCESS ALL 3 REVIEWS → koseri_review
    # ═══════════════════════════════════════════════════════════
    for review in [r1, r2, r3]:
        review.status = 'submitted'
        review.submitted_at = datetime.now(timezone.utc)
        db.session.commit()

        summary = process_review(review)

        review.status = 'koseri_review'
        db.session.commit()

        print(f'  📊 {review.reference_no}: {summary["total_cases"]} cases — '
              f'{summary["compliant"]} compliant, '
              f'{summary["non_compliant"]} non-compliant, '
              f'{summary["needs_review"]} needs_review')

        # Audit log
        db.session.add(AuditLog(
            user_id=fedkew_user.id, action='submit_review',
            detail=f'SEED: {review.reference_no} submitted → AI processed → koseri_review',
            ip_addr='127.0.0.1'
        ))
        db.session.commit()

    print()
    print('═' * 60)
    print('  ALL 3 REVIEWS NOW AT koseri_review STATUS')
    print('  Login as koseri/koseri123 to review them')
    print('═' * 60)
