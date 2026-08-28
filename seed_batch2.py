"""Seed BATCH 2 — another koperasi review with 10 diverse cases.
Mix of Tawaruk, Opsyen/Bai'nah, and Early Settlement.
Scenarios: clean, reversed sequences, missing dates, same-day conflicts,
           multiple violations, partial missing data, borderline fees.
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
    # ── Ensure users exist ────────────────────────────────────────────────
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

    # ── New Review (different koperasi) ───────────────────────────────────
    review = KoperasiReview(
        koperasi_name='Koperasi Sawit Sejahtera Berhad',
        no_pendaftaran='KP-5678/2021',
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

    # T5: ✅ CLEAN — perfect sequence, all docs present
    t5 = Case(
        review_id=review.id, process_type='tawaruk', product_type='kenderaan',
        account_no='TWK-005', member_name='Hakim bin Zainal', fin_amount=38000.00,
        date_appli=date(2025, 6, 15), tenure_period=72,
        surat_tawaran_date=date(2025, 6, 12),
        perjanjian_pembiayaan_date=date(2025, 6, 14),
        wakalah_date=date(2025, 7, 1), wakalah_time='08:30',
        purchase_request_date=date(2025, 7, 1),
        murabahah_contract_date=date(2025, 7, 2),
        disbursement_date=date(2025, 7, 3), disbursement_time='14:00',
        doc_msc='MSC_Hakim_TWK005.pdf',
    )
    db.session.add(t5)
    db.session.commit()
    make_fake_pdf(os.path.join(uploads_base, str(t5.id), 'MSC_Hakim_TWK005.pdf'))
    process_case(t5)
    db.session.commit()
    print(f"  TWK-005 Hakim (CLEAN): {t5.ai_conclusion}")

    # T6: ❌ MULTIPLE VIOLATIONS — wakalah after disbursement + purchase request missing
    t6 = Case(
        review_id=review.id, process_type='tawaruk', product_type='peribadi',
        account_no='TWK-006', member_name='Rozita binti Hamid', fin_amount=12000.00,
        date_appli=date(2025, 8, 1), tenure_period=36,
        surat_tawaran_date=date(2025, 7, 28),
        perjanjian_pembiayaan_date=date(2025, 7, 30),
        wakalah_date=date(2025, 8, 20), wakalah_time='16:00',   # WAY after disbursement
        purchase_request_date=None,                               # MISSING
        murabahah_contract_date=date(2025, 8, 8),
        disbursement_date=date(2025, 8, 10), disbursement_time='10:00',
        doc_msc='MSC_Rozita_TWK006.pdf',
    )
    db.session.add(t6)
    db.session.commit()
    make_fake_pdf(os.path.join(uploads_base, str(t6.id), 'MSC_Rozita_TWK006.pdf'))
    process_case(t6)
    db.session.commit()
    print(f"  TWK-006 Rozita (MULTIPLE VIOLATIONS): {t6.ai_conclusion}")

    # T7: ❌ REVERSED ORDER — entire sequence backwards
    t7 = Case(
        review_id=review.id, process_type='tawaruk', product_type='peribadi',
        account_no='TWK-007', member_name='Firdaus bin Latif', fin_amount=22000.00,
        date_appli=date(2025, 9, 1), tenure_period=48,
        surat_tawaran_date=date(2025, 8, 28),
        perjanjian_pembiayaan_date=date(2025, 8, 30),
        wakalah_date=date(2025, 9, 15), wakalah_time='11:00',
        purchase_request_date=date(2025, 9, 12),                 # Before wakalah!
        murabahah_contract_date=date(2025, 9, 8),                # Before purchase!
        disbursement_date=date(2025, 9, 5), disbursement_time='09:00',  # First!
    )
    db.session.add(t7)
    db.session.commit()
    process_case(t7)
    db.session.commit()
    print(f"  TWK-007 Firdaus (REVERSED ORDER): {t7.ai_conclusion}")

    # T8: ⚠️ MISSING MSC DOC — all dates OK but no document uploaded
    t8 = Case(
        review_id=review.id, process_type='tawaruk', product_type='kenderaan',
        account_no='TWK-008', member_name='Norazah binti Wahab', fin_amount=50000.00,
        date_appli=date(2025, 10, 1), tenure_period=84,
        surat_tawaran_date=date(2025, 9, 28),
        perjanjian_pembiayaan_date=date(2025, 9, 30),
        wakalah_date=date(2025, 10, 5), wakalah_time='09:00',
        purchase_request_date=date(2025, 10, 5),
        murabahah_contract_date=date(2025, 10, 6),
        disbursement_date=date(2025, 10, 7), disbursement_time='14:30',
        doc_msc=None,                                             # NO DOC!
    )
    db.session.add(t8)
    db.session.commit()
    process_case(t8)
    db.session.commit()
    print(f"  TWK-008 Norazah (MISSING DOC): {t8.ai_conclusion}")

    # ══════════════════════════════════════════════════════════════════════
    #  OPSYEN / BAI'NAH CASES (3 cases)
    # ══════════════════════════════════════════════════════════════════════

    # O4: ✅ CLEAN — proper Bai'nah flow
    o4 = Case(
        review_id=review.id, process_type='opsyen', product_type='peribadi',
        account_no='OPS-004', member_name='Zulkifli bin Sulaiman', fin_amount=35000.00,
        date_appli=date(2025, 7, 10), tenure_period=60,
        surat_tawaran_date=date(2025, 7, 8),
        perjanjian_pembiayaan_date=date(2025, 7, 9),
        surat_opsyen_date=date(2025, 7, 15),
        perjanjian_pembelian_date=date(2025, 7, 16),
        wakil_pembelian_date=date(2025, 7, 16),
        perjanjian_jualan_date=date(2025, 7, 18),
        wakil_penjualan_date=date(2025, 7, 18),
        disbursement_date=date(2025, 7, 20), disbursement_time='10:00',
        doc_perjanjian_pembelian='PP_Zulkifli_OPS004.pdf',
    )
    db.session.add(o4)
    db.session.commit()
    make_fake_pdf(os.path.join(uploads_base, str(o4.id), 'PP_Zulkifli_OPS004.pdf'))
    process_case(o4)
    db.session.commit()
    print(f"  OPS-004 Zulkifli (CLEAN): {o4.ai_conclusion}")

    # O5: ❌ DISBURSEMENT BEFORE SALE — money out before sale agreement
    o5 = Case(
        review_id=review.id, process_type='opsyen', product_type='kenderaan',
        account_no='OPS-005', member_name='Mariam binti Talib', fin_amount=60000.00,
        date_appli=date(2025, 8, 5), tenure_period=84,
        surat_tawaran_date=date(2025, 8, 3),
        perjanjian_pembiayaan_date=date(2025, 8, 4),
        surat_opsyen_date=date(2025, 8, 10),
        perjanjian_pembelian_date=date(2025, 8, 12),
        wakil_pembelian_date=date(2025, 8, 12),
        perjanjian_jualan_date=date(2025, 8, 20),                # Sale AFTER disbursement
        wakil_penjualan_date=date(2025, 8, 20),
        disbursement_date=date(2025, 8, 15), disbursement_time='09:00',  # Disbursed before sale!
        doc_perjanjian_pembelian='PP_Mariam_OPS005.pdf',
    )
    db.session.add(o5)
    db.session.commit()
    make_fake_pdf(os.path.join(uploads_base, str(o5.id), 'PP_Mariam_OPS005.pdf'))
    process_case(o5)
    db.session.commit()
    print(f"  OPS-005 Mariam (DISBURSEMENT BEFORE SALE): {o5.ai_conclusion}")

    # O6: ⚠️ ALL BAI'NAH DATES MISSING — only basic info present
    o6 = Case(
        review_id=review.id, process_type='opsyen', product_type='peribadi',
        account_no='OPS-006', member_name='Shahrul bin Noor', fin_amount=18000.00,
        date_appli=date(2025, 9, 15), tenure_period=48,
        surat_tawaran_date=date(2025, 9, 12),
        perjanjian_pembiayaan_date=date(2025, 9, 14),
        surat_opsyen_date=None,                                   # MISSING
        perjanjian_pembelian_date=None,                           # MISSING
        wakil_pembelian_date=None,                                # MISSING
        perjanjian_jualan_date=None,                              # MISSING
        wakil_penjualan_date=None,                                # MISSING
        disbursement_date=date(2025, 9, 25), disbursement_time='11:30',
    )
    db.session.add(o6)
    db.session.commit()
    process_case(o6)
    db.session.commit()
    print(f"  OPS-006 Shahrul (ALL DATES MISSING): {o6.ai_conclusion}")

    # ══════════════════════════════════════════════════════════════════════
    #  EARLY SETTLEMENT CASES (3 cases)
    # ══════════════════════════════════════════════════════════════════════

    # E4: ✅ CLEAN — Ibra' properly applied, low fee
    e4 = Case(
        review_id=review.id, process_type='early_settlement', product_type='kenderaan',
        account_no='ES-004', member_name='Wan Azizah binti Ibrahim', fin_amount=48000.00,
        date_appli=date(2024, 12, 1), tenure_period=72,
        surat_tawaran_date=date(2024, 11, 28),
        perjanjian_pembiayaan_date=date(2024, 11, 30),
        klausa_early_settlement=True,
        amount_rebate=4200.00,
        fee_rebate=200.00,
    )
    db.session.add(e4)
    db.session.commit()
    process_case(e4)
    db.session.commit()
    print(f"  ES-004 Wan Azizah (CLEAN): {e4.ai_conclusion}")

    # E5: ❌ IBRA' CLAUSE EXISTS BUT ZERO REBATE — violation
    e5 = Case(
        review_id=review.id, process_type='early_settlement', product_type='peribadi',
        account_no='ES-005', member_name='Bakri bin Jaafar', fin_amount=32000.00,
        date_appli=date(2025, 2, 1), tenure_period=60,
        surat_tawaran_date=date(2025, 1, 28),
        perjanjian_pembiayaan_date=date(2025, 1, 30),
        klausa_early_settlement=True,                             # Has clause
        amount_rebate=0,                                          # BUT zero rebate!
        fee_rebate=800.00,
    )
    db.session.add(e5)
    db.session.commit()
    process_case(e5)
    db.session.commit()
    print(f"  ES-005 Bakri (CLAUSE BUT NO REBATE): {e5.ai_conclusion}")

    # E6: ❌ FEE EQUALS REBATE — penalty effectively cancels ibra'
    e6 = Case(
        review_id=review.id, process_type='early_settlement', product_type='peribadi',
        account_no='ES-006', member_name='Salina binti Ahmad', fin_amount=26000.00,
        date_appli=date(2025, 4, 1), tenure_period=48,
        surat_tawaran_date=date(2025, 3, 28),
        perjanjian_pembiayaan_date=date(2025, 3, 30),
        klausa_early_settlement=True,
        amount_rebate=1800.00,
        fee_rebate=1800.00,                                       # FEE == REBATE!
    )
    db.session.add(e6)
    db.session.commit()
    process_case(e6)
    db.session.commit()
    print(f"  ES-006 Salina (FEE EQUALS REBATE): {e6.ai_conclusion}")

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
    TWK-005  Hakim     ✅ Clean — perfect sequence & docs
    TWK-006  Rozita    ❌ Wakalah after disbursement + missing purchase request
    TWK-007  Firdaus   ❌ Entire sequence reversed (disbursement first)
    TWK-008  Norazah   ⚠️  All dates OK but MSC document not uploaded

  OPSYEN / BAI'NAH (3):
    OPS-004  Zulkifli  ✅ Clean — proper Bai'nah flow
    OPS-005  Mariam    ❌ Disbursement before sale agreement
    OPS-006  Shahrul   ⚠️  All Bai'nah dates missing (only basic info)

  EARLY SETTLEMENT (3):
    ES-004   Wan Azizah ✅ Clean — proper Ibra', low fee
    ES-005   Bakri      ❌ Has Ibra' clause but zero rebate given
    ES-006   Salina     ❌ Fee equals rebate (penalty cancels ibra')

  Login:
    FedKew:  admin / admin123
    KoSERI:  koseri / koseri123

  URLs:
    FedKew:  http://127.0.0.1:5000/fedkew/review/{review.id}/data
    KoSERI:  http://127.0.0.1:5000/koseri/review/{review.id}/workbench
""")
