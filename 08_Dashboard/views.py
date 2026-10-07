"""Dashboard pages: overview, faculties, exam results, students at risk, more.

Each page answers one management question with a handful of numbers, one or
two charts and one table. Detail that is not needed every day sits in
expanders.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
import interventions as iv
import metrics as m
import risk_model as rm
import ui
from report_pdf import build_pdf

MX = config.SCORE_MAX
PCT = st.column_config.NumberColumn
NOT_ADMITTED = "Qo'yilmagan"
NO_ACTION = "-"            # risk table: no intervention recorded yet
GRADES_H = 250             # exams page: grades chart and the table beside it


def _scope():
    """(may see named students, faculty restriction) for the selected role."""
    role = st.session_state.get("role", "oqituvchi")
    fk = st.session_state.get("own_faculty") if role == "dekan" else None
    return role != "oqituvchi", fk


def _no_student_access():
    st.info("Tanlangan rol (professor-o'qituvchi) uchun talaba darajasidagi shaxsiy ma'lumotlar "
            "yopiq. Faqat umumlashtirilgan ko'rsatkichlar ko'rsatiladi.")


@st.cache_data(show_spinner=False, max_entries=2)
def _report(version: str, _d: dict) -> bytes:
    """One-page PDF summary; rebuilt only when the data version changes."""
    return build_pdf(_d)


def _lines(df, x, series, title, height=300):
    """A few percentage series on one axis, legend always shown."""
    fig = go.Figure()
    for (col, label), color in zip(series, ui.SERIES):
        ui.glow_line(fig, df[x], df[col], label, color, ".1%", unified=True)
    fig.update_layout(hovermode="x unified")
    return ui.style(fig, height, "y", title=title)


# ----------------------------------------------------------------- 1. overview
def overview(d):
    k = m.kpis(d)
    score, detail = m.university_health(d)
    ui.header("Umumiy ko'rinish", f"O'zgarishlar {k['compared_with']} semestriga nisbatan ko'rsatilgan")

    # one focal point (the health score) with the supporting numbers beside it
    focal, side = st.columns([5, 9])
    with focal:
        weakest = detail.sort_values("SubScore").iloc[0]
        ui.score(score, "Universitet salomatlik bali",
                 f"Eng zaif komponent: {weakest.Component} ({weakest.SubScore:.0f} ball)")
    with side:
        c = st.columns(3)
        ui.kpi(c[0], "Faol talabalar", ui.num(k["total_students"]))
        ui.kpi(c[1], "O'rtacha GPA (5 ballik)", f"{k['avg_gpa']:.2f}",
               f"{round(k['avg_gpa'] - k['avg_gpa_prev'], 2) + 0:+.2f}")
        ui.kpi(c[2], "Davomat", ui.pct(k["attendance"]), ui.pp(k["attendance"], k["attendance_prev"]))
        c = st.columns(3)
        ui.kpi(c[0], "Fandan yiqilish", ui.pct(k["failure_rate"]),
               ui.pp(k["failure_rate"], k["failure_rate_prev"]), inverse=True,
               help=f"Jami ball {config.PASS_MARK} dan past bo'lgan fan natijalari ulushi.")
        ui.kpi(c[1], "Xavf ostida", ui.num(k["high_risk_students"]),
               help=f"Model bahosi bo'yicha yuqori yoki kritik xavfda: faol talabalarning "
                    f"{ui.pct(k['high_risk_share'])}.")
        ui.kpi(c[2], "To'lov yig'ilishi", ui.pct(k["collection_rate"]),
               ui.pp(k["collection_rate"], k["collection_rate_prev"]))

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Nimaga e'tibor berish kerak")
        alerts = m.alerts(d)
        shown = max(1, min(len(alerts), 5))
        for a in alerts[:5]:
            ui.alert_box(a["level"], a["text"])
        if len(alerts) > 5:
            with st.expander(f"Yana {len(alerts) - 5} ta xabar"):
                for a in alerts[5:]:
                    ui.alert_box(a["level"], a["text"])
        if not alerts:
            st.write("Faol ogohlantirish yo'q.")
    with right:
        st.subheader("Xavf darajalari")
        risk = d["risk"].RiskLevel.value_counts().reindex(config.RISK_ORDER).fillna(0).reset_index()
        risk.columns = ["Daraja", "Talabalar"]
        ui.show(ui.bar_v(risk, "Daraja", "Talabalar", colors=[ui.RISK_COLORS[r] for r in risk.Daraja],
                         height=max(240, ui.ALERT_ROW * shown - ui.ALERT_GAP)))

    st.subheader("Yildan yilga dinamika")
    options = {"O'rtacha GPA": ("AvgGPA", False), "Davomat": ("AttendanceRate", True),
               "Fandan yiqilish": ("FailureRate", True)}
    choice = st.segmented_control("Ko'rsatkich", list(options), default="O'rtacha GPA",
                                  label_visibility="collapsed") or "O'rtacha GPA"
    col, percent = options[choice]
    trend = m.semester_trend(d).merge(
        d["semesters"][["SemesterKey", "AcademicYear", "SemesterName"]], on="SemesterKey")
    ui.show(ui.season_lines(trend, col, percent=percent))
    st.caption("Kuz va Bahor semestrlari alohida chiziqda: ularda o'qitiladigan fanlar turlicha, "
               "shuning uchun har bir semestr faqat o'tgan yillardagi shu semestr bilan solishtiriladi.")

    st.download_button(
        "Rahbariyat uchun bir sahifalik hisobotni yuklab olish (PDF)", icon=":material/download:",
        data=_report(st.session_state.get("data_version", ""), d),
        file_name=f"universitet_hisoboti_{k['semester'].replace(' ', '_')}.pdf", mime="application/pdf")

    with st.expander("Salomatlik bali qanday hisoblangan"):
        show = detail.assign(Qiymat=[
            f"{v:.2f}" if key == "academic" else ui.pct(v) for key, v in zip(detail.Key, detail.Value)])
        st.dataframe(show[["Component", "Qiymat", "SubScore", "Weight", "Points"]], hide_index=True,
                     width="stretch", column_config={
                         "Component": "Komponent",
                         "SubScore": st.column_config.ProgressColumn("Ball (0-100)", min_value=0,
                                                                     max_value=100, format="%.0f"),
                         "Weight": PCT("Vazn", format="percent"),
                         "Points": PCT("Hissa", format="%.1f")})
        st.caption("Har bir komponent «eng yomon → eng yaxshi» mezon oralig'ida 0-100 ballga "
                   "o'tkaziladi va vaznga ko'paytiriladi. Mezon va vaznlar config.py faylida.")
    an = m.anomalies(d)
    with st.expander(f"Aniqlangan anomaliyalar ({len(an)})"):
        if len(an):
            st.dataframe(an.drop(columns=["SemesterKey", "Z", "Type"]).rename(columns={
                "What": "Nima bo'ldi", "Where": "Qayerda", "When": "Qachon", "Before": "Oldin",
                "After": "Keyin", "Change": "O'zgarish",
                "PossibleReason": "Ehtimoliy sabab (tekshirish uchun)"}), hide_index=True, width="stretch")
        else:
            st.write("Anomaliya aniqlanmadi.")
    ui.synthetic_note()


# ------------------------------------------------------------------ 2. faculty
def faculty(d):
    ui.header("Fakultetlar", "Fakultetlar taqqoslamasi, salomatlik bali bo'yicha tartiblangan")
    fs = m.faculty_summary(d)
    table = fs[["Rank", "FacultyName", "Students", "AvgGPA", "AttendanceRate", "FailureRate",
                "HighRiskShare", "HealthScore"]].rename(columns={
                    "Rank": "O'rin", "FacultyName": "Fakultet", "Students": "Talabalar",
                    "AvgGPA": "O'rtacha GPA", "AttendanceRate": "Davomat",
                    "FailureRate": "Fandan yiqilish", "HighRiskShare": "Xavf ostida",
                    "HealthScore": "Salomatlik bali"})
    st.dataframe(
        ui.shade(table, ["Fandan yiqilish", "Xavf ostida"], {
            "Talabalar": "{:,.0f}", "O'rtacha GPA": "{:.2f}", "Davomat": "{:.1%}",
            "Fandan yiqilish": "{:.1%}", "Xavf ostida": "{:.1%}", "Salomatlik bali": "{:.0f}"}),
        hide_index=True, width="stretch")
    st.caption("Yorqinroq rang - yuqoriroq yiqilish yoki xavf ulushi.")
    ui.export_buttons(table, f"fakultetlar_{st.session_state.semester_label.replace(' ', '_')}", "faculty")
    weak = fs.sort_values("HighRiskShare", ascending=False).iloc[0]
    st.markdown(f"**Eng ko'p e'tibor talab qiladigan fakultet:** {weak.FacultyName} - xavf ostidagilar "
                f"{ui.pct(weak.HighRiskShare)}, o'rtacha GPA {weak.AvgGPA:.2f}, "
                f"fandan yiqilish {ui.pct(weak.FailureRate)}.")

    options = {"O'rtacha GPA": ("AvgGPA", False), "Davomat": ("AttendanceRate", True),
               "Fandan yiqilish": ("FailureRate", True)}
    st.subheader("Bitta fakultet, qolganlar fonida")
    names = list(fs.sort_values("FacultyKey").FacultyName)
    c0, c1, c2 = st.columns([3, 4, 2])
    name = c0.selectbox("Fakultet", names, index=names.index(weak.FacultyName))
    fk = int(fs.loc[fs.FacultyName == name, "FacultyKey"].iloc[0])
    choice = c1.segmented_control("Ko'rsatkich", list(options), default="O'rtacha GPA") or "O'rtacha GPA"
    current = "Kuz" if d["latest"] % 2 == 0 else "Bahor"
    season = c2.segmented_control("Semestr", ["Kuz", "Bahor"], default=current,
                                  help="Kuz va Bahorda fanlar turlicha, shuning uchun bir xil semestrlar "
                                       "solishtiriladi.") or current
    col, percent = options[choice]
    trend = m.faculty_trend(d)
    trend = trend[trend.SemesterKey % 2 == (0 if season == "Kuz" else 1)]
    ui.show(ui.faculty_lines(trend, d, col, f"{choice} - {season} semestrlari, yildan yilga",
                             percent=percent, highlight=fk))
    st.caption("Yorqin chiziq - tanlangan fakultet, xira chiziqlar - qolgan fakultetlar "
               "(nomini ko'rish uchun grafik ustiga boring).")

    st.subheader(f"{name}: fanlar va guruhlar")
    c1, c2 = st.columns(2)
    with c1:
        cs = m.course_summary(d, -1)
        cs = cs[(cs.FacultyKey == fk) & (cs.Enrollment >= 30)].nlargest(7, "FailureRate")
        g = m.exam_by(d, d["latest"], "group")
        g = g[(g.FacultyKey == fk) & (g.N >= 20)].nlargest(7, "FailureRate")
        tall = ui.bar_h_height(cs, g)
        ui.show(ui.bar_h(cs, "FailureRate", "CourseName", "Eng qiyin fanlar (yiqilish ulushi)",
                         percent=True, height=tall))
    with c2:
        ui.show(ui.bar_h(g, "FailureRate", "GroupName", "Yiqilish eng yuqori guruhlar", percent=True,
                         height=tall))
    ui.synthetic_note()


# -------------------------------------------------------------------- 3. exams
def exams(d):
    ui.header("Imtihon natijalari", "Oraliq va yakuniy nazorat tahlili", chip=False)
    st.caption(f"Baholash tizimi: joriy nazorat {MX['current']} ball + oraliq nazorat {MX['midterm']} ball + "
               f"yakuniy nazorat {MX['final']} ball = 100. O'tish bali {config.PASS_MARK}. "
               f"Sababsiz qoldirilgan darslar {config.MAX_UNEXCUSED_ABSENCE:.0%} dan oshsa, talaba yakuniy "
               "nazoratga qo'yilmaydi.")
    _, own = _scope()
    sems = d["semesters"].sort_values("SemesterKey", ascending=False)
    c1, c2 = st.columns(2)
    sem = c1.selectbox("Semestr", list(sems.SemesterKey),
                       format_func=dict(zip(sems.SemesterKey, sems.SemesterLabel)).get)
    fac_names = dict(zip(d["faculties"].FacultyKey, d["faculties"].FacultyName))
    if own:
        fk = own
        c2.selectbox("Fakultet", [fac_names[own]], disabled=True)
    else:
        pick = c2.selectbox("Fakultet", ["Barcha fakultetlar"] + list(fac_names.values()))
        fk = next((int(key) for key, v in fac_names.items() if v == pick), None)

    def result(semester):
        """Exam figures of the current selection for one semester (None if no data)."""
        if not (d["exam_group"].SemesterKey == semester).any():
            return None
        if fk:
            t = m.exam_by(d, semester, "faculty").set_index("FacultyKey")
            return t.loc[fk] if fk in t.index else None
        return m.exam_by(d, semester, "university").iloc[0]

    cur, prev = result(sem), result(sem - 2)
    if cur is None:
        return st.warning("Tanlangan semestr uchun ma'lumot yo'q.")

    def delta(col):
        return None if prev is None else f"{(cur[col] - prev[col]) * 100:+.1f} f.p."

    c = st.columns(4)
    ui.kpi(c[0], "Oraliq nazorat", ui.pct(cur.MidtermPct), delta("MidtermPct"),
           help=f"O'rtacha {cur.Midterm:.1f} / {MX['midterm']} ball. O'tganlar: {ui.pct(cur.MidtermPassRate)}.")
    ui.kpi(c[1], "Yakuniy nazorat", ui.pct(cur.FinalPct), delta("FinalPct"),
           help=f"O'rtacha {cur.FinalAdmitted:.1f} / {MX['final']} ball, faqat qo'yilgan talabalar. "
                f"O'tganlar: {ui.pct(cur.FinalPassRate)}.")
    ui.kpi(c[2], "Qo'yilmaganlar", ui.pct(cur.NotAdmittedRate), delta("NotAdmittedRate"),
           inverse=True, help=f"{ui.num(cur.NotAdmitted)} ta fan natijasi (davomat qoidasi).")
    ui.kpi(c[3], "Yiqilganlar", ui.pct(cur.FailureRate), delta("FailureRate"), inverse=True,
           help=f"{ui.num(cur.Failed)} ta natija {config.PASS_MARK} balldan past.")
    gap = cur.ExamGap * 100
    st.markdown(
        f"Yakuniy nazorat natijasi oraliq nazoratdan **{abs(gap):.1f} foiz punkt "
        f"{'past' if gap < 0 else 'yuqori'}**. Oraliq nazoratdan o'tgan, lekin fandan yiqilgan natijalar: "
        f"**{ui.pct(cur.LostAfterMidterm)}** - bu talabalarni yakuniy nazoratgacha qo'llab-quvvatlash mumkin edi.")

    dist = m.exam_distribution(d, sem, fk)
    fig = go.Figure()
    bands = dist["hist"].Band.str.replace("%", "", regex=False)
    for col, label, color in [("Midterm", "Oraliq nazorat", ui.SERIES[0]),
                              ("Final", "Yakuniy nazorat", ui.SERIES[1])]:
        fig.add_bar(x=bands, y=dist["hist"][col], name=label, marker=dict(color=color, cornerradius=6),
                    hovertemplate=f"{label}<br>%{{x}}%: %{{y:.1%}}<extra></extra>")
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08)
    fig = ui.style(fig, 320, "y", title="Natijalar taqsimoti: talabalar ulushi, natija oralig'i bo'yicha "
                                        "(maksimal balldan %)")
    fig.update_xaxes(type="category")
    ui.show(fig)

    c1, c2 = st.columns([2, 3])
    with c1:
        grades = pd.DataFrame({
            "Baho": [config.GRADE_NAMES[g] for g in ("5", "4", "3", "2")],
            "Ulush": [cur.N5 / cur.N, cur.N4 / cur.N, cur.N3 / cur.N, cur.Failed / cur.N]})
        ui.show(ui.bar_h(grades, "Ulush", "Baho", "Yakuniy baholar", percent=True, height=GRADES_H,
                         colors=ui.GRADE_COLORS))
    with c2:
        st.markdown("**Oraliq nazoratdan yakuniy nazoratgacha**")
        flow = dist["flow_share"].copy()
        flow.columns = [f"Yakuniy: {col}" for col in flow.columns]
        flow.insert(0, "Natijalar soni", dist["flow"].sum(axis=1))
        flow.index.name = "Oraliq nazorat natijasi"
        flow = flow.reset_index()
        bad = [f"Yakuniy: 60% dan past", f"Yakuniy: {NOT_ADMITTED}"]
        st.dataframe(ui.shade(flow, bad, {"Natijalar soni": "{:,.0f}",
                                          **{col: "{:.1%}" for col in flow.columns[2:]}}),
                     hide_index=True, width="stretch", height=GRADES_H - 42)   # 42: the title above
        low = dist["flow_share"].loc["60% dan past"]
        st.caption(f"Qator bo'yicha o'qiladi. Oraliq nazoratda 60% dan past olganlarning "
                   f"{ui.pct(low['60% dan past'] + low[NOT_ADMITTED])} qismi yakuniy nazoratdan ham o'ta "
                   "olmagan yoki unga qo'yilmagan: oraliq nazorat - erta ogohlantirish belgisi.")

    c1, c2 = st.columns(2)
    with c1:
        if fk:
            g = d["exam_group"][d["exam_group"].FacultyKey == fk].groupby(
                "SemesterKey")[m._EXAM_COLS].sum().reset_index()
            tr = m.exam_rates(g).merge(d["semesters"][["SemesterKey", "SemesterLabel"]],
                                       on="SemesterKey").sort_values("SemesterKey")
        else:
            tr = m.exam_by(d, None, "semester")
        tr = tr[tr.SemesterKey % 2 == sem % 2]      # same season only: comparable courses
        season = "Kuz" if sem % 2 == 0 else "Bahor"
        ui.show(_lines(tr, "SemesterLabel", [("MidtermPct", "Oraliq nazorat"),
                                             ("FinalPct", "Yakuniy nazorat")],
                       f"O'rtacha natija, {season} semestrlari"))
    with c2:
        courses = m.exam_by(d, sem, "course")
        courses = courses[courses.N >= config.ALERTS["min_course_enrollment"]]
        if fk:
            courses = courses[courses.FacultyKey == fk]
        worst = courses.nsmallest(8, "ExamGap").assign(Gap=lambda x: -x.ExamGap)
        ui.show(ui.bar_h(worst, "Gap", "CourseName",
                         "Yakuniy nazorat oraliqdan eng ko'p pasaygan fanlar", percent=True, height=300))

    with st.expander("Batafsil jadval: fakultet, guruh, fan va o'qituvchi kesimida"):
        views = {"Fakultetlar": "faculty", "Guruhlar": "group", "Fanlar": "course",
                 "O'qituvchilar": "teacher"}
        view = st.segmented_control("Kesim", list(views), default="Fanlar",
                                    label_visibility="collapsed") or "Fanlar"
        t = m.exam_by(d, sem, views[view])
        if fk and "FacultyKey" in t:
            t = t[t.FacultyKey == fk]
        t = t[t.N >= (20 if view == "Guruhlar" else 30)].sort_values("FailureRate", ascending=False)
        label = {"faculty": ["FacultyName"], "group": ["GroupName", "FacultyName"],
                 "course": ["CourseName", "FacultyName"],
                 "teacher": ["TeacherName", "DepartmentName"]}[views[view]]
        names = {"FacultyName": "Fakultet", "GroupName": "Guruh", "CourseName": "Fan",
                 "TeacherName": "O'qituvchi", "DepartmentName": "Kafedra", "N": "Natijalar",
                 "MidtermPct": "Oraliq", "FinalPct": "Yakuniy", "ExamGap": "Farq",
                 "NotAdmittedRate": "Qo'yilmagan", "FailureRate": "Yiqilgan", "ExcellentRate": "A'lo (5)"}
        t = t[label + ["N", "MidtermPct", "FinalPct", "ExamGap", "NotAdmittedRate", "FailureRate",
                       "ExcellentRate"]].rename(columns=names)
        st.dataframe(
            ui.shade(t, ["Qo'yilmagan", "Yiqilgan"], {
                "Natijalar": "{:,.0f}", "Oraliq": "{:.1%}", "Yakuniy": "{:.1%}", "Farq": "{:+.1%}",
                "Qo'yilmagan": "{:.1%}", "Yiqilgan": "{:.1%}", "A'lo (5)": "{:.1%}"}),
            hide_index=True, width="stretch", height=360)
        st.caption("Farq - yakuniy minus oraliq nazorat. Yorqinroq rang - yuqoriroq ulush."
                   + (" Ko'rsatkichlar fan qiyinligi va talabalar tarkibiga bog'liq; bu o'qituvchini "
                      "baholash emas." if view == "O'qituvchilar" else ""))
    ui.synthetic_note()


# --------------------------------------------------------------------- 4. risk
def _model_trust(d):
    """One plain sentence on how reliable the list is, from the model's test semester."""
    mm = d["model_metrics"]
    test = mm[(mm.Split == "test") & (mm.Rule == "recall target")].sort_values("IsBest", ascending=False)
    if not len(test):
        return
    best = test.iloc[0]
    right, found = round(best.Precision * 10), round(best.Recall * 10)
    ui.callout("Ro'yxatga ishonch", (
        f"Model xavf ehtimoli {best.Threshold:.0%} va undan yuqori talabalarni belgilaydi. Sinov semestrida "
        f"belgilangan har 10 talabadan taxminan <b>{right} nafari</b> haqiqatan xavf ostida bo'lgan, "
        f"{10 - right} nafari esa bekorga belgilangan. Xavf ostidagi har 10 talabadan <b>{found} nafari</b> "
        f"ro'yxatga tushgan, {10 - found} nafari o'tkazib yuborilgan. Daraja qancha yuqori bo'lsa, "
        "bashorat shuncha ishonchli: ro'yxat - suhbat uchun asos, hukm emas."))


