"""One-page executive summary as a PDF, built from the same metrics as the dashboard.

    from report_pdf import build_pdf
    pdf_bytes = build_pdf(metrics.load_all(engine))
"""
import io
import sys
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import metrics as m  # noqa: E402

NAVY, BLUE, MUTED, LINE, SOFT = "#111111", "#d52b1e", "#767676", "#bdbdbd", "#f2f2f2"
LEVEL = {"critical": ("KRITIK", "#d52b1e"), "warning": ("OGOHLANTIRISH", "#111111"),
         "attention": ("E'TIBOR", "#111111"), "positive": ("IJOBIY", "#767676")}


def _style(name, size, color=NAVY, bold=False, space=0, leading=None):
    return ParagraphStyle(name, fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=size,
                          textColor=colors.HexColor(color), spaceAfter=space,
                          leading=leading or size * 1.3)


def _clean(text: str) -> str:
    """The built-in PDF font has no arrows or typographic quotes."""
    for a, b in (("→", "->"), ("«", '"'), ("»", '"'), ("—", "-"), ("·", "|")):
        text = text.replace(a, b)
    return text


def build_pdf(d: dict) -> bytes:
    k = m.kpis(d)
    score, detail = m.university_health(d)
    fs = m.faculty_summary(d)
    ex = m.exam_overview(d)
    alerts = m.alerts(d)

    h1, h2 = _style("h1", 22, bold=True, space=4), _style("h2", 8.5, bold=True, space=5)
    body, small = _style("body", 9.5, leading=13), _style("small", 8, MUTED, leading=10.5)
    label, value = _style("label", 8, MUTED), _style("value", 15, bold=True)

    story = [
        Paragraph("University Intelligence: rahbariyat uchun qisqa hisobot", h1),
        Paragraph(f"Semestr: {k['semester']} | solishtirish: {k['compared_with']} | "
                  f"tayyorlangan: {datetime.now():%Y-%m-%d %H:%M}", small),
        Spacer(1, 7 * mm),
    ]

    def cell(name, val, note=""):
        return [Paragraph(name, label), Paragraph(val, value), Paragraph(note, small)]

    def pp(cur, prev):
        return "" if prev is None else f"{(cur - prev) * 100:+.1f} f.p."

    cards = [
        cell("Salomatlik bali", f"{score:.0f} / 100"),
        cell("Faol talabalar", f"{k['total_students']:,}".replace(",", " ")),
        cell("O'rtacha GPA (5 ballik)", f"{k['avg_gpa']:.2f}", f"{round(k['avg_gpa'] - k['avg_gpa_prev'], 2) + 0:+.2f}"),
        cell("Davomat", f"{k['attendance']:.1%}", pp(k["attendance"], k["attendance_prev"])),
        cell("Fandan yiqilish", f"{k['failure_rate']:.1%}", pp(k["failure_rate"], k["failure_rate_prev"])),
        cell("Xavf ostidagi talabalar", f"{k['high_risk_students']:,}".replace(",", " "),
             f"faol talabalarning {k['high_risk_share']:.1%}"),
    ]
    grid = Table([cards[:3], cards[3:]], colWidths=[58 * mm] * 3)
    grid.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, -1), 1.4, colors.HexColor(NAVY)),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [grid, Spacer(1, 6 * mm)]

    story.append(Paragraph("NIMAGA E'TIBOR BERISH KERAK", h2))
    for a in alerts[:5]:
        name, color = LEVEL[a["level"]]
        story.append(Paragraph(f'<font color="{color}"><b>{name}:</b></font> {_clean(a["text"])}', body))
    if not alerts:
        story.append(Paragraph("Faol ogohlantirish yo'q.", body))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("FAKULTETLAR", h2))
    rows = [["O'rin", "Fakultet", "Talabalar", "GPA", "Davomat", "Yiqilish", "Xavf ostida", "Ball"]]
    for r in fs.itertuples():
        rows.append([r.Rank, r.FacultyName, f"{r.Students:,}".replace(",", " "), f"{r.AvgGPA:.2f}",
                     f"{r.AttendanceRate:.1%}", f"{r.FailureRate:.1%}", f"{r.HighRiskShare:.1%}",
                     f"{r.HealthScore:.0f}"])
    table = Table(rows, colWidths=[12 * mm, 52 * mm, 20 * mm, 15 * mm, 20 * mm, 19 * mm, 22 * mm, 14 * mm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor(NAVY)),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"), ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor(LINE)),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story += [table, Spacer(1, 5 * mm)]

    mx = config.SCORE_MAX
    story.append(Paragraph("IMTIHON NATIJALARI", h2))
    story.append(Paragraph(
        f"Oraliq nazorat o'rtacha natijasi {ex['MidtermPct']:.1%} (o'tganlar {ex['MidtermPassRate']:.1%}); "
        f"yakuniy nazorat {ex['FinalPct']:.1%} (qo'yilganlar orasida o'tganlar {ex['FinalPassRate']:.1%}). "
        f"Yakuniy nazoratga qo'yilmagan natijalar: {ex['NotAdmittedRate']:.1%}. Oraliq nazoratdan o'tgan, "
        f"lekin fandan yiqilganlar: {ex['LostAfterMidterm']:.1%}. Baholash: joriy {mx['current']} + oraliq "
        f"{mx['midterm']} + yakuniy {mx['final']} ball, o'tish bali {config.PASS_MARK}.", body))
    story.append(Spacer(1, 5 * mm))

    weakest = detail.sort_values("SubScore").iloc[0]
    worst = fs.sort_values("HighRiskShare", ascending=False).iloc[0]
    story.append(Paragraph("BIRINCHI NAVBATDAGI QADAMLAR", h2))
    for i, text in enumerate([
            f"{worst.FacultyName} fakultetidagi {int(worst.HighRiskStudents)} nafar yuqori yoki kritik xavfdagi "
            "talaba bilan maslahatchilar ishini boshlash.",
            "Oraliq nazoratda 60% dan past natija olgan talabalarga yakuniy nazoratgacha qo'shimcha "
            "konsultatsiya tashkil etish.",
            f"Salomatlik balining eng zaif komponentini ko'rib chiqish: {weakest.Component} "
            f"({weakest.SubScore:.0f} ball)."], 1):
        story.append(Paragraph(f"{i}. {_clean(text)}", body))

    story += [Spacer(1, 7 * mm), Paragraph(
        "Ma'lumotlar sintetik (sun'iy yaratilgan) - haqiqiy universitet ma'lumoti emas. Xavf bahosi model "
        "ehtimolligi bo'lib, kafolat emas. Manba: University Intelligence & AI Decision System.", small)]

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                      bottomMargin=14 * mm, title="University Intelligence hisoboti").build(story)
    return buf.getvalue()
