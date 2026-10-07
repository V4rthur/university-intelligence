"""Dashboard pages 9-11: what-if simulation, AI agent, data quality and refresh."""
import subprocess
import sys

import pandas as pd
import streamlit as st

import config
import metrics as m
import risk_model as rm
import scenarios as sc
import ui
from agent import OFFLINE_QUESTIONS, UniversityAgent, has_credentials, offline_answer
from agent_tools import ROLES, Toolbox


@st.cache_resource(show_spinner="Model yuklanmoqda...")
def _simulation(version: str):
    bundle = rm.load_bundle()
    return sc.population(ui.engine(), bundle), bundle


# ---------------------------------------------------------------- 9. scenarios
def scenarios(d):
    ui.header("«Agar...» ssenariylari", "Qaror ta'sirini oldindan baholash")
    st.caption("Rahbariyat qaror qabul qilishdan oldin uning kutilayotgan ta'sirini sinab ko'radi. "
               "Tutqichlar o'zgartiriladi, so'ng o'qitilgan modellar keyingi semestr natijalarini "
               "qayta bashorat qiladi.")
    pop, bundle = _simulation(st.session_state.get("data_version", ""))

    titles = {k: v["title"] for k, v in sc.SCENARIOS.items()} | {"custom": "Maxsus ssenariy (o'zim sozlayman)"}
    c1, c2 = st.columns([3, 2])
    key = c1.selectbox("Ssenariy", list(titles), format_func=titles.get)
    fac = c2.selectbox("Qamrov", ["Butun universitet"] + list(d["faculties"].FacultyName))
    fk = None if fac == "Butun universitet" else int(
        d["faculties"].loc[d["faculties"].FacultyName == fac, "FacultyKey"].iloc[0])

    if key == "custom":
        targets = {"all": "Barcha talabalar", "high_risk": "Yuqori va kritik xavfdagilar",
                   "top_risk": "Xavfi eng yuqori ulush"}
        c = st.columns(3)
        target = c[0].selectbox("Kimga ta'sir qiladi", list(targets), format_func=targets.get)
        share = c[1].slider("Ulush (faqat «eng yuqori ulush» uchun)", 5, 60, 30, 5,
                            format="%d%%", disabled=target != "top_risk") / 100
        c = st.columns(4)
        att = c[0].slider("Davomat (f.p.)", -15, 15, 0) / 100
        sub = c[1].slider("Topshiriq topshirish (f.p.)", -20, 20, 0) / 100
        asg = c[2].slider("Topshiriq bali (ball)", -15, 15, 0)
        load = c[3].slider("O'qituvchi yuklamasi (%)", -30, 30, 0) / 100
        res = sc.simulate(pop, bundle, title=titles[key], target=target, share=share, faculty_key=fk,
                          assumptions="Foydalanuvchi belgilagan tutqichlar.", attendance=att,
                          submission=sub, assignment_score=asg, teacher_load_pct=load)
    else:
        res = sc.run_scenario(pop, bundle, key, faculty_key=fk)

    st.subheader(res["title"])
    st.markdown(f"**Faraz:** {res['assumptions']}  \n**Ta'sir doirasi:** "
                f"{ui.num(res['affected'])} / {ui.num(res['students'])} faol talaba")
    t = res["table"]
    cols = st.columns(3)
    for i, r in enumerate(t.itertuples()):
        if "%" in r.Format:
            delta = f"{r.Change * 100:+.2f} f.p."
        elif "," in r.Format:
            delta = f"{r.Change:+,.0f}"
        else:
            delta = f"{r.Change:+.2f}"
        higher_is_better = r.Key in ("predicted_gpa", "retention", "graduation_probability")
        ui.kpi(cols[i % 3], r.Outcome, r.Format.format(r.Scenario), delta,
               inverse=not higher_is_better, help=f"Hozirgi holat: {r.Format.format(r.Baseline)}")
    st.dataframe(sc.format_table(res), hide_index=True, width="stretch")

    gpa = t.loc[t.Key == "predicted_gpa", "Change"].iloc[0]
    risk = t.loc[t.Key == "at_risk_students", "Change"].iloc[0]
    if abs(gpa) < 0.015 and abs(risk) < 0.005 * res["students"]:
        st.info("O'zgarish model xatoligi doirasida: ma'lumotlarda bu tutqich va natijalar o'rtasida "
                "sezilarli bog'liqlik kuzatilmagan. Bunday chora o'z-o'zidan akademik natijani "
                "o'zgartirishi kutilmaydi.")
    with st.expander("Simulyatsiya qanday ishlaydi va uning chegaralari"):
        lv = bundle["levers"]["SemGPA"]
        st.markdown(
            "1. Har bir faol talabaning oxirgi semestr ko'rsatkichlari olinadi.\n"
            "2. Ssenariy tutqichlari (davomat, topshiriq, yuklama) tanlangan talabalar uchun o'zgartiriladi.\n"
            "3. O'zgarish shu semestr GPA va yiqilgan fanlarga talabaning o'z tarixidan baholangan "
            "bog'liqlik orqali o'tkaziladi "
            f"(masalan, davomat +10 f.p. ↔ GPA {lv['AttendanceRate'] * 0.1:+.2f}).\n"
            "4. Xavf, GPA, yiqilish va o'qishni tark etish modellari keyingi semestrni qayta bashorat qiladi.\n\n"
            f"**Chegaralar:** {res['note']} Dasturlarning ta'sir kuchi (masalan, tyutorlik topshiriq balini "
            "necha ballga oshirishi) - faraz; uni tajriba (pilot) natijalari bilan almashtirish kerak. "
            "Bitirish ehtimoli har semestrdagi tark etish ehtimoli o'zgarmaydi degan soddalashtirishga tayanadi.")
    ui.synthetic_note()


