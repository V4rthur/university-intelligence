"""Build the defence presentation (PHASE 14) from the live warehouse numbers.

    python 11_Presentation/build_presentation.py

Writes 11_Presentation/University_Intelligence_Taqdimot.pptx (16 slides, about
7-10 minutes, speaker notes included). Every figure on the slides is read from
the warehouse through 05_Analytics/facts.py, so re-running the script after a
data refresh keeps the deck consistent with the dashboard.
"""
import sys
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import facts as F  # noqa: E402

# Minimal / Swiss palette: black, white, greys and one red accent.
NAVY, TEAL, INK, MUTED = "111111", "111111", "111111", "6B6B6B"
CARD, WHITE, AMBER, RED, ICE = "F2F2F2", "FFFFFF", "111111", "D52B1E", "BDBDBD"
RISK = ["D6D6D6", "9A9A9A", "4D4D4D", "D52B1E"]
OUT = config.PRESENTATION_DIR / "University_Intelligence_Taqdimot.pptx"
W, H = 13.333, 7.5


def rgb(h):
    return RGBColor.from_string(h)


def sp(n):
    return f"{n:,.0f}".replace(",", " ")


class Deck:
    def __init__(self):
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = Inches(W), Inches(H)
        self.n = 0

    def slide(self, title=None, notes="", dark=False):
        s = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        self.n += 1
        self.s = s
        if dark:
            s.background.fill.solid()
            s.background.fill.fore_color.rgb = rgb(NAVY)
        if title:
            self.text(0.6, 0.4, 12.1, 1.0, title, 30, True, WHITE if dark else NAVY, anchor="middle")
        if not dark:
            self.text(0.6, 6.95, 9, 0.3, "Sintetik ma'lumot asosida · University Intelligence & AI Decision System",
                      10, color=MUTED)
            self.text(11.9, 6.95, 0.85, 0.3, str(self.n), 10, color=MUTED, align="right")
        s.notes_slide.notes_text_frame.text = notes
        return s

    def text(self, x, y, w, h, content, size=16, bold=False, color=INK, align="left", anchor="top",
             spacing=6):
        box = self.s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = {"top": MSO_ANCHOR.TOP, "middle": MSO_ANCHOR.MIDDLE,
                              "bottom": MSO_ANCHOR.BOTTOM}[anchor]
        items = content if isinstance(content, list) else [content]
        for i, item in enumerate(items):
            txt, opt = item if isinstance(item, tuple) else (item, {})
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}[align]
            p.space_after = Pt(opt.get("spacing", spacing))
            r = p.add_run()
            r.text = txt
            r.font.name = "Arial"
            r.font.size = Pt(opt.get("size", size))
            r.font.bold = opt.get("bold", bold)
            r.font.color.rgb = rgb(opt.get("color", color))
        return box

    def card(self, x, y, w, h, fill=CARD):
        shp = self.s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
        shp.fill.solid()
        shp.fill.fore_color.rgb = rgb(fill)
        shp.line.fill.background()
        shp.shadow.inherit = False
        return shp

    def stat(self, x, y, w, value, label, color=TEAL, h=1.9):
        self.card(x, y, w, h)
        self.text(x + 0.25, y + 0.2, w - 0.5, 0.9, value, 40, True, color, anchor="middle")
        self.text(x + 0.25, y + 1.15, w - 0.5, h - 1.3, label, 14, color=MUTED)

    def badge(self, x, y, number, fill=RED, d=0.55):
        c = self.s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(d), Inches(d))
        c.fill.solid()
        c.fill.fore_color.rgb = rgb(fill)
        c.line.fill.background()
        c.shadow.inherit = False
        tf = c.text_frame
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = str(number)
        r.font.size, r.font.bold, r.font.name = Pt(18), True, "Arial"
        r.font.color.rgb = rgb(WHITE)

    def arrow(self, x, y, w=0.35, h=0.3):
        a = self.s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x), Inches(y), Inches(w), Inches(h))
        a.fill.solid()
        a.fill.fore_color.rgb = rgb(MUTED)
        a.line.fill.background()
        a.shadow.inherit = False

    def box(self, x, y, w, h, title, sub, fill=CARD, title_color=NAVY, sub_color=MUTED):
        self.card(x, y, w, h, fill)
        self.text(x + 0.15, y + 0.15, w - 0.3, h - 0.3,
                  [(title, dict(size=16, bold=True, color=title_color, spacing=4)),
                   (sub, dict(size=12, color=sub_color))], align="center", anchor="middle")

    def bar_chart(self, x, y, w, h, categories, values, number_format, colors=None, horizontal=True):
        data = CategoryChartData()
        data.categories = categories
        data.add_series("s", values)
        kind = XL_CHART_TYPE.BAR_CLUSTERED if horizontal else XL_CHART_TYPE.COLUMN_CLUSTERED
        chart = self.s.shapes.add_chart(kind, Inches(x), Inches(y), Inches(w), Inches(h), data).chart
        chart.has_legend = False
        chart.has_title = False
        chart.font.size, chart.font.name = Pt(12), "Arial"
        chart.font.color.rgb = rgb(MUTED)
        plot = chart.plots[0]
        plot.gap_width = 60
        plot.vary_by_categories = False
        plot.has_data_labels = True
        dl = plot.data_labels
        dl.number_format, dl.number_format_is_linked = number_format, False
        dl.position = XL_LABEL_POSITION.OUTSIDE_END
        dl.font.size = Pt(12)
        dl.font.color.rgb = rgb(INK)
        chart.value_axis.minimum_scale = 0
        chart.value_axis.visible = False
        chart.value_axis.has_major_gridlines = False
        chart.category_axis.format.line.fill.background()
        chart.category_axis.tick_labels.font.size = Pt(12)
        if horizontal:
            chart.category_axis.reverse_order = True
        series = plot.series[0]
        for i in range(len(values)):
            pt = series.points[i]
            pt.format.fill.solid()
            pt.format.fill.fore_color.rgb = rgb(colors[i] if colors else TEAL)

    def table(self, x, y, w, col_widths, header, rows, row_h=0.62):
        shape = self.s.shapes.add_table(len(rows) + 1, len(header), Inches(x), Inches(y), Inches(w),
                                        Inches(row_h * (len(rows) + 1)))
        t = shape.table
        for j, cw in enumerate(col_widths):
            t.columns[j].width = Inches(cw)
        for i, row in enumerate([header] + rows):
            for j, val in enumerate(row):
                cell = t.cell(i, j)
                cell.fill.solid()
                cell.fill.fore_color.rgb = rgb(NAVY if i == 0 else (WHITE if i % 2 else CARD))
                cell.vertical_anchor = MSO_ANCHOR.MIDDLE
                cell.margin_left = cell.margin_right = Inches(0.12)
                p = cell.text_frame.paragraphs[0]
                p.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER
                r = p.add_run()
                r.text = str(val)
                r.font.size, r.font.name = Pt(14), "Arial"
                r.font.bold = i == 0
                r.font.color.rgb = rgb(WHITE if i == 0 else INK)