def _interventions(d, row, user):
    """What has been done for the selected student, and a form to record more."""
    st.markdown("**Ko'rilgan choralar**")
    if config.OFFLINE:
        return st.caption("Bu - namoyish nusxasi: choralar bu yerda saqlanmaydi. To'liq tizimda shu joyda "
                          "talaba uchun ko'rilgan choralar qayd etiladi va ularning natijasi kuzatiladi.")
    engine, key = ui.engine(), int(row.StudentKey)
    done = iv.for_student(engine, key)
    if len(done):
        shown = done.assign(Outcome=done.Outcome.fillna("")).set_index("InterventionID")
        edited = st.data_editor(
            shown, hide_index=True, width="stretch", key=f"iv_edit_{key}",
            disabled=["CreatedAt", "Type", "Note", "CreatedBy"],
            column_config={
                "CreatedAt": st.column_config.DatetimeColumn("Sana", format="DD.MM.YYYY HH:mm"),
                "Type": "Chora",
                "Status": st.column_config.SelectboxColumn("Holat", options=iv.STATUSES, required=True),
                "Outcome": st.column_config.SelectboxColumn("Natija", options=[""] + iv.OUTCOMES),
                "Note": "Izoh", "CreatedBy": "Kim yozgan"})
        changed = edited[(edited.Status != shown.Status) | (edited.Outcome.fillna("") != shown.Outcome)]
        if len(changed):
            for iid, r in changed.iterrows():
                iv.update(engine, int(iid), r.Status, r.Outcome or None, user)
            st.rerun()
        st.caption("Holat va natijani jadvalning o'zida o'zgartirish mumkin - u darhol saqlanadi.")
    else:
        st.caption("Bu talaba uchun hali chora qayd etilmagan.")
    with st.form(f"iv_add_{key}", border=False, clear_on_submit=True):
        c1, c2, c3 = st.columns([2, 4, 1], vertical_alignment="bottom")
        kind = c1.selectbox("Yangi chora", iv.TYPES)
        note = c2.text_input("Izoh", max_chars=1000, placeholder="Masalan: kurator bilan suhbat, 12-oktabr")
        if c3.form_submit_button("Qo'shish", type="primary", width="stretch"):
            iv.add(engine, key, int(d["latest"]), kind, note, user)
            st.rerun()


