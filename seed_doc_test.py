"""Seed comprehensive test data — Tawaruk, Opsyen/Bai'nah, Early Settlement.
Mix of: clean (no issues), sequence violations, missing data, same-day timing issues.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from app import app
from models import db, User, KoperasiReview, Case, AuditLog
from datetime import date, datetime, timezone
from werkzeug.security import generate_password_hash
from ai_engine import process_case


# ── Fake PDF generator ────────────────────────────────────────────────────────
def make_fake_pdf(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n0000000009 00000 n \n"
        b"0000000058 00000 n \n0000000115 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n210\n%%EOF"
    )
    with open(path, 'wb') as f:
        f.write(pdf)


with app.app_context():
    # ── Users ──────────────────────────────────────────────────────────────
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username='admin', name='Admin FedKew', role='fedkew',
                     password=generate_password_hash('admin123'))
        db.session.add(admin)
        db.session.commit()
        print("✅ Created FedKew user: admin / admin123")

    reviewer = User.query.filter_by(username='koseri').first()
    if not reviewer:
        reviewer = User(username='koseri', name='Dr. Ahmad (KoSERI)', role='koseri',
                        password=generate_password_hash('koseri123'))
        db.session.add(reviewer)
        db.session.commit()
        print("✅ Created KoSERI user: koseri / koseri123")

    # ── Review ─────────────────────────────────────────────────────────────
    review = KoperasiReview(
        koperasi_name='Koperasi Getah Berhad',
        no_pendaftaran='KP-1234/2020',
        created_by=admin.id,
        status='draft',
    )
    review.generate_reference_no()
    db.session.add(review)
    db.session.commit()
    print(f"\n📋 Review: {review.reference_no}")

    uploads_base = os.path.join(os.path.dirname(__file__), 'uploads', 'cases')

    # ══════════════════════════════════════════════════════════════════════
    #  TAWARUK CASES (4 cases)
    # ══════════════════════════════════════════════════════════════════════

    # T1: ✅ CLEAN — all dates correct, proper sequence
    t1 = Case(
        review_id=review.id, process_type='tawaruk', product_type='peribadi',
        account_no='TWK-001', member_name='Ahmad bin Ismail', fin_amount=25000.00,
        date_appli=date(2025, 1, 10), tenure_period=60,
        surat_tawaran_date=date(2025, 1, 8),
        perjanjian_pembiayaan_date=date(2025, 1, 9),
        wakalah_date=date(2025, 2, 1), wakalah_time='09:00',
        purchase_request_date=date(2025, 2, 1),
        murabahah_contract_date=date(2025, 2, 2),
        disbursement_date=date(2025, 2, 3), disbursement_time='14:00',
        doc_msc='MSC_Ahmad_TWK001.pdf',
    )
    db.session.add(t1)
    db.session.commit()
    make_fake_pdf(os.path.join(uploads_base, str(t1.id), 'MSC_Ahmad_TWK001.pdf'))
    process_case(t1)
    db.session.commit()
    print(f"  TWK-001 Ahmad (CLEAN): {t1.ai_conclusion}")

    # T2: ❌ SEQUENCE VIOLATION — disbursement before murabahah contract
    t2 = Case(
        review_id=review.id, process_type='tawaruk', product_type='peribadi',
        account_no='TWK-002', member_name='Hassan bin Ali', fin_amount=18000.00,
        date_appli=date(2025, 3, 5), tenure_period=48,
        surat_tawaran_date=date(2025, 3, 3),
        perjanjian_pembiayaan_date=date(2025, 3, 4),
        wakalah_date=date(2025, 3, 10), wakalah_time='10:00',
        purchase_request_date=date(2025, 3, 11),
        murabahah_contract_date=date(2025, 3, 15),     # contract AFTER disbursement!
        disbursement_date=date(2025, 3, 12), disbursement_time='11:00',  # disbursed early
        doc_msc='MSC_Hassan_TWK002.pdf',
    )
    db.session.add(t2)
    db.session.commit()
    make_fake_pdf(os.path.join(uploads_base, str(t2.id), 'MSC_Hassan_TWK002.pdf'))
    process_case(t2)
    db.session.commit()
    print(f"  TWK-002 Hassan (TARTIB VIOLATION): {t2.ai_conclusion}")

    # T3: ⚠️ MISSING DATA — no wakalah date, no murabahah date
    t3 = Case(
        review_id=review.id, process_type='tawaruk', product_type='kenderaan',
        account_no='TWK-003', member_name='Aminah binti Yusof', fin_amount=42000.00,
        date_appli=date(2025, 4, 1), tenure_period=84,
        surat_tawaran_date=date(2025, 3, 28),
        perjanjian_pembiayaan_date=date(2025, 3, 30),
        wakalah_date=None, wakalah_time=None,           # MISSING
        purchase_request_date=date(2025, 4, 5),
        murabahah_contract_date=None,                    # MISSING
        disbursement_date=date(2025, 4, 10), disbursement_time='09:30',
    )
    db.session.add(t3)
    db.session.commit()
    process_case(t3)
    db.session.commit()
    print(f"  TWK-003 Aminah (MISSING DATA): {t3.ai_conclusion}")

    # T4: ❌ SAME-DAY TIME ISSUE — wakalah time after disbursement time
    t4 = Case(
        review_id=review.id, process_type='tawaruk', product_type='peribadi',
        account_no='TWK-004', member_name='Razak bin Osman', fin_amount=15000.00,
        date_appli=date(2025, 5, 1), tenure_period=36,
        surat_tawaran_date=date(2025, 4, 28),
        perjanjian_pembiayaan_date=date(2025, 4, 30),
        wakalah_date=date(2025, 5, 5), wakalah_time='15:00',  # wakalah AFTER disbursement
        purchase_request_date=date(2025, 5, 5),
        murabahah_contract_date=date(2025, 5, 5),
        disbursement_date=date(2025, 5, 5), disbursement_time='09:00',  # disbursed at 9am
        doc_msc='MSC_Razak_TWK004.pdf',
    )
    db.session.add(t4)
    db.session.commit()
    make_fake_pdf(os.path.join(uploads_base, str(t4.id), 'MSC_Razak_TWK004.pdf'))
    process_case(t4)
    db.session.commit()
    print(f"  TWK-004 Razak (SAME-DAY TIMING): {t4.ai_conclusion}")

    # ══════════════════════════════════════════════════════════════════════
    #  OPSYEN / BAI'NAH CASES (3 cases)
    # ══════════════════════════════════════════════════════════════════════

    # O1: ✅ CLEAN — proper Bai'nah sequence
    o1 = Case(
        review_id=review.id, process_type='opsyen', product_type='kenderaan',
        account_no='OPS-001', member_name='Siti binti Ali', fin_amount=45000.00,
        date_appli=date(2025, 3, 10), tenure_period=84,
        surat_tawaran_date=date(2025, 3, 8),
        perjanjian_pembiayaan_date=date(2025, 3, 9),
        surat_opsyen_date=date(2025, 3, 15),
        perjanjian_pembelian_date=date(2025, 3, 16),
        wakil_pembelian_date=date(2025, 3, 16),
        perjanjian_jualan_date=date(2025, 3, 17),
        wakil_penjualan_date=date(2025, 3, 17),
        disbursement_date=date(2025, 3, 18), disbursement_time='10:00',
        doc_perjanjian_pembelian='PP_Siti_OPS001.pdf',
    )
    db.session.add(o1)
    db.session.commit()
    make_fake_pdf(os.path.join(uploads_base, str(o1.id), 'PP_Siti_OPS001.pdf'))
    process_case(o1)
    db.session.commit()
    print(f"  OPS-001 Siti (CLEAN): {o1.ai_conclusion}")

    # O2: ❌ SEQUENCE VIOLATION — sale before purchase
    o2 = Case(
        review_id=review.id, process_type='opsyen', product_type='peribadi',
        account_no='OPS-002', member_name='Kamal bin Hashim', fin_amount=30000.00,
        date_appli=date(2025, 6, 1), tenure_period=60,
        surat_tawaran_date=date(2025, 5, 28),
        perjanjian_pembiayaan_date=date(2025, 5, 30),
        surat_opsyen_date=date(2025, 6, 5),
        perjanjian_pembelian_date=date(2025, 6, 10),
        wakil_pembelian_date=date(2025, 6, 10),
        perjanjian_jualan_date=date(2025, 6, 8),         # sale BEFORE purchase!
        wakil_penjualan_date=date(2025, 6, 8),
        disbursement_date=date(2025, 6, 12), disbursement_time='14:00',
        doc_perjanjian_pembelian='PP_Kamal_OPS002.pdf',
    )
    db.session.add(o2)
    db.session.commit()
    make_fake_pdf(os.path.join(uploads_base, str(o2.id), 'PP_Kamal_OPS002.pdf'))
    process_case(o2)
    db.session.commit()
    print(f"  OPS-002 Kamal (SEQUENCE VIOLATION): {o2.ai_conclusion}")

    # O3: ⚠️ MISSING DATA — no perjanjian pembelian, no wakil dates
    o3 = Case(
        review_id=review.id, process_type='opsyen', product_type='peribadi',
        account_no='OPS-003', member_name='Faridah binti Rahman', fin_amount=20000.00,
        date_appli=date(2025, 7, 1), tenure_period=48,
        surat_tawaran_date=date(2025, 6, 28),
        perjanjian_pembiayaan_date=date(2025, 6, 30),
        surat_opsyen_date=date(2025, 7, 5),
        perjanjian_pembelian_date=None,                   # MISSING
        wakil_pembelian_date=None,                        # MISSING
        perjanjian_jualan_date=date(2025, 7, 10),
        wakil_penjualan_date=None,                        # MISSING
        disbursement_date=date(2025, 7, 12), disbursement_time='11:00',
    )
    db.session.add(o3)
    db.session.commit()
    process_case(o3)
    db.session.commit()
    print(f"  OPS-003 Faridah (MISSING DATA): {o3.ai_conclusion}")

    # ══════════════════════════════════════════════════════════════════════
    #  EARLY SETTLEMENT CASES (3 cases)
    # ══════════════════════════════════════════════════════════════════════

    # E1: ✅ CLEAN — Ibra' clause exists, rebate given, fee reasonable
    e1 = Case(
        review_id=review.id, process_type='early_settlement', product_type='peribadi',
        account_no='ES-001', member_name='Zainab binti Kassim', fin_amount=35000.00,
        date_appli=date(2024, 6, 1), tenure_period=60,
        surat_tawaran_date=date(2024, 5, 28),
        perjanjian_pembiayaan_date=date(2024, 5, 30),
        klausa_early_settlement=True,
        amount_rebate=2500.00,
        fee_rebate=150.00,
    )
    db.session.add(e1)
    db.session.commit()
    process_case(e1)
    db.session.commit()
    print(f"  ES-001 Zainab (CLEAN): {e1.ai_conclusion}")

    # E2: ❌ NO IBRA' — clause missing, no rebate given
    e2 = Case(
        review_id=review.id, process_type='early_settlement', product_type='kenderaan',
        account_no='ES-002', member_name='Iskandar bin Musa', fin_amount=55000.00,
        date_appli=date(2024, 9, 1), tenure_period=84,
        surat_tawaran_date=date(2024, 8, 28),
        perjanjian_pembiayaan_date=date(2024, 8, 30),
        klausa_early_settlement=False,                    # NO CLAUSE!
        amount_rebate=0,                                  # NO REBATE!
        fee_rebate=500.00,
    )
    db.session.add(e2)
    db.session.commit()
    process_case(e2)
    db.session.commit()
    print(f"  ES-002 Iskandar (NO IBRA'): {e2.ai_conclusion}")

    # E3: ❌ EXCESSIVE FEE — fee exceeds rebate amount
    e3 = Case(
        review_id=review.id, process_type='early_settlement', product_type='peribadi',
        account_no='ES-003', member_name='Nurul binti Aziz', fin_amount=28000.00,
        date_appli=date(2024, 11, 1), tenure_period=48,
        surat_tawaran_date=date(2024, 10, 28),
        perjanjian_pembiayaan_date=date(2024, 10, 30),
        klausa_early_settlement=True,
        amount_rebate=1200.00,
        fee_rebate=1500.00,                               # FEE > REBATE!
    )
    db.session.add(e3)
    db.session.commit()
    process_case(e3)
    db.session.commit()
    print(f"  ES-003 Nurul (EXCESSIVE FEE): {e3.ai_conclusion}")

    # ── Set review status ─────────────────────────────────────────────────
    review.status = 'koseri_review'
    db.session.commit()

    # ── Audit log ─────────────────────────────────────────────────────────
    db.session.add(AuditLog(user_id=admin.id, action='submit',
                            detail=f'{review.reference_no}: Submitted with 10 cases',
                            ip_addr='127.0.0.1'))
    db.session.commit()

    print(f"""
{'='*60}
✅ Done! Review '{review.reference_no}' seeded with 10 cases:
{'='*60}
  TAWARUK (4):
    TWK-001  Ahmad     ✅ Clean
    TWK-002  Hassan    ❌ Tartib violation (disbursement before contract)
    TWK-003  Aminah    ⚠️  Missing wakalah + murabahah dates
    TWK-004  Razak     ❌ Same-day timing (wakalah after disbursement)

  OPSYEN / BAI'NAH (3):
    OPS-001  Siti      ✅ Clean
    OPS-002  Kamal     ❌ Sale before purchase
    OPS-003  Faridah   ⚠️  Missing perjanjian + wakil dates

  EARLY SETTLEMENT (3):
    ES-001   Zainab    ✅ Clean (Ibra' given properly)
    ES-002   Iskandar  ❌ No Ibra' clause, no rebate
    ES-003   Nurul     ❌ Fee exceeds rebate (penalty violation)

  Login:
    FedKew:  admin / admin123
    KoSERI:  koseri / koseri123

  URLs:
    FedKew:  http://127.0.0.1:5000/fedkew/review/{review.id}/data
    KoSERI:  http://127.0.0.1:5000/koseri/review/{review.id}/workbench
""")