def build() -> Path:
    f = F.collect()
    k, best, w, sc = f["kpis"], f["best"], f["worst_faculty"], f["scenarios"]
    q, ex = f["quality"], f["example"]
    d = Deck()

    # 1 ------------------------------------------------------------------ title
    d.slide(dark=True, notes="(20 soniya) Salomlashish. Loyiha nomi va bitta gap: bu tizim universitet "
            "rahbariyatiga ma'lumot asosida qaror qabul qilishga yordam beradi.")
    d.text(0.9, 2.0, 11.5, 1.6, "University Intelligence\n& AI Decision System", 48, True, WHITE, spacing=0)
    d.text(0.9, 4.15, 11.0, 0.9, "Universitet boshqaruvi uchun ma'lumotlarga asoslangan "
           "qarorlarni qo'llab-quvvatlash tizimi", 22, color=ICE)
    d.text(0.9, 5.6, 11.0, 0.5, "Data Engineering  ·  Data Analytics  ·  Machine Learning  ·  AI Agent",
           16, color=ICE)

    # 2 ---------------------------------------------------------------- problem
    d.slide("Qarorlar kech va tarqoq ma'lumot asosida qabul qilinadi",
            "(40 soniya) Uchta muammo. Ma'lumot turli fayllarda; muammo semestr oxirida ko'rinadi; "
            "xavf ostidagi talaba o'qishni tashlagach aniqlanadi.")
    for i, (head, body) in enumerate([
            ("Ma'lumot tarqoq", "Baholar, davomat, to'lov va topshiriqlar alohida fayl va tizimlarda. "
                                "Yagona manzara yo'q."),
            ("Qaror kechikadi", "Davomat pasayishi yoki fandan ommaviy yiqilish semestr yakunida, "
                                "oqibatidan keyin ko'rinadi."),
            ("Xavf kech aniqlanadi", "Qiynalayotgan talaba akademik qarzdor bo'lgach yoki o'qishni "
                                     "tashlagach ma'lum bo'ladi.")]):
        x = 0.6 + i * 4.1
        d.card(x, 1.8, 3.85, 4.4)
        d.badge(x + 0.35, 2.15, i + 1)
        d.text(x + 0.35, 3.0, 3.2, 0.6, head, 22, True, NAVY)
        d.text(x + 0.35, 3.75, 3.2, 2.2, body, 16, color=INK)

    # 3 ---------------------------------------------------------- why it matters
    d.slide("Har bir kechikkan qaror - yo'qotilgan talaba",
            "(40 soniya) Raqamlar bizning (sintetik) universitet ma'lumotidan. O'qishni tashlaganlar, "
            "hozir xavf ostidagilar, yiqilish darajasi va to'lanmagan kontrakt.")
    for i, (val, lab, col) in enumerate([
            (sp(f["dropped"]), "talaba 4 yilda o'qishni tark etgan", RED),
            (sp(k["high_risk_students"]), f"faol talaba yuqori yoki kritik xavfda ({k['high_risk_share']:.0%})", RED),
            (f"{k['failure_rate']:.1%}", "fan natijalari - yiqilish (joriy semestr)", AMBER),
            (f"{k['outstanding_debt'] / 1e9:.0f} mlrd", "so'm to'lanmagan kontrakt qarzi", AMBER)]):
        d.stat(0.6 + i * 3.07, 2.0, 2.85, val, lab, col, h=2.6)
    d.text(0.6, 5.1, 12.1, 1.2, "Bu holatlarning aksariyati oldindan ko'rinadi - agar ma'lumot bir joyda "
           "bo'lsa va undan to'g'ri savol so'ralsa.", 20, color=NAVY)

    # 4 --------------------------------------------------------------- solution
    d.slide("Bitta tizim to'rt savolga javob beradi",
            "(40 soniya) To'rt daraja: tavsifiy, diagnostik, bashoratli, tavsiyaviy. Muhimi - ular "
            "alohida loyihalar emas, bitta ma'lumot oqimiga ulangan.")
    for i, (qn, level, how) in enumerate([
            ("Nima bo'ldi?", "Tavsifiy tahlil", "KPI, salomatlik bali, fakultet va fan ko'rsatkichlari"),
            ("Nega bo'ldi?", "Diagnostik tahlil", "Chuqurlashish, anomaliyalar, omillar tahlili"),
            ("Nima bo'ladi?", "Bashoratli tahlil", "Talaba xavfi modeli, keyingi semestr GPA bashorati"),
            ("Nima qilish kerak?", "Tavsiyaviy tahlil", "«Agar...» ssenariylari, alertlar, AI agent")]):
        x = 0.6 + i * 3.07
        d.card(x, 1.8, 2.85, 4.5, NAVY if i == 3 else CARD)
        dark = i == 3
        d.text(x + 0.25, 2.1, 2.35, 1.2, qn, 24, True, WHITE if dark else NAVY)
        d.text(x + 0.25, 3.4, 2.35, 0.5, level, 14, True, ICE if dark else TEAL)
        d.text(x + 0.25, 4.0, 2.35, 2.0, how, 15, color=WHITE if dark else INK)

    # 5 ----------------------------------------------------------- architecture
    d.slide("Arxitektura: ma'lumotdan qarorgacha bitta oqim",
            "(50 soniya) Chapdan o'ngga: xom fayllar, Python ETL, SQL Server ombori. Ombordan uchta "
            "iste'molchi: dashboard, ML, AI agent. Hammasi bir xil tahlil qatlamidan foydalanadi.")
    y = 3.0
    d.box(0.6, y, 2.05, 1.5, "Manbalar", "CSV · Excel · JSON\n11 turdagi fayl")
    d.arrow(2.75, y + 0.6)
    d.box(3.2, y, 2.05, 1.5, "Python ETL", "tozalash · tekshirish\ntransformatsiya", TEAL, WHITE, WHITE)
    d.arrow(5.35, y + 0.6)
    d.box(5.8, y, 2.2, 1.5, "SQL Server ombori", "yulduz sxemasi\n7 o'lchov · 6 fakt", TEAL, WHITE, WHITE)
    d.arrow(8.1, y + 0.6)
    for i, (t, s) in enumerate([("Dashboard", "7 sahifa · Streamlit"), ("ML modellari", "xavf · tushuntirish"),
                                ("AI agent", "9 vosita · LLM")]):
        d.box(8.55, 1.75 + i * 1.4, 2.2, 1.2, t, s)
    d.arrow(10.85, y + 0.6)
    d.box(11.3, y, 1.45, 1.5, "Qaror", "rahbariyat", RED, WHITE, WHITE)
    d.text(0.6, 6.05, 12.1, 0.6, "Dashboard va AI agent bir xil tahlil funksiyalarini chaqiradi - "
           "grafikdagi va javobdagi raqam hech qachon farq qilmaydi.", 16, color=MUTED)

    # 6 ------------------------------------------------------- data engineering
    d.slide("Ishonchli ma'lumot: har bir yozuv tekshiruvdan o'tadi",
            "(40 soniya) ETL olti bosqich. Qayta ishga tushirish dublikat yaratmaydi - MERGE. "
            "Yaroqsiz yozuvlar o'chirilmaydi, sababi bilan karantinga olinadi.")
    steps = ["Extract - faqat yangi yoki o'zgargan fayllar (xesh bo'yicha)",
             "Clean - format, tur, bo'sh qiymat, dublikat",
             "Validate - oraliq, chetlanish, bog'lanish yaxlitligi",
             "Stage - toza yozuvlar staging jadvallarida",
             "Load - MERGE: qayta yuklash dublikat yaratmaydi",
             "Test - har ishga tushirishdan keyin avtomatik tekshiruv"]
    for i, s in enumerate(steps):
        d.badge(0.6, 1.75 + i * 0.8, i + 1, d=0.5)
        d.text(1.3, 1.75 + i * 0.8, 6.3, 0.5, s, 16, anchor="middle")
    d.stat(8.2, 1.7, 4.5, sp(f["fact_rows"]), "ombordagi fakt yozuvlari", h=1.5)
    d.stat(8.2, 3.35, 4.5, f"{q['score']:.2%}", "ma'lumotlar sifati bali", h=1.5)
    d.stat(8.2, 5.0, 4.5, sp(q["rejected"]), "yaroqsiz yozuv karantinga olingan", AMBER, h=1.5)

    # 7 -------------------------------------------------------------- dashboard
    fs = f["faculties"].sort_values("AvgGPA", ascending=False)
    d.slide("Boshqaruv paneli: har bir sahifa bitta savolga javob beradi",
            "(40 soniya) Dashboard brauzerda ochiladi, sof Pythonda yozilgan. Chapda fakultetlar GPA "
            "taqqoslamasi. Bu yerda jonli demoga o'tish mumkin.")
    d.text(0.6, 1.6, 6.2, 0.4, f"Fakultetlar bo'yicha o'rtacha GPA ({k['semester']})", 16, True, NAVY)
    d.bar_chart(0.5, 2.0, 6.4, 4.6, list(fs.FacultyName), [round(float(v), 2) for v in fs.AvgGPA], "0.00",
                colors=[RED if n == w.FacultyName else TEAL for n in fs.FacultyName])
    groups = [("Hozir nima bo'lyapti?", "Umumiy ko'rinish · Fakultetlar"),
              ("Imtihonlar qanday o'tdi?", "Imtihon natijalari: oraliq va yakuniy nazorat"),
              ("Kimga yordam kerak?", "Xavf ostidagi talabalar va sabablari"),
              ("Nima qilish kerak?", "«Agar...» ssenariylari · AI yordamchi")]
    for i, (g, pages) in enumerate(groups):
        d.card(7.3, 1.7 + i * 1.25, 5.45, 1.1)
        d.text(7.55, 1.78 + i * 1.25, 5.0, 0.95, [(g, dict(size=16, bold=True, color=NAVY, spacing=2)),
                                                 (pages, dict(size=13, color=MUTED))], anchor="middle")

    # 8 -------------------------------------------------------- risk prediction
    d.slide(f"Model xavf ostidagi talabalarning {best.Recall:.0%} qismini oldindan topadi",
            "(50 soniya) Model keyingi semestrni bashorat qiladi va keyingi semestrda sinalgan. "
            "Accuracy yetarli emas: asosiy ko'rsatkich recall. False Negative - yordamsiz qolgan talaba.")
    d.stat(0.6, 1.8, 2.75, f"{best.Recall:.0%}", "Recall - topilgan xavf ostidagi talabalar", h=2.1)
    d.stat(3.55, 1.8, 2.75, f"{best.Precision:.0%}", "Precision - belgilanganlar ichida haqiqiylari", h=2.1)
    d.stat(0.6, 4.1, 2.75, f"{best.ROC_AUC:.2f}", "ROC-AUC - saralash sifati", h=2.1)
    d.stat(3.55, 4.1, 2.75, sp(best.FN), "False Negative - o'tkazib yuborilgan", RED, h=2.1)
    d.text(6.9, 1.7, 5.8, 0.4, "Faol talabalar xavf darajasi bo'yicha", 16, True, NAVY)
    lv = f["risk_levels"]
    d.bar_chart(6.8, 2.1, 6.0, 3.6, list(lv.index), [int(v) for v in lv.values], "# ##0", colors=RISK,
                horizontal=False)
    d.text(6.9, 5.8, 5.8, 0.9, f"4 ta model taqqoslandi; tanlangani: {best.Model}. Sinov - o'qitishda "
           "ishtirok etmagan keyingi semestr.", 14, color=MUTED)

    # 9 ----------------------------------------------------------- explainable
    shares = [(g, float(ex[c])) for g, c in F.rm.GROUP_COLUMNS.items() if float(ex[c]) >= 1]
    shares.sort(key=lambda x: -x[1])
    d.slide("Har bir bashorat tushuntiriladi: nima uchun xavf yuqori",
            "(40 soniya) Model faqat 'xavf yuqori' demaydi. Har bir talaba uchun omillar ulushi "
            "ko'rsatiladi. Bu model nimaga tayanganini ko'rsatadi, sababni isbotlamaydi.")
    d.card(0.6, 1.8, 5.2, 4.6)
    d.text(0.9, 2.0, 4.6, 0.4, f"Misol: talaba ID {int(ex.StudentKey)} · {ex.FacultyName}", 14, color=MUTED)
    d.text(0.9, 2.45, 4.6, 1.0, f"{ex.RiskProbability:.0%}", 54, True, RED, anchor="middle")
    d.text(0.9, 3.5, 4.6, 0.4, f"keyingi semestr uchun xavf ehtimoli ({ex.RiskLevel})", 14, color=MUTED)
    d.text(0.9, 4.15, 4.6, 2.1, [
        f"Joriy semestr GPA: {ex.SemGPA:.2f}", f"Davomat: {ex.AttendanceRate:.0%}",
        f"Yiqilgan fanlar: {int(ex.FailedCourses)} (jami {int(ex.CumFailedCourses)})",
        f"Topshiriq topshirish: {ex.SubmissionRate:.0%}"], 16)
    d.text(6.3, 1.7, 6.4, 0.4, "Omillarning xavfdagi ulushi, %", 16, True, NAVY)
    d.bar_chart(6.2, 2.1, 6.6, 3.6, [s[0] for s in shares], [round(s[1], 1) for s in shares], '0"%"')
    d.text(6.3, 5.8, 6.4, 0.9, "Usul: omil qiymatlari tipik xavfsiz talaba qiymatlari bilan almashtiriladi "
           "va bashorat qanchaga kamayishi o'lchanadi.", 14, color=MUTED)

    # 10 ------------------------------------------------------------- scenarios
    d.slide("«Agar...» ssenariylari: qaror ta'siri oldindan baholanadi",
            "(50 soniya) Besh ssenariy. Eng katta samara - maqsadli dasturlarda. O'qituvchi yuklamasi "
            "bo'yicha sezilarli bog'liqlik topilmadi - bu ham topilma.")
    rows = [[v["title"], sp(v["affected"]), f"{v['d_risk']:+,}".replace(",", " "), f"{v['d_gpa']:+.2f}",
             f"{round(v['d_fail'] * 100, 1) + 0:+.1f} f.p."] for v in sc.values()]
    d.table(0.6, 1.75, 12.1, [5.9, 1.6, 1.7, 1.2, 1.7],
            ["Ssenariy", "Qamrov", "Xavf ostidagilar", "GPA", "Yiqilish"], rows, row_h=0.68)
    d.text(0.6, 6.0, 12.1, 0.8, "Model asosidagi baho: kuzatilgan bog'liqliklarga tayanadi, kafolatlangan "
           "sabab-oqibat emas. Dasturlar ta'sir kuchi - sozlanadigan faraz.", 14, color=MUTED)

    # 11 ----------------------------------------------------------------- agent
    d.slide("AI agent: savol tabiiy tilda, javob faqat ma'lumotdan",
            "(50 soniya) Bu chatbot emas. Agent qaysi vositani chaqirishni o'zi tanlaydi, har bir "
            "raqam vosita natijasidan olinadi. Ma'lumot bo'lmasa - buni ochiq aytadi.")
    tools = ["Universitet holati", "Fakultetlar", "Imtihonlar", "Talabalar", "Fanlar",
             "ML bashorati", "Ssenariylar", "SQL (o'qish)", "Hisobot"]
    d.text(0.6, 1.7, 5.6, 0.4, "9 ta vosita", 16, True, NAVY)
    for i, t in enumerate(tools):
        d.card(0.6 + (i % 3) * 1.95, 2.2 + (i // 3) * 1.25, 1.8, 1.05)
        d.text(0.72 + (i % 3) * 1.95, 2.2 + (i // 3) * 1.25, 1.56, 1.05, t, 14, color=INK, anchor="middle")
    d.card(6.8, 1.7, 5.9, 4.15, NAVY)
    d.text(7.1, 1.95, 5.3, 3.65, [
        ("SAVOL", dict(size=12, bold=True, color=ICE, spacing=2)),
        ("Qaysi fakultetda akademik xavf eng yuqori?", dict(size=16, color=WHITE, spacing=12)),
        ("JAVOB", dict(size=12, bold=True, color=ICE, spacing=2)),
        (f"{w.FacultyName}: yuqori/kritik xavfda {int(w.HighRiskStudents)} talaba "
         f"({w.HighRiskShare:.1%}), GPA {w.AvgGPA:.2f}, davomat {w.AttendanceRate:.1%}",
         dict(size=16, color=WHITE, spacing=12)),
        ("HIMOYA", dict(size=12, bold=True, color=ICE, spacing=2)),
        ("Vositalar izi ko'rsatiladi · rolga qarab kirish · SQL faqat SELECT",
         dict(size=14, color=WHITE))], anchor="middle")

    # 12 -------------------------------------------------------------- insights
    an = f["anomalies"]
    insights = [
        (f"{w.FacultyName} fakulteti xavf zonasida",
         f"Xavf ostidagilar {w.HighRiskShare:.0%}; GPA uch yil ketma-ket pasaymoqda: "
         + " → ".join(f"{v:.2f}" for v in f["worst_gpa_trend"][-3:])),
        ("Xavfni akademik tarix tushuntiradi",
         ", ".join(f"{g} {v:.0f}%" for g, v in f["factor_shares"].head(3).items())
         + ". Davomat ta'siri GPA orqali aks etgan."),
    ]
    ex_ = f["exam"]
    insights.append(("Oraliq nazorat - erta ogohlantirish",
                     f"Oraliqda 60% dan past olganlarning {ex_['low_midterm_not_passed']:.0%} qismi yakuniy "
                     f"nazoratdan o'tmagan. Yakuniyga qo'yilmaganlar: {ex_['NotAdmittedRate']:.1%}"))
    for _, a in an[~an.What.str.contains("oshdi")].head(1).iterrows():
        insights.append((f"Anomaliya: {a.Where}", f"{a.When}: {a.What.lower()} ({a.Before} → {a.After})"))
    d.slide("Asosiy topilmalar",
            "(50 soniya) To'rtta topilma, har biri raqam bilan. Anomaliyalar tizim tomonidan avtomatik "
            "aniqlangan; ehtimoliy sabab - tekshirish uchun yo'nalish.")
    for i, (head, body) in enumerate(insights[:4]):
        x, y = 0.6 + (i % 2) * 6.15, 1.8 + (i // 2) * 2.45
        d.card(x, y, 5.95, 2.2)
        d.badge(x + 0.3, y + 0.3, i + 1)
        d.text(x + 1.05, y + 0.3, 4.65, 0.6, head, 18, True, NAVY, anchor="middle")
        d.text(x + 0.3, y + 1.05, 5.35, 1.05, body, 15)

    # 13 ------------------------------------------------------- recommendations
    t, iv = sc["tutoring_30"], sc["risk_intervention"]
    recs = [
        (f"{w.FacultyName} fakultetida maqsadli akademik dastur",
         f"{int(w.HighRiskStudents)} nafar yuqori/kritik xavfdagi talaba bilan birinchi navbatda ishlash"),
        ("Tyutorlik dasturini pilot sifatida sinash",
         f"Xavfi eng yuqori 30% talaba; model bahosi: xavf ostidagilar {t['d_risk']:+,}".replace(",", " ")),
        ("Xavfdagi talabalarga maslahatchi biriktirish",
         f"Model bahosi: yuqori/kritik guruh {iv['d_high']:+,} talabaga o'zgaradi".replace(",", " ")),
        ("Anomaliya aniqlangan fanlarni ko'rib chiqish",
         "Imtihon materiallari va baholash mezonlari tekshiriladi"),
    ]
    d.slide("Tavsiyalar: kimga, nima va qaysi tartibda",
            "(40 soniya) Tavsiyalar ustuvorlik tartibida va raqamga bog'langan. Birinchisi - eng yuqori "
            "xavfli fakultet. Ikkinchisi - pilot, chunki samarani faqat tajriba isbotlaydi.")
    for i, (head, body) in enumerate(recs):
        y = 1.75 + i * 1.2
        d.card(0.6, y, 12.1, 1.05)
        d.badge(0.85, y + 0.25, i + 1)
        d.text(1.65, y + 0.1, 10.8, 0.45, head, 18, True, NAVY, anchor="middle")
        d.text(1.65, y + 0.55, 10.8, 0.4, body, 14, color=MUTED, anchor="middle")

    # 14 ---------------------------------------------------------------- impact
    a = sc["attendance_drop"]
    d.slide("Kutilayotgan ta'sir",
            "(30 soniya) Uchta raqam simulyatsiyadan. Bular model bahosi - kafolat emas; haqiqiy samara "
            "pilot tajribada o'lchanadi.")
    d.stat(0.6, 1.9, 3.85, f"{t['d_risk']:+,}".replace(",", " "),
           "xavf ostidagi talaba - tyutorlik dasturi (30% qamrov)", h=2.5)
    d.stat(4.75, 1.9, 3.85, f"{iv['d_high']:+,}".replace(",", " "),
           "yuqori/kritik xavfdagi talaba - maqsadli aralashuv", h=2.5)
    d.stat(8.9, 1.9, 3.8, f"{a['d_risk']:+,}".replace(",", " "),
           "xavf ostidagi talaba - agar davomat 5 f.p. pasaysa (harakatsizlik narxi)", RED, h=2.5)
    d.text(0.6, 4.8, 12.1, 1.6, [
        "Xavf ostidagi talaba semestr yakunida emas, keyingi semestr boshlanishidan oldin aniqlanadi.",
        "Resurslar eng katta samara kutilgan guruhga yo'naltiriladi.",
        "Rahbariyat, dekanat va o'qituvchilar yagona manbadagi raqamlar bilan ishlaydi."], 16)

    # 15 ---------------------------------------------------------------- future
    d.slide("Keyingi qadamlar",
            "(30 soniya) Tizim haqiqiy ma'lumotga ulanishga tayyor: faqat manba almashadi. Keyingi "
            "bosqich - pilot va semestr ichidagi erta ogohlantirish.")
    for i, (head, body) in enumerate([
            ("Haqiqiy ma'lumot", "LMS, kontingent va buxgalteriya tizimlariga ulanish"),
            ("Erta ogohlantirish", "Semestr ichida, haftalik davomat va topshiriqlar asosida"),
            ("Pilot tajribalar", "Aralashuv samarasini o'lchash va simulyatsiyaga qaytarish"),
            ("Xavfsizlik", "SQL rollari, qator darajasidagi himoya, yagona kirish (SSO)")]):
        x = 0.6 + i * 3.07
        d.card(x, 1.9, 2.85, 3.6)
        d.badge(x + 0.25, 2.2, i + 1)
        d.text(x + 0.25, 3.0, 2.35, 0.9, head, 20, True, NAVY)
        d.text(x + 0.25, 3.95, 2.35, 1.4, body, 15)
    d.text(0.6, 5.85, 12.1, 0.8, "Cheklov: natijalar sintetik ma'lumotda olingan. Haqiqiy universitetda "
           "raqamlar boshqacha bo'ladi, usul esa o'zgarmaydi.", 14, color=MUTED)

    # 16 ------------------------------------------------------------ conclusion
    d.slide(dark=True, notes="(30 soniya) Yakun: bu to'rt texnologiyani bitta qaror tizimiga "
            "birlashtirgan loyiha. Savollarga tayyorman - jonli demoni ko'rsatishim mumkin.")
    d.text(0.9, 1.2, 11.5, 2.2, "Bu dashboard emas, model emas, chatbot emas.\n"
           "Bu - qaror qabul qilish tizimi.", 40, True, WHITE, spacing=0)
    d.text(0.9, 3.9, 11.5, 2.2, [
        f"{sp(f['fact_rows'])} yozuv tozalangan va yagona omborda",
        f"Xavf ostidagi talabalarning {best.Recall:.0%} qismi bir semestr oldin aniqlanadi",
        "Har bir bashorat tushuntiriladi, har bir qaror oldindan sinab ko'riladi",
        "AI agent faqat ma'lumot va model natijasiga tayanadi"], 20, color=ICE, spacing=10)
    d.text(0.9, 6.5, 11.5, 0.4, "Savollaringizga tayyorman", 16, color=WHITE)

    config.PRESENTATION_DIR.mkdir(parents=True, exist_ok=True)
    d.prs.save(OUT)
    return OUT


if __name__ == "__main__":
    print(f"saved {build().relative_to(config.ROOT)}")