def risk(d):
    ui.header("Xavf ostidagi talabalar", "Keyingi semestr uchun bashorat va uning sabablari")
    st.caption("Model har bir faol talaba uchun keyingi semestrda akademik xavf ehtimolini baholaydi: "
               f"semestr GPA {config.AT_RISK_GPA:g} dan past, yoki {config.AT_RISK_FAILED} va undan ko'p "
               "fandan yiqilish, yoki o'qishni tark etish.")
    allowed, fk = _scope()
    t = m.risk_table(d)
    t = t if fk is None else t[t.FacultyKey == fk]

    counts = t.RiskLevel.value_counts().reindex(config.RISK_ORDER).fillna(0).astype(int)
    c = st.columns(4)
    for i, level in enumerate(config.RISK_ORDER):
        ui.kpi(c[i], f"{level} xavf", ui.num(counts[level]), help=f"Ulush: {ui.pct(counts[level] / len(t))}")
    _model_trust(d)

    if not allowed:
        by_fac = t.assign(High=t.RiskLevel.isin(m.HIGH_RISK)).groupby(
            ["FacultyKey", "FacultyName"])["High"].mean().reset_index().sort_values("High", ascending=False)
        ui.show(ui.bar_h(by_fac, "High", "FacultyName", "Yuqori/kritik xavfdagilar ulushi", percent=True))
        return _no_student_access()

    c1, c2, c3 = st.columns(3)
    levels = c1.multiselect("Xavf darajasi", config.RISK_ORDER, default=["Kritik", "Yuqori"])
    facs = c2.multiselect("Fakultet", sorted(t.FacultyName.unique()))
    query = c3.text_input("Qidirish (ism, guruh yoki ID)", placeholder="Masalan: Karimov, IQ-23-04")
    status = iv.latest_by_student(ui.engine()).set_index("StudentKey").Status
    t = t.assign(Chora=t.StudentKey.map(status).fillna(NO_ACTION))
    untouched = st.toggle("Faqat hali chora ko'rilmagan talabalar", key="risk_untouched")
    view = t[t.RiskLevel.isin(levels or config.RISK_ORDER)]
    if untouched:
        view = view[view.Chora == NO_ACTION]
    if facs:
        view = view[view.FacultyName.isin(facs)]
    if query.strip():
        q = query.strip().lower()
        view = t[t.FullName.str.lower().str.contains(q, regex=False)
                 | t.GroupName.str.lower().str.contains(q, regex=False)
                 | (t.StudentKey.astype(str) == q)]
    view = view.head(500)
    cols = {"StudentKey": "ID", "FullName": "Talaba", "GroupName": "Guruh", "FacultyName": "Fakultet",
            "RiskProbability": "Xavf ehtimoli", "RiskLevel": "Daraja", "SemGPA": "GPA",
            "AttendanceRate": "Davomat", "FailedCourses": "Yiqilgan fanlar", "Chora": "Chora",
            "MainFactors": "Asosiy omillar"}
    shown = view[list(cols)].rename(columns=cols)
    event = st.dataframe(
        ui.shade(shown, [], {"Xavf ehtimoli": "{:.0%}", "GPA": "{:.2f}", "Davomat": "{:.0%}"},
                 tag="Daraja"),
        hide_index=True, width="stretch", height=300, on_select="rerun",
        selection_mode="single-row", key="risk_table")
    st.caption(f"{len(view):,} ta talaba, shundan {int((view.Chora != NO_ACTION).sum()):,} tasi uchun chora "
               "qayd etilgan. Tafsilotni ko'rish uchun qatorni tanlang.")
    ui.export_buttons(shown, f"xavf_ostidagi_talabalar_{st.session_state.semester_label.replace(' ', '_')}",
                      "risk")
    rows = event.selection.rows if event and event.selection else []
    if not len(view):
        return ui.synthetic_note()
    row = view.iloc[rows[0] if rows and rows[0] < len(view) else 0]

    # everything about the selected student in one card
    with st.container(border=True):
        st.markdown(
            f'<div class="ui-profile"><span class="name">{row.FullName}</span>'
            f'<span class="ui-pill" style="{ui.RISK_TAG[row.RiskLevel]}">'
            f'{row.RiskLevel} xavf · {row.RiskProbability:.0%}</span>'
            f'<span class="meta">{row.GroupName} · {row.FacultyName} · {int(row.StudyYear)}-kurs · '
            f'{row.TuitionStatus}</span></div>', unsafe_allow_html=True)
        p = m.student_profile(d, ui.engine(), int(row.StudentKey))
        hist = p["history"]
        c = st.columns(4)
        ui.kpi(c[0], "Semestr GPA", f"{row.SemGPA:.2f}",
               None if len(hist) < 2 else f"{hist.SemGPA.iloc[-1] - hist.SemGPA.iloc[-2]:+.2f}")
        ui.kpi(c[1], "Davomat", ui.pct(row.AttendanceRate))
        ui.kpi(c[2], "Yiqilgan fanlar", f"{int(row.FailedCourses)}",
               help=f"Jami: {int(row.CumFailedCourses)}")
        ui.kpi(c[3], "Keyingi GPA bashorati", f"{row.PredictedNextGPA:.2f}")
        c1, c2 = st.columns(2)
        with c1:
            f = pd.DataFrame({"Omil": list(rm.GROUP_COLUMNS),
                              "Ulush": [row[col] / 100 for col in rm.GROUP_COLUMNS.values()]})
            f = f[f.Ulush > 0].sort_values("Ulush", ascending=False)
            ui.show(ui.bar_h(f, "Ulush", "Omil", "Nima uchun xavf yuqori (omillar ulushi)",
                             percent=True, height=260))
        with c2:
            ui.show(ui.line(hist, "SemesterLabel", "SemGPA", "Semestr GPA dinamikasi", height=260))
        g = p["grades"][p["grades"].SemesterKey == p["grades"].SemesterKey.max()]
        st.dataframe(g.drop(columns=["SemesterLabel", "SemesterKey"]).rename(columns={
            "CourseName": "Fan", "TeacherName": "O'qituvchi", "CurrentScore": f"Joriy ({MX['current']})",
            "MidtermScore": f"Oraliq ({MX['midterm']})", "FinalScore": f"Yakuniy ({MX['final']})",
            "TotalScore": "Jami", "FinalGrade": "Baho", "AttendanceScore": "Davomat, %",
            "Admitted": "Yakuniyga qo'yilgan"}), hide_index=True, width="stretch")
        st.caption("Omillar ulushi: omil qiymatlari xavf ostida bo'lmagan tipik talaba qiymatlari bilan "
                   "almashtirilganda model bashorati qanchaga kamayishi. Ehtimollik - baho, kafolat emas.")
        _interventions(d, row, st.session_state.auth_user)

    mm = d["model_metrics"]
    if len(mm):
        with st.expander("Model qanchalik ishonchli"):
            test = mm[(mm.Split == "test") & (mm.Rule == "recall target")].sort_values(
                "IsBest", ascending=False)
            best = test.iloc[0]
            st.markdown(
                f"Tanlangan model: **{best.Model}**. U eski semestrlarda o'qitilib, keyingi semestrda "
                f"sinalgan. Xavf ostidagi talabalarning **{best.Recall:.0%}** qismini topadi (recall); "
                f"belgilanganlarning **{best.Precision:.0%}** qismi haqiqatan xavf ostida (precision).\n\n"
                f"Faqat accuracy yetarli emas: talabalarning ko'pchiligi xavf ostida emas, shuning uchun "
                f"hech kimni belgilamaydigan model ham «aniq» ko'rinadi. Eng qimmat xato - **False "
                f"Negative** ({int(best.FN):,} ta): model o'tkazib yuborgan, yordamsiz qoladigan talaba.")
            st.dataframe(test[["Model", "Accuracy", "Precision", "Recall", "F1", "ROC_AUC"]],
                         hide_index=True, width="stretch", column_config={
                             col: PCT(format="%.3f") for col in
                             ["Accuracy", "Precision", "Recall", "F1", "ROC_AUC"]})
    ui.synthetic_note()