# -------------------------------------------------------------------- 10. agent
def agent(d):
    ui.header("AI yordamchi", "Savolni oddiy tilda bering - javob ombor va model natijalaridan olinadi")
    role = st.session_state.get("role", "oqituvchi")
    fac_name = st.session_state.get("own_faculty_name") if role == "dekan" else None
    st.caption(f"Rol: **{ROLES[role]['label']}**" + (f" · {fac_name}" if fac_name else "") +
               " · Yordamchi faqat ma'lumotlar ombori, tahlil qatlami, ML modeli va simulyatsiya "
               "vositalaridan olingan natijalarga tayanadi.")

    sig = (role, fac_name, st.session_state.get("data_version"))
    if st.session_state.get("agent_sig") != sig:
        st.session_state.agent_sig = sig
        st.session_state.toolbox = Toolbox(ui.engine(), role=role, own_faculty=fac_name, data=d)
        st.session_state.agent = None
        st.session_state.chat = []
    toolbox, online = st.session_state.toolbox, has_credentials()

    if not online:
        st.warning("Claude API kaliti topilmadi (`ANTHROPIC_API_KEY`). Oflayn rejim: quyidagi tayyor "
                   "savollar bevosita vositalar natijasidan javob beradi. To'liq erkin savol-javob "
                   "uchun kalitni o'rnatib, dashboardni qayta ishga tushiring.")

    st.markdown("**Tayyor savollar**")
    cols = st.columns(3)
    preset = None
    for i, (key, question) in enumerate(OFFLINE_QUESTIONS.items()):
        if cols[i % 3].button(question, key=f"preset_{key}", width="stretch"):
            preset = (key, question)

    # before the first question, show what an answer looks like (built from live data)
    if not st.session_state.chat and preset is None:
        if st.session_state.get("agent_sample_sig") != sig:
            st.session_state.agent_sample_sig = sig
            st.session_state.agent_sample = offline_answer(toolbox, "overview")["text"]
        with st.container(border=True):
            st.caption("Namuna javob - joriy ma'lumotlar asosida")
            st.markdown(st.session_state.agent_sample)

    for msg in st.session_state.chat:
        with st.chat_message(msg["role"]):
            st.markdown(msg["text"])
            if msg.get("tools"):
                with st.expander(f"Foydalanilgan vositalar ({len(msg['tools'])})"):
                    st.dataframe(pd.DataFrame(msg["tools"]).astype(str), hide_index=True, width="stretch")

    typed = st.chat_input("Savolingizni yozing, masalan: Nega Iqtisodiyot fakulteti natijalari pasaymoqda?",
                          disabled=not online)
    question = typed or (preset[1] if preset else None)
    if not question:
        return
    st.session_state.chat.append({"role": "user", "text": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        if online:
            if st.session_state.agent is None:
                st.session_state.agent = UniversityAgent(toolbox)
            status = st.status("Ma'lumotlar tahlil qilinmoqda...", expanded=False)
            answer = st.session_state.agent.ask(
                question, on_tool=lambda name, args: status.write(f"Vosita: `{name}` {args or ''}"))
            status.update(label="Tahlil yakunlandi", state="complete")
        else:
            answer = offline_answer(toolbox, preset[0])
        st.markdown(answer["text"])
        if answer["tools"]:
            with st.expander(f"Foydalanilgan vositalar ({len(answer['tools'])})"):
                st.dataframe(pd.DataFrame(answer["tools"]).astype(str), hide_index=True, width="stretch")
    st.session_state.chat.append({"role": "assistant", "text": answer["text"], "tools": answer["tools"]})


# ------------------------------------------------------------- 11. data quality
def data_quality(d):
    q = m.data_quality(ui.engine())
    last = q["last_run"]
    c = st.columns(4)
    ui.kpi(c[0], "Ma'lumotlar sifati bali", ui.pct(q["score"], 2),
           help="1 − (muammoli yozuvlar / o'qilgan yozuvlar). Tuzatilgan va rad etilgan yozuvlar hisobga olinadi.")
    ui.kpi(c[1], "Jami o'qilgan yozuvlar", ui.num(q["total_rows"]))
    ui.kpi(c[2], "Rad etilgan (karantin)", ui.num(q["rejected"]))
    ui.kpi(c[3], "Oxirgi ETL", f"{last['FinishedAt']:%d.%m %H:%M}" if last else "-",
           help=last["Message"] if last else None)
    c = st.columns(4)
    ui.kpi(c[0], "Yetishmayotgan qiymatlar", ui.num(q["missing"]))
    ui.kpi(c[1], "Takroriy yozuvlar", ui.num(q["duplicates"]))
    ui.kpi(c[2], "Yaroqsiz yozuvlar", ui.num(q["invalid"]))
    ui.kpi(c[3], "Bog'lanish xatolari (orphan)", ui.num(q["orphans"]))

    names = {"whitespace_trimmed": "Ortiqcha bo'shliqlar", "duplicate": "Takroriy yozuvlar",
             "format_standardised": "Yozilish shakli standartlashtirildi",
             "type_corrected": "Ma'lumot turi tuzatildi", "missing_filled": "Bo'sh qiymat to'ldirildi",
             "missing_imputed": "Bo'sh ball mediana bilan to'ldirildi",
             "missing_required": "Majburiy maydon bo'sh", "invalid_category": "Noma'lum toifa",
             "invalid_number": "Son emas", "invalid_date": "Sana emas",
             "out_of_range": "Ruxsat etilgan oraliqdan tashqarida", "orphan_key": "Bog'lanish xatosi (orphan)"}
    actions = {"FIXED": "Tuzatildi", "REJECTED": "Rad etildi", "FLAGGED": "Belgilandi"}
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Tekshiruvlar bo'yicha")
        bc = q["by_check"].assign(
            Tekshiruv=lambda x: x.CheckName.map(lambda v: names.get(v, v.replace("outlier_", "Chetlanish: "))),
            Amal=lambda x: x.Action.map(actions))
        st.dataframe(bc[["Tekshiruv", "Amal", "IssueCount"]].rename(columns={"IssueCount": "Yozuvlar"}),
                     hide_index=True, width="stretch", height=330)
    with c2:
        st.subheader("Jadvallar bo'yicha")
        st.dataframe(
            q["by_table"][["TableName", "RowsRead", "RowsLoaded", "RowsRejected", "QualityScore"]],
            hide_index=True, width="stretch", height=330,
            column_config={
                "TableName": "Jadval", "RowsRead": st.column_config.NumberColumn("O'qildi", format="localized"),
                "RowsLoaded": st.column_config.NumberColumn("Yuklandi", format="localized"),
                "RowsRejected": st.column_config.NumberColumn("Rad etildi", format="localized"),
                "QualityScore": st.column_config.ProgressColumn("Sifat", min_value=0.9, max_value=1,
                                                                format="percent")})

    st.subheader("ETL ishga tushirishlar tarixi")
    runs = q["runs"][["RunID", "StartedAt", "FinishedAt", "Status", "FilesProcessed", "RowsRead",
                      "RowsLoaded", "RowsRejected", "Message"]]
    st.dataframe(runs.rename(columns={
        "StartedAt": "Boshlandi", "FinishedAt": "Tugadi", "Status": "Holat", "FilesProcessed": "Fayllar",
        "RowsRead": "O'qildi", "RowsLoaded": "Yuklandi", "RowsRejected": "Rad etildi",
        "Message": "Natija"}), hide_index=True, width="stretch", height=240)

    st.subheader("Ma'lumotlarni yangilash")
    st.markdown(
        "Yangi fayl `01_Data/raw` papkasiga tushganda konveyer faqat yangi yoki o'zgargan fayllarni "
        "o'qiydi, tozalaydi, omborga `MERGE` orqali qo'shadi (takror yuklash dublikat yaratmaydi) va "
        "talabalar xavfini qayta hisoblaydi. Dashboard yangi ma'lumotni 30 soniya ichida o'zi ko'rsatadi.")
    if config.OFFLINE:
        return st.caption("Bu - namoyish nusxasi: u saqlangan ma'lumot nusxasini ko'rsatadi, konveyer bu "
                          "yerdan ishga tushirilmaydi.")
    if st.session_state.get("role", "oqituvchi") != "rahbariyat":
        return st.caption("Konveyerni ishga tushirish faqat rahbariyat roli uchun ochiq.")
    c1, c2 = st.columns(2)
    run_args = None
    if c1.button("Yangi fayllarni yuklash (ETL + qayta baholash)", width="stretch"):
        run_args = []
    if c2.button("Yangi semestr kelishini simulyatsiya qilish", width="stretch",
                 help="Sintetik generator yana bir semestr ma'lumotini yaratadi, so'ng konveyer uni yuklaydi."):
        run_args = ["--new-semester"]
    if run_args is not None:
        with st.status("Konveyer ishlamoqda (1-3 daqiqa)...", expanded=True) as status:
            proc = subprocess.run([sys.executable, str(config.ROOT / "run_pipeline.py"), *run_args],
                                  capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  cwd=config.ROOT, env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
            st.code((proc.stdout or "")[-3500:] + (proc.stderr or "")[-1500:])
            status.update(label="Konveyer yakunlandi" if proc.returncode == 0 else "Konveyer xato bilan tugadi",
                          state="complete" if proc.returncode == 0 else "error")
        if proc.returncode == 0:
            st.rerun()
