"""
Report Generator — PDF Service (SSPS v2.0)
═══════════════════════════════════════════
Institutional-grade Shariah Compliance Report.
System-generated — no individual signatures.
KoSERI identity FULLY MASKED.
"""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, Image, KeepTogether,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Rect, String
from datetime import datetime, timezone
from collections import Counter, defaultdict
import os
import json

# ── Colour Palette ────────────────────────────────────────────────────────────
NAVY        = colors.HexColor('#0a1628')
NAVY_LIGHT  = colors.HexColor('#0f1d32')
GOLD        = colors.HexColor('#c9952e')
DARK_GOLD   = colors.HexColor('#a67c24')
GREEN       = colors.HexColor('#16a34a')
GREEN_BG    = colors.HexColor('#f0fdf4')
RED         = colors.HexColor('#dc2626')
RED_BG      = colors.HexColor('#fef2f2')
AMBER       = colors.HexColor('#d97706')
AMBER_BG    = colors.HexColor('#fffbeb')
LIGHT_GRAY  = colors.HexColor('#f1f5f9')
MID_GRAY    = colors.HexColor('#e2e8f0')
WHITE       = colors.white
GRAY_TEXT   = colors.HexColor('#64748b')
DARK_TEXT   = colors.HexColor('#1e293b')

PAGE_W, PAGE_H = A4
MARGIN_L = 20 * mm
MARGIN_R = 20 * mm
MARGIN_T = 28 * mm
MARGIN_B = 22 * mm
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R

# Logo path
LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                         'static', 'img', 'logo.png')


# ═════════════════════════════════════════════════════════════════════════════
#  STYLES
# ═════════════════════════════════════════════════════════════════════════════
def _styles():
    """Custom paragraph styles."""
    ss = getSampleStyleSheet()

    ss.add(ParagraphStyle('CoverTitle', parent=ss['Title'],
                          fontName='Helvetica-Bold', fontSize=20,
                          textColor=WHITE, alignment=TA_CENTER,
                          spaceAfter=2 * mm, leading=24))
    ss.add(ParagraphStyle('CoverSub', parent=ss['Normal'],
                          fontName='Helvetica', fontSize=10,
                          textColor=GOLD, alignment=TA_CENTER))
    ss.add(ParagraphStyle('SectionHead', parent=ss['Heading2'],
                          fontName='Helvetica-Bold', fontSize=12,
                          textColor=WHITE, spaceBefore=0, spaceAfter=0,
                          leading=16))
    ss.add(ParagraphStyle('SubHead', parent=ss['Heading3'],
                          fontName='Helvetica-Bold', fontSize=10,
                          textColor=DARK_GOLD, spaceBefore=4 * mm,
                          spaceAfter=2 * mm))
    ss.add(ParagraphStyle('Body', parent=ss['Normal'],
                          fontName='Helvetica', fontSize=9,
                          textColor=DARK_TEXT, leading=14))
    ss.add(ParagraphStyle('BodySmall', parent=ss['Normal'],
                          fontName='Helvetica', fontSize=8,
                          textColor=GRAY_TEXT, leading=12))
    ss.add(ParagraphStyle('BodyCenter', parent=ss['Normal'],
                          fontName='Helvetica', fontSize=9,
                          textColor=DARK_TEXT, alignment=TA_CENTER))
    ss.add(ParagraphStyle('KPINumber', parent=ss['Normal'],
                          fontName='Helvetica-Bold', fontSize=26,
                          textColor=NAVY, alignment=TA_CENTER, leading=30))
    ss.add(ParagraphStyle('KPILabel', parent=ss['Normal'],
                          fontName='Helvetica', fontSize=8,
                          textColor=GRAY_TEXT, alignment=TA_CENTER))
    ss.add(ParagraphStyle('TOCEntry', parent=ss['Normal'],
                          fontName='Helvetica', fontSize=10,
                          textColor=DARK_TEXT, leading=18))
    ss.add(ParagraphStyle('TOCHeading', parent=ss['Normal'],
                          fontName='Helvetica-Bold', fontSize=14,
                          textColor=NAVY, spaceAfter=6 * mm))
    ss.add(ParagraphStyle('CenterBold', parent=ss['Normal'],
                          fontName='Helvetica-Bold', fontSize=10,
                          alignment=TA_CENTER, textColor=NAVY))
    ss.add(ParagraphStyle('VerdictGreen', parent=ss['Normal'],
                          fontName='Helvetica-Bold', fontSize=14,
                          textColor=GREEN, alignment=TA_CENTER))
    ss.add(ParagraphStyle('VerdictRed', parent=ss['Normal'],
                          fontName='Helvetica-Bold', fontSize=14,
                          textColor=RED, alignment=TA_CENTER))
    return ss