# --------------------------------------------------------------------- 7. more
def more(d, data_quality):
    ui.header("Boshqa ko'rsatkichlar", "Moliya, o'qituvchilar va ma'lumotlar sifati")
    tab_fin, tab_teach, tab_dq = st.tabs(["Moliya", "O'qituvchilar", "Ma'lumotlar sifati"])

    with tab_fin:
        pay, latest = d["payments"], d["latest"]
        cur = pay[pay.SemesterKey == latest][["Tuition", "Paid", "Debt"]].sum()
        c = st.columns(4)
        ui.kpi(c[0], "Hisoblangan kontrakt, so'm", ui.money(cur.Tuition))
        ui.kpi(c[1], "To'langan, so'm", ui.money(cur.Paid))
        ui.kpi(c[2], "Qarzdorlik, so'm", ui.money(cur.Debt))
        ui.kpi(c[3], "Yig'ilish darajasi", ui.pct(cur.Paid / cur.Tuition))
        c1, c2 = st.columns(2)
        with c1:
            by_fac = pay[pay.SemesterKey == latest].merge(d["faculties"], on="FacultyKey")
            by_fac = by_fac.assign(DebtB=by_fac.Debt / 1e9).sort_values("DebtB", ascending=False)
            colors = ui.faculty_color(d)
            debt_risk = m.risk_vs_debt(d)
            tall = ui.bar_h_height(by_fac, debt_risk)
            ui.show(ui.bar_h(by_fac, "DebtB", "FacultyName", "Fakultetlar bo'yicha qarzdorlik (mlrd so'm)",
                             colors=[colors[int(x)] for x in by_fac.FacultyKey], height=tall))
        with c2:
            ui.show(ui.bar_h(debt_risk, "AtRiskShare", "DebtBand",
                             "Akademik xavf ostidagilar ulushi (qarz guruhlari bo'yicha)", percent=True,
                             height=tall))
        st.caption("Qarzi katta talabalar orasida akademik xavf ko'proq uchraydi. Bu bog'liqlik: qarz past "
                   "natijaga sabab bo'ladi degan xulosa emas.")

    with tab_teach:
        ts = m.teacher_summary(d, d["latest"])
        c = st.columns(3)
        ui.kpi(c[0], "Dars bergan o'qituvchilar", ui.num(len(ts)))
        ui.kpi(c[1], "Median yuklama", f"{ts.Students.median():.0f} talaba")
        ui.kpi(c[2], "Ortiqcha yuklangan", ui.num(ts.Overloaded.sum()),
               help=f"Semestrda {config.TEACHER_OVERLOAD_STUDENTS} dan ortiq talaba.")
        st.dataframe(
            ts.sort_values("Students", ascending=False)[[
                "TeacherName", "DepartmentName", "Courses", "Students", "AvgGPA", "AttendanceRate",
                "FailureRate", "Overloaded"]], hide_index=True, width="stretch", height=420,
            column_config={
                "TeacherName": "O'qituvchi", "DepartmentName": "Kafedra", "Courses": "Fanlar",
                "Students": PCT("Talabalar", format="%d"),
                "AvgGPA": PCT("Talabalar GPA", format="%.2f"),
                "AttendanceRate": PCT("Davomat", format="percent"),
                "FailureRate": PCT("Yiqilish", format="percent"),
                "Overloaded": st.column_config.CheckboxColumn("Ortiqcha yuklama")})
        r = float(np.corrcoef(ts.Students, ts.AvgGPA)[0, 1])
        st.caption(f"Bu jadval o'qituvchini baholamaydi: ko'rsatkichlar fan qiyinligi va talabalar tarkibiga "
                   f"bog'liq. Yuklama va GPA korrelyatsiyasi r = {r:+.2f} (sabab-oqibat emas).")

    with tab_dq:
        data_quality(d)