# ═════════════════════════════════════════════════════════════════════════════
#  HELPER BUILDERS
# ═════════════════════════════════════════════════════════════════════════════

def _section_header(title):
    """Navy-band section header with gold left accent."""
    t = Table([[Paragraph(title, _cached_styles['SectionHead'])]],
              colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), NAVY),
        ('LEFTPADDING', (0, 0), (-1, -1), 4 * mm),
        ('TOPPADDING', (0, 0), (-1, -1), 3 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3 * mm),
        ('LINEAFTER', (0, 0), (0, -1), 0, NAVY),
        ('LINEBEFORE', (0, 0), (0, -1), 3, GOLD),
    ]))
    return t


def _severity_color(sev):
    if sev == 'HIGH':
        return RED, RED_BG
    elif sev == 'MEDIUM':
        return AMBER, AMBER_BG
    return GRAY_TEXT, LIGHT_GRAY


def _decision_display(case):
    d = case.koseri_decision or case.ai_conclusion or 'N/A'
    mapping = {
        'compliant': 'PATUH', 'non_compliant': 'TIDAK PATUH',
        'SHARIAH_COMPLIANT': 'PATUH', 'NON_SHARIAH_COMPLIANT': 'TIDAK PATUH',
        'NEEDS_REVIEW': 'PERLU SEMAKAN',
    }
    return mapping.get(d, d)


def _is_compliant(case):
    d = _decision_display(case)
    return d == 'PATUH'


def _opinion_display(opinion):
    return {
        'PATUH_SYARIAH': 'PATUH SYARIAH',
        'PATUH_SECARA_AMNYA': 'PATUH SYARIAH SECARA AMNYA',
        'TIDAK_PATUH_SYARIAH': 'TIDAK PATUH SYARIAH',
        'NO_CASES': 'TIADA KES',
    }.get(opinion, opinion)


# ═════════════════════════════════════════════════════════════════════════════
#  PAGE HEADER / FOOTER CALLBACKS
# ═════════════════════════════════════════════════════════════════════════════

_pdf_meta = {}   # shared state for ref_no


def _first_page(canvas, doc):
    """Cover page — no header/footer."""
    pass


def _later_pages(canvas, doc):
    """Header + Footer on pages 2+."""
    canvas.saveState()
    ref = _pdf_meta.get('ref', '')

    # ── Header ──
    y_h = PAGE_H - 16 * mm
    # Logo
    if os.path.exists(LOGO_PATH):
        canvas.drawImage(LOGO_PATH, MARGIN_L, y_h - 3 * mm,
                         width=12 * mm, height=12 * mm,
                         preserveAspectRatio=True, mask='auto')
    # Text
    canvas.setFont('Helvetica-Bold', 8)
    canvas.setFillColor(NAVY)
    canvas.drawString(MARGIN_L + 14 * mm, y_h + 1 * mm, 'SSPS')
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(GRAY_TEXT)
    canvas.drawString(MARGIN_L + 14 * mm, y_h - 3 * mm, 'Federasi Kewangan')
    # Ref right-aligned
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(GRAY_TEXT)
    canvas.drawRightString(PAGE_W - MARGIN_R, y_h + 1 * mm, ref)
    # Gold line
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN_L, y_h - 6 * mm, PAGE_W - MARGIN_R, y_h - 6 * mm)

    # ── Footer ──
    y_f = 12 * mm
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(0.3)
    canvas.line(MARGIN_L, y_f + 4 * mm, PAGE_W - MARGIN_R, y_f + 4 * mm)
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(GRAY_TEXT)
    canvas.drawString(MARGIN_L, y_f, 'SULIT — Untuk Kegunaan Dalaman Sahaja')
    canvas.drawRightString(PAGE_W - MARGIN_R, y_f,
                           f'Muka {doc.page} daripada {{TOTAL}}')

    canvas.restoreState()


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN GENERATOR
# ═════════════════════════════════════════════════════════════════════════════

# Cache styles at module level for helpers
_cached_styles = None


def generate_report_pdf(review):
    """Generate full institutional Shariah compliance PDF report."""
    global _cached_styles
    _cached_styles = _styles()
    styles = _cached_styles

    # Output
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                               'reports')
    os.makedirs(reports_dir, exist_ok=True)
    filepath = os.path.join(reports_dir, f'{review.reference_no}_Laporan.pdf')

    _pdf_meta['ref'] = review.reference_no

    # ── Build document with page templates ──
    frame = Frame(MARGIN_L, MARGIN_B,
                  CONTENT_W, PAGE_H - MARGIN_T - MARGIN_B,
                  id='main')

    doc = BaseDocTemplate(filepath, pagesize=A4)
    doc.addPageTemplates([
        PageTemplate(id='cover', frames=[
            Frame(MARGIN_L, MARGIN_B, CONTENT_W,
                  PAGE_H - MARGIN_B - 15 * mm, id='cover_frame')
        ], onPage=_first_page),
        PageTemplate(id='content', frames=[frame], onPage=_later_pages),
    ])

    story = []

    # ── Pre-compute analytics ──
    cases = review.cases
    total = review.case_count
    compliant = review.compliant_count
    nc = review.non_compliant_count
    opinion = review.overall_opinion
    opinion_str = _opinion_display(opinion)

    all_findings = []
    type_stats = defaultdict(lambda: {'total': 0, 'patuh': 0, 'tidak': 0,
                                       'amount': 0.0})
    total_amount = 0.0
    patuh_amount = 0.0
    tidak_amount = 0.0

    for c in cases:
        fs = c.findings
        all_findings.extend(fs)
        pt = (c.process_type or 'lain').replace('_', ' ').title()
        is_ok = _is_compliant(c)
        amt = c.fin_amount or 0
        type_stats[pt]['total'] += 1
        type_stats[pt]['amount'] += amt
        total_amount += amt
        if is_ok:
            type_stats[pt]['patuh'] += 1
            patuh_amount += amt
        else:
            type_stats[pt]['tidak'] += 1
            tidak_amount += amt

    high_total = sum(1 for f in all_findings if f.get('severity') == 'HIGH')
    med_total = sum(1 for f in all_findings if f.get('severity') == 'MEDIUM')
    total_findings = len(all_findings)

    # Top non-compliant rules
    rule_counter = Counter()
    rule_names = {}
    rule_sevs = {}
    for f in all_findings:
        rid = f.get('rule_id', '?')
        rule_counter[rid] += 1
        rule_names[rid] = f.get('rule_name', rid)
        rule_sevs[rid] = f.get('severity', 'MEDIUM')
    top_rules = rule_counter.most_common(10)

    now = datetime.now(timezone.utc)
    now_str = now.strftime('%d/%m/%Y %H:%M UTC')
    date_str = review.review_date.strftime('%d/%m/%Y') if review.review_date else '—'

    # ═══════════════════════════════════════════════════════════════════════
    #  PAGE 1: COVER
    # ═══════════════════════════════════════════════════════════════════════

    # Navy header band (using a table as background)
    cover_top = []

    # Spacer to push into band area
    cover_top.append(Spacer(1, 10 * mm))

    # Logo
    if os.path.exists(LOGO_PATH):
        logo = Image(LOGO_PATH, width=32 * mm, height=32 * mm)
        logo.hAlign = 'CENTER'
        cover_top.append(logo)
        cover_top.append(Spacer(1, 4 * mm))

    # Title in navy band
    navy_band_data = [
        [Paragraph('LAPORAN SEMAKAN<br/>PEMATUHAN SYARIAH',
                   styles['CoverTitle'])],
        [Paragraph('Sistem Semakan Pematuhan Syariah (SSPS)',
                   styles['CoverSub'])],
    ]
    navy_band = Table(navy_band_data, colWidths=[CONTENT_W])
    navy_band.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), NAVY),
        ('TOPPADDING', (0, 0), (-1, 0), 5 * mm),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 5 * mm),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(Spacer(1, 15 * mm))
    if os.path.exists(LOGO_PATH):
        logo = Image(LOGO_PATH, width=32 * mm, height=32 * mm)
        logo.hAlign = 'CENTER'
        story.append(logo)
        story.append(Spacer(1, 6 * mm))
    story.append(navy_band)
    story.append(Spacer(1, 6 * mm))

    # Gold rule
    story.append(HRFlowable(width='100%', thickness=1.5, color=GOLD))
    story.append(Spacer(1, 8 * mm))

    # Reference box
    ref_data = [
        [Paragraph('<b>No. Rujukan:</b>', styles['Body']),
         Paragraph(review.reference_no, styles['Body'])],
        [Paragraph('<b>Koperasi:</b>', styles['Body']),
         Paragraph(review.koperasi_name, styles['Body'])],
        [Paragraph('<b>No. Pendaftaran:</b>', styles['Body']),
         Paragraph(review.no_pendaftaran, styles['Body'])],
        [Paragraph('<b>Tarikh Semakan:</b>', styles['Body']),
         Paragraph(date_str, styles['Body'])],
        [Paragraph('<b>Tarikh Laporan:</b>', styles['Body']),
         Paragraph(now_str, styles['Body'])],
    ]
    ref_table = Table(ref_data, colWidths=[45 * mm, CONTENT_W - 45 * mm])
    ref_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5 * mm),
        ('LEFTPADDING', (0, 0), (-1, -1), 4 * mm),
        ('GRID', (0, 0), (-1, -1), 0.3, MID_GRAY),
        ('ROUNDEDCORNERS', [3, 3, 3, 3]),
    ]))
    story.append(ref_table)
    story.append(Spacer(1, 10 * mm))

    # Verdict badge
    is_patuh = opinion in ('PATUH_SYARIAH', 'PATUH_SECARA_AMNYA')
    verdict_bg = GREEN_BG if is_patuh else RED_BG
    verdict_border = GREEN if is_patuh else RED
    verdict_style = styles['VerdictGreen'] if is_patuh else styles['VerdictRed']

    verdict_data = [
        [Paragraph('PENDAPAT KESELURUHAN', styles['KPILabel'])],
        [Paragraph(opinion_str, verdict_style)],
    ]
    verdict_table = Table(verdict_data, colWidths=[CONTENT_W * 0.6])
    verdict_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), verdict_bg),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, 0), 3 * mm),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 4 * mm),
        ('BOX', (0, 0), (-1, -1), 1.5, verdict_border),
        ('ROUNDEDCORNERS', [4, 4, 4, 4]),
    ]))
    verdict_table.hAlign = 'CENTER'
    story.append(verdict_table)

    # Switch to content template for page 2+
    story.append(PageBreak())
    story.append(Spacer(0, 0))  # force template switch trigger

    # ═══════════════════════════════════════════════════════════════════════
    #  PAGE 2: TABLE OF CONTENTS
    # ═══════════════════════════════════════════════════════════════════════

    story.append(Paragraph('KANDUNGAN', styles['TOCHeading']))
    story.append(HRFlowable(width='100%', thickness=0.5, color=GOLD))
    story.append(Spacer(1, 4 * mm))

    toc_entries = [
        ('1.', 'Ringkasan Eksekutif'),
        ('2.', 'Daftar Kes Keseluruhan'),
        ('3.', 'Penemuan Terperinci'),
    ]
    # Add sub-entries for each case
    for i, c in enumerate(cases, 1):
        name = c.member_name or 'Tanpa Nama'
        toc_entries.append(
            (f'   3.{i}', f'{c.account_no} — {name}')
        )
    toc_entries.append(('4.', 'Analisis Pematuhan'))
    toc_entries.append(('5.', 'Pengesahan Laporan'))

    toc_data = []
    for num, title in toc_entries:
        is_sub = num.startswith('   ')
        indent = '      ' if is_sub else ''
        dot_style = ParagraphStyle('toc_item', parent=styles['Body'],
                                   fontName='Helvetica' if is_sub else 'Helvetica-Bold',
                                   fontSize=9 if is_sub else 10,
                                   textColor=GRAY_TEXT if is_sub else DARK_TEXT)
        toc_data.append([
            Paragraph(f'{indent}{num}', dot_style),
            Paragraph(title, dot_style),
        ])

    toc_table = Table(toc_data, colWidths=[20 * mm, CONTENT_W - 20 * mm])
    toc_table.setStyle(TableStyle([
        ('TOPPADDING', (0, 0), (-1, -1), 1.5 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5 * mm),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(toc_table)
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    #  SECTION 1: EXECUTIVE SUMMARY
    # ═══════════════════════════════════════════════════════════════════════

    story.append(_section_header('1.  RINGKASAN EKSEKUTIF'))
    story.append(Spacer(1, 5 * mm))

    # KPI Row — 3 boxes
    kpi_cells = [
        [Paragraph(str(total), styles['KPINumber']),
         Paragraph(str(compliant), ParagraphStyle('kpi_g', parent=styles['KPINumber'],
                                                   textColor=GREEN)),
         Paragraph(str(nc), ParagraphStyle('kpi_r', parent=styles['KPINumber'],
                                            textColor=RED))],
        [Paragraph('Jumlah Kes', styles['KPILabel']),
         Paragraph('Kes Patuh', styles['KPILabel']),
         Paragraph('Kes Tidak Patuh', styles['KPILabel'])],
    ]
    kpi_w = CONTENT_W / 3
    kpi_table = Table(kpi_cells, colWidths=[kpi_w, kpi_w, kpi_w])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GRAY),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, 0), 5 * mm),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 4 * mm),
        ('BOX', (0, 0), (-1, -1), 0.5, MID_GRAY),
        ('LINEBEFORE', (1, 0), (1, -1), 0.5, MID_GRAY),
        ('LINEBEFORE', (2, 0), (2, -1), 0.5, MID_GRAY),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 6 * mm))

    # ── Analytics: By Process Type ──
    story.append(Paragraph('Pecahan Mengikut Jenis Proses', styles['SubHead']))
    pt_header = ['Jenis Proses', 'Jumlah', 'Patuh', 'Tidak Patuh',
                 'Jumlah Amaun (RM)']
    pt_data = [pt_header]
    for pt_name in sorted(type_stats.keys()):
        s = type_stats[pt_name]
        pt_data.append([
            pt_name, str(s['total']), str(s['patuh']), str(s['tidak']),
            f"{s['amount']:,.2f}",
        ])
    pt_data.append([
        Paragraph('<b>JUMLAH</b>', styles['BodySmall']),
        Paragraph(f'<b>{total}</b>', styles['BodySmall']),
        Paragraph(f'<b>{compliant}</b>', styles['BodySmall']),
        Paragraph(f'<b>{nc}</b>', styles['BodySmall']),
        Paragraph(f'<b>{total_amount:,.2f}</b>', styles['BodySmall']),
    ])
    cw_pt = [CONTENT_W * 0.28, CONTENT_W * 0.13, CONTENT_W * 0.13,
             CONTENT_W * 0.18, CONTENT_W * 0.28]
    pt_table = Table(pt_data, colWidths=cw_pt)
    pt_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, -1), (-1, -1), LIGHT_GRAY),
        ('GRID', (0, 0), (-1, -1), 0.5, MID_GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 2 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2 * mm),
        ('LEFTPADDING', (0, 0), (-1, -1), 2 * mm),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (-1, 1), (-1, -1), 'RIGHT'),
        # Alternate row bg
        *[('BACKGROUND', (0, i), (-1, i), WHITE if i % 2 == 1 else
           colors.HexColor('#f8fafc'))
          for i in range(1, len(pt_data) - 1)],
    ]))
    story.append(pt_table)
    story.append(Spacer(1, 5 * mm))

    # ── Severity Distribution ──
    story.append(Paragraph('Taburan Tahap Risiko Penemuan', styles['SubHead']))
    sev_data = [['Tahap', 'Bilangan', '% Penemuan']]
    for sev_name, sev_count, sev_col in [
        ('HIGH', high_total, RED), ('MEDIUM', med_total, AMBER),
    ]:
        pct = f'{sev_count / total_findings * 100:.0f}%' if total_findings else '0%'
        sev_data.append([sev_name, str(sev_count), pct])
    sev_data.append(['JUMLAH', str(total_findings), '100%'])

    sev_table = Table(sev_data, colWidths=[CONTENT_W * 0.3, CONTENT_W * 0.35,
                                            CONTENT_W * 0.35])
    sev_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, MID_GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 2 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2 * mm),
        ('LEFTPADDING', (0, 0), (-1, -1), 3 * mm),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('BACKGROUND', (0, 1), (-1, 1), RED_BG),
        ('TEXTCOLOR', (0, 1), (0, 1), RED),
        ('FONTNAME', (0, 1), (0, 1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 2), (-1, 2), AMBER_BG),
        ('TEXTCOLOR', (0, 2), (0, 2), AMBER),
        ('FONTNAME', (0, 2), (0, 2), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), LIGHT_GRAY),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    story.append(sev_table)
    story.append(Spacer(1, 5 * mm))

    # ── Financial Impact ──
    story.append(Paragraph('Impak Kewangan', styles['SubHead']))
    fin_data = [
        ['Jumlah Amaun Disemak', f'RM {total_amount:,.2f}'],
        ['Amaun Kes Patuh', f'RM {patuh_amount:,.2f}'],
        ['Amaun Kes Tidak Patuh', f'RM {tidak_amount:,.2f}'],
    ]
    fin_table = Table(fin_data, colWidths=[CONTENT_W * 0.55, CONTENT_W * 0.45])
    fin_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), GRAY_TEXT),
        ('TEXTCOLOR', (1, 0), (1, 0), DARK_TEXT),
        ('TEXTCOLOR', (1, 1), (1, 1), GREEN),
        ('TEXTCOLOR', (1, 2), (1, 2), RED),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5 * mm),
        ('LEFTPADDING', (0, 0), (-1, -1), 3 * mm),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3 * mm),
        ('GRID', (0, 0), (-1, -1), 0.3, MID_GRAY),
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GRAY),
    ]))
    story.append(fin_table)
    story.append(Spacer(1, 5 * mm))

    # FedKew summary
    if review.fedkew_summary:
        story.append(Paragraph('Ulasan Federasi Kewangan:', styles['SubHead']))
        q_data = [[Paragraph(review.fedkew_summary, styles['Body'])]]
        q_table = Table(q_data, colWidths=[CONTENT_W - 6 * mm])
        q_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fefce8')),
            ('LINEBEFORE', (0, 0), (0, -1), 3, GOLD),
            ('TOPPADDING', (0, 0), (-1, -1), 3 * mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3 * mm),
            ('LEFTPADDING', (0, 0), (-1, -1), 4 * mm),
        ]))
        story.append(q_table)

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    #  SECTION 2: CASE REGISTER
    # ═══════════════════════════════════════════════════════════════════════

    story.append(_section_header('2.  DAFTAR KES KESELURUHAN'))
    story.append(Spacer(1, 4 * mm))

    reg_header = ['#', 'Akaun', 'Nama Anggota', 'Jenis', 'Amaun (RM)',
                  'Penemuan', 'Keputusan']
    reg_data = [reg_header]

    for i, c in enumerate(cases, 1):
        dec = _decision_display(c)
        ok = _is_compliant(c)
        # Findings summary: "2H 1M" or "—"
        h = c.high_count
        m = c.medium_count
        f_summary = []
        if h:
            f_summary.append(f'{h}H')
        if m:
            f_summary.append(f'{m}M')
        f_str = ' '.join(f_summary) if f_summary else '—'

        reg_data.append([
            str(i),
            c.account_no,
            Paragraph(c.member_name or 'Tanpa Nama', styles['BodySmall']),
            (c.process_type or '—').replace('_', ' ').title()[:10],
            f'{c.fin_amount:,.2f}' if c.fin_amount else '—',
            f_str,
            dec,
        ])

    # Totals row
    reg_data.append([
        '', '',
        Paragraph(f'<b>JUMLAH: {total} kes</b>', styles['BodySmall']),
        '', f'{total_amount:,.2f}',
        f'{total_findings} penemuan', '',
    ])

    reg_cw = [8 * mm, 22 * mm, CONTENT_W - 130 * mm, 20 * mm,
              25 * mm, 20 * mm, 20 * mm]
    reg_table = Table(reg_data, colWidths=reg_cw, repeatRows=1)
    reg_table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 7),
        # Body
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        # Totals row
        ('BACKGROUND', (0, -1), (-1, -1), LIGHT_GRAY),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        # Grid
        ('GRID', (0, 0), (-1, -1), 0.3, MID_GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 2 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2 * mm),
        ('LEFTPADDING', (0, 0), (-1, -1), 1.5 * mm),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (4, 0), (4, -1), 'RIGHT'),
        ('ALIGN', (5, 0), (5, -1), 'CENTER'),
        ('ALIGN', (6, 0), (6, -1), 'CENTER'),
        # Alternate rows
        *[('BACKGROUND', (0, i), (-1, i),
           WHITE if i % 2 == 1 else colors.HexColor('#f8fafc'))
          for i in range(1, len(reg_data) - 1)],
    ]))

    # Color-code keputusan column in each data row
    for i in range(1, len(reg_data) - 1):
        c_case = cases[i - 1]
        ok = _is_compliant(c_case)
        reg_table.setStyle(TableStyle([
            ('TEXTCOLOR', (6, i), (6, i), GREEN if ok else RED),
            ('FONTNAME', (6, i), (6, i), 'Helvetica-Bold'),
        ]))

    story.append(reg_table)
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    #  SECTION 3: DETAILED FINDINGS
    # ═══════════════════════════════════════════════════════════════════════

    story.append(_section_header('3.  PENEMUAN TERPERINCI'))
    story.append(Spacer(1, 4 * mm))

    for i, case in enumerate(cases, 1):
        dec = _decision_display(case)
        ok = _is_compliant(case)
        pt = (case.process_type or '—').replace('_', ' ').title()
        prod = (case.product_type or '—').replace('_', ' ').title()
        amt_str = f'RM {case.fin_amount:,.2f}' if case.fin_amount else '—'

        # Case header bar
        header_data = [[
            Paragraph(
                f'<b>3.{i}  {case.account_no}</b> — '
                f'{case.member_name or "Tanpa Nama"}',
                ParagraphStyle('ch', parent=styles['Body'],
                               textColor=WHITE, fontSize=9,
                               fontName='Helvetica-Bold')),
            Paragraph(
                f'{pt} / {prod}  ·  {amt_str}',
                ParagraphStyle('cm', parent=styles['Body'],
                               textColor=colors.HexColor('#94a3b8'),
                               fontSize=8, alignment=TA_RIGHT)),
        ]]
        ch_table = Table(header_data,
                         colWidths=[CONTENT_W * 0.6, CONTENT_W * 0.4])
        ch_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NAVY),
            ('TOPPADDING', (0, 0), (-1, -1), 3 * mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3 * mm),
            ('LEFTPADDING', (0, 0), (-1, -1), 4 * mm),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4 * mm),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        # Decision badge
        badge_color = GREEN if ok else RED
        badge_bg = GREEN_BG if ok else RED_BG
        badge_data = [[
            Paragraph(f'Keputusan: <b>{dec}</b>',
                      ParagraphStyle('badge', parent=styles['Body'],
                                     textColor=badge_color, fontSize=9,
                                     fontName='Helvetica-Bold'))
        ]]
        badge_table = Table(badge_data, colWidths=[CONTENT_W])
        badge_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), badge_bg),
            ('TOPPADDING', (0, 0), (-1, -1), 2 * mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2 * mm),
            ('LEFTPADDING', (0, 0), (-1, -1), 4 * mm),
            ('BOX', (0, 0), (-1, -1), 0.5, badge_color),
        ]))

        findings = case.findings
        case_elements = [ch_table, badge_table]

        if findings:
            # Findings table: Rule | Details (stacked) | Severity
            f_rows = [['Peraturan', 'Butiran Penemuan', 'Tahap']]
            for f in findings:
                sev = f.get('severity', 'MEDIUM')
                detail = (
                    f'<b>Penemuan:</b> {f.get("finding", "—")}<br/>'
                    f'<b>Kesan:</b> {f.get("effect", "—")}<br/>'
                    f'<b>Pembetulan:</b> {f.get("rectification", "—")}<br/>'
                    f'<b>Rujukan:</b> {f.get("source", "—")}'
                )
                f_rows.append([
                    Paragraph(f'<b>{f.get("rule_id", "—")}</b><br/>'
                              f'<font size="7">{f.get("rule_name", "")}</font>',
                              styles['BodySmall']),
                    Paragraph(detail, styles['BodySmall']),
                    Paragraph(f'<b>{sev}</b>',
                              ParagraphStyle('sev', parent=styles['BodySmall'],
                                             alignment=TA_CENTER,
                                             textColor=RED if sev == 'HIGH' else AMBER)),
                ])

            f_cw = [25 * mm, CONTENT_W - 50 * mm, 25 * mm]
            f_table = Table(f_rows, colWidths=f_cw)

            f_styles = [
                ('BACKGROUND', (0, 0), (-1, 0), NAVY),
                ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 7),
                ('GRID', (0, 0), (-1, -1), 0.3, MID_GRAY),
                ('TOPPADDING', (0, 0), (-1, -1), 2 * mm),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2 * mm),
                ('LEFTPADDING', (0, 0), (-1, -1), 2 * mm),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ]
            # Severity row bg
            for fi in range(1, len(f_rows)):
                sev = findings[fi - 1].get('severity', 'MEDIUM')
                _, bg = _severity_color(sev)
                f_styles.append(('BACKGROUND', (2, fi), (2, fi), bg))
                # Left border accent
                sc, _ = _severity_color(sev)
                f_styles.append(('LINEBEFORE', (0, fi), (0, fi), 2.5, sc))

            f_table.setStyle(TableStyle(f_styles))
            case_elements.append(Spacer(1, 2 * mm))
            case_elements.append(f_table)
        else:
            no_f = Paragraph(
                '<i>Tiada penemuan ketidakpatuhan dikesan.</i>',
                ParagraphStyle('nof', parent=styles['Body'],
                               textColor=GREEN))
            case_elements.append(Spacer(1, 2 * mm))
            case_elements.append(no_f)

        # Gold separator
        case_elements.append(Spacer(1, 3 * mm))
        case_elements.append(HRFlowable(width='100%', thickness=0.3,
                                        color=GOLD))
        case_elements.append(Spacer(1, 3 * mm))

        story.extend(case_elements)

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    #  SECTION 4: COMPLIANCE ANALYTICS
    # ═══════════════════════════════════════════════════════════════════════

    story.append(_section_header('4.  ANALISIS PEMATUHAN'))
    story.append(Spacer(1, 5 * mm))

    if top_rules:
        story.append(Paragraph('Peraturan Paling Kerap Dilanggar',
                               styles['SubHead']))
        tr_data = [['Peraturan', 'Nama Peraturan', 'Tahap', 'Kekerapan']]
        for rid, cnt in top_rules:
            sev = rule_sevs.get(rid, 'MEDIUM')
            tr_data.append([
                rid,
                Paragraph(rule_names.get(rid, rid), styles['BodySmall']),
                sev,
                str(cnt),
            ])
        tr_cw = [18 * mm, CONTENT_W - 66 * mm, 22 * mm, 22 * mm]
        tr_table = Table(tr_data, colWidths=tr_cw)
        tr_styles = [
            ('BACKGROUND', (0, 0), (-1, 0), NAVY),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.3, MID_GRAY),
            ('TOPPADDING', (0, 0), (-1, -1), 2 * mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2 * mm),
            ('LEFTPADDING', (0, 0), (-1, -1), 2 * mm),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('ALIGN', (3, 0), (3, -1), 'CENTER'),
        ]
        for ri in range(1, len(tr_data)):
            sev = rule_sevs.get(top_rules[ri - 1][0], 'MEDIUM')
            sc, bg = _severity_color(sev)
            tr_styles.append(('TEXTCOLOR', (2, ri), (2, ri), sc))
            tr_styles.append(('FONTNAME', (2, ri), (2, ri), 'Helvetica-Bold'))
            tr_styles.append(('BACKGROUND', (2, ri), (2, ri), bg))
            # Alternate rows
            if ri % 2 == 0:
                tr_styles.append(('BACKGROUND', (0, ri), (1, ri),
                                  colors.HexColor('#f8fafc')))
                tr_styles.append(('BACKGROUND', (3, ri), (3, ri),
                                  colors.HexColor('#f8fafc')))

        tr_table.setStyle(TableStyle(tr_styles))
        story.append(tr_table)
    else:
        story.append(Paragraph(
            'Tiada pelanggaran dikesan — semua kes patuh sepenuhnya.',
            styles['Body']))

    story.append(Spacer(1, 8 * mm))

    # Compliance rate summary
    rate = (compliant / total * 100) if total else 0
    story.append(Paragraph('Kadar Pematuhan Keseluruhan', styles['SubHead']))
    rate_data = [[
        Paragraph(f'<b>{rate:.0f}%</b>',
                  ParagraphStyle('rate', parent=styles['KPINumber'],
                                 fontSize=32,
                                 textColor=GREEN if rate >= 80 else (
                                     AMBER if rate >= 50 else RED))),
    ], [
        Paragraph(f'{compliant} daripada {total} kes patuh Syariah',
                  styles['BodyCenter']),
    ]]
    rate_table = Table(rate_data, colWidths=[CONTENT_W * 0.5])
    rate_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GRAY),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, 0), 5 * mm),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 4 * mm),
        ('BOX', (0, 0), (-1, -1), 0.5, MID_GRAY),
    ]))
    rate_table.hAlign = 'CENTER'
    story.append(rate_table)

    story.append(Spacer(1, 10 * mm))

    # ═══════════════════════════════════════════════════════════════════════
    #  SECTION 5: SIGN-OFF (No signatory — system-generated)
    # ═══════════════════════════════════════════════════════════════════════

    story.append(_section_header('5.  PENGESAHAN LAPORAN'))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(
        'Laporan ini dijana secara automatik oleh Sistem Semakan Pematuhan '
        'Syariah (SSPS) Federasi Kewangan. Laporan ini merupakan dokumen '
        'rasmi yang dijana oleh sistem dan <b>tidak memerlukan tandatangan '
        'manual</b>.',
        styles['Body']))
    story.append(Spacer(1, 5 * mm))

    so_data = [
        ['No. Rujukan Laporan:', review.reference_no],
        ['Dijana Oleh:', 'SSPS — Federasi Kewangan'],
        ['Tarikh & Masa:', now.strftime('%d/%m/%Y %H:%M:%S UTC')],
        ['Jumlah Muka Surat:', 'Dijana secara automatik'],
    ]
    so_table = Table(so_data, colWidths=[45 * mm, CONTENT_W - 45 * mm])
    so_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), DARK_GOLD),
        ('TEXTCOLOR', (1, 0), (1, -1), DARK_TEXT),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5 * mm),
        ('LEFTPADDING', (0, 0), (-1, -1), 4 * mm),
        ('BOX', (0, 0), (-1, -1), 1, GOLD),
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GRAY),
        ('GRID', (0, 0), (-1, -1), 0.3, MID_GRAY),
    ]))
    story.append(so_table)

    story.append(Spacer(1, 10 * mm))
    story.append(HRFlowable(width='40%', thickness=0.5, color=GOLD))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph('— TAMAT LAPORAN —', styles['CenterBold']))

    # ═══════════════════════════════════════════════════════════════════════
    #  BUILD PDF (two-pass for page numbers)
    # ═══════════════════════════════════════════════════════════════════════

    # First pass — build to get total pages
    doc.build(story)

    # Second pass — fix page numbers in footer
    total_pages = doc.page
    _fix_page_numbers(filepath, total_pages)

    return filepath


def _fix_page_numbers(filepath, total_pages):
    """Replace {TOTAL} placeholder in PDF with actual page count."""
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
        data = data.replace(b'{TOTAL}', str(total_pages).encode())
        with open(filepath, 'wb') as f:
            f.write(data)
    except Exception:
        pass  # Non-critical — worst case shows {TOTAL}
