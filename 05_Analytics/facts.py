"""Collect the headline facts of the current warehouse state in one dictionary.

Used by the presentation builder and by the findings document, so both always
quote the live numbers instead of figures typed by hand.

    python 05_Analytics/facts.py     # rewrites 10_Documentation/04_Natijalar_va_topilmalar.md
"""
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import metrics as m  # noqa: E402
import risk_model as rm  # noqa: E402
import scenarios as sc  # noqa: E402


def collect(engine=None) -> dict:
    engine = engine or config.get_engine()
    d = m.load_all(engine)
    k = m.kpis(d)
    score, detail = m.university_health(d)
    fs = m.faculty_summary(d)
    ft = m.faculty_trend(d)
    risk = m.risk_table(d)
    mm = d["model_metrics"]
    best = mm[(mm.IsBest == 1) & (mm.Split == "test") & (mm.Rule == "recall target")].iloc[0]
    models = mm[(mm.Split == "test") & (mm.Rule == "recall target")]

    bundle = rm.load_bundle()
    pop = sc.population(engine, bundle)
    scen = {}
    for key in sc.SCENARIOS:
        r = sc.run_scenario(pop, bundle, key)
        t = r["table"].set_index("Key")
        scen[key] = dict(title=r["title"], assumptions=r["assumptions"], affected=r["affected"],
                         d_gpa=float(t.loc["predicted_gpa", "Change"]),
                         d_risk=int(t.loc["at_risk_students", "Change"]),
                         d_high=int(t.loc["high_risk_students", "Change"]),
                         d_fail=float(t.loc["failure_rate", "Change"]),
                         d_grad=float(t.loc["graduation_probability", "Change"]))

    with engine.connect() as con:
        counts = dict(con.execute(text(
            "SELECT t.name, SUM(p.rows) FROM sys.tables t JOIN sys.partitions p "
            "ON p.object_id = t.object_id AND p.index_id IN (0, 1) "
            "WHERE SCHEMA_NAME(t.schema_id) = 'dw' GROUP BY t.name")).all())

    worst = fs.sort_values("HighRiskShare", ascending=False).iloc[0]
    same_sem = ft[(ft.FacultyKey == worst.FacultyKey)
                  & (ft.SemesterKey % 2 == d["latest"] % 2)].sort_values("SemesterKey")
    high = risk[risk.RiskLevel.isin(m.HIGH_RISK)]
    shares = high[list(rm.GROUP_COLUMNS.values())].mean()
    shares.index = list(rm.GROUP_COLUMNS)
    st = d["students"]
    an = m.anomalies(d)
    exam = m.exam_overview(d)
    low = m.exam_distribution(d, d["latest"])["flow_share"].loc["60% dan past"]
    exam["low_midterm_not_passed"] = float(low["60% dan past"] + low["Qo'yilmagan"])
    return {
        "data": d, "kpis": k, "health": score, "health_detail": detail, "faculties": fs,
        "risk_levels": risk.RiskLevel.value_counts().reindex(config.RISK_ORDER).fillna(0).astype(int),
        "best": best, "models": models, "scenarios": scen, "counts": counts,
        "fact_rows": int(sum(v for n, v in counts.items() if n.startswith("Fact"))),
        "students_total": int(len(st)), "dropped": int((st.Status == "Chetlashtirilgan").sum()),
        "teachers": int(len(d["teachers"])), "courses": int(len(d["courses"])),
        "worst_faculty": worst, "worst_gpa_trend": list(same_sem.AvgGPA.round(2)),
        "worst_trend_labels": list(same_sem.SemesterLabel),
        "factor_shares": shares.sort_values(ascending=False),
        # a critical-risk student whose risk is spread over several factors makes
        # the clearest illustration of an explanation
        "example": risk[risk.RiskProbability >= 0.8].sort_values("F_GPA").iloc[0],
        "alerts": m.alerts(d), "anomalies": an,
        "debt": m.risk_vs_debt(d), "quality": m.data_quality(engine), "exam": exam,
        "levers": bundle["levers"], "threshold": bundle["threshold"],
    }


def findings_markdown(f: dict) -> str:
    k, best, w, s = f["kpis"], f["best"], f["worst_faculty"], f["scenarios"]
    q, debt = f["quality"], f["debt"].set_index("DebtBand")
    lines = [
        "# Natijalar, topilmalar va tavsiyalar", "",
        f"_Avtomatik yaratilgan: `python 05_Analytics/facts.py`. Joriy semestr: **{k['semester']}**. "
        "Ma'lumotlar sintetik; bashoratlar ehtimollik bo'lib, kafolat emas._", "",
        "## Tizim hajmi", "",
        f"- Talabalar: {f['students_total']:,} (faol {k['total_students']:,}); o'qituvchilar: "
        f"{f['teachers']}; fanlar: {f['courses']}",
        f"- Ombordagi fakt yozuvlari: {f['fact_rows']:,}",
        f"- Ma'lumotlar sifati bali: {q['score']:.2%} ({q['total_rows']:,} yozuv o'qilgan, "
        f"{q['rejected']:,} tasi karantinga olingan, {q['duplicates']:,} dublikat olib tashlangan)", "",
        "## Asosiy ko'rsatkichlar", "",
        f"- Universitet salomatlik bali: **{f['health']:.1f} / 100**",
        f"- O'rtacha GPA: {k['avg_gpa']:.2f} · davomat: {k['attendance']:.1%} · "
        f"fanlardan yiqilish: {k['failure_rate']:.1%}",
        f"- Bitirish darajasi: {k['graduation_rate']:.1%} · semestrdan semestrga saqlanish: {k['retention']:.1%}",
        f"- To'lov yig'ilishi: {k['collection_rate']:.1%} · jami qarzdorlik: {k['outstanding_debt'] / 1e9:,.1f} mlrd so'm",
        f"- Yuqori yoki kritik xavfdagi talabalar: **{k['high_risk_students']:,}** "
        f"({k['high_risk_share']:.1%})", "",
        "## Imtihon natijalari", "",
        f"Baholash: joriy nazorat {config.SCORE_MAX['current']} + oraliq nazorat "
        f"{config.SCORE_MAX['midterm']} + yakuniy nazorat {config.SCORE_MAX['final']} = 100 ball; "
        f"o'tish bali {config.PASS_MARK}; baholar 5 / 4 / 3 / 2.", "",
        f"- Oraliq nazorat o'rtacha natijasi: {f['exam']['MidtermPct']:.1%} (o'tganlar "
        f"{f['exam']['MidtermPassRate']:.1%})",
        f"- Yakuniy nazorat o'rtacha natijasi: {f['exam']['FinalPct']:.1%} (qo'yilganlar orasida o'tganlar "
        f"{f['exam']['FinalPassRate']:.1%})",
        f"- Yakuniy nazoratga qo'yilmagan natijalar (davomat qoidasi): {f['exam']['NotAdmittedRate']:.1%}",
        f"- Baholar: 5 - {f['exam']['grades']['5'] / f['exam']['N']:.1%}, 4 - "
        f"{f['exam']['grades']['4'] / f['exam']['N']:.1%}, 3 - {f['exam']['grades']['3'] / f['exam']['N']:.1%}, "
        f"2 - {f['exam']['grades']['2'] / f['exam']['N']:.1%}",
        f"- Oraliq nazoratda 60% dan past olganlarning {f['exam']['low_midterm_not_passed']:.1%} qismi yakuniy "
        "nazoratdan ham o'ta olmagan yoki unga qo'yilmagan: oraliq nazorat - erta ogohlantirish belgisi.",
        f"- Oraliq nazoratdan o'tgan, lekin fandan yiqilgan natijalar: {f['exam']['LostAfterMidterm']:.1%}", "",
        "## Model sifati (keyingi semestrda sinov)", "",
        "| Model | Chegara | Accuracy | Precision | Recall | F1 | ROC-AUC |", "|---|---|---|---|---|---|---|",
    ]
    for r in f["models"].sort_values("IsBest", ascending=False).itertuples():
        mark = " (tanlangan)" if r.IsBest else ""
        lines.append(f"| {r.Model}{mark} | {r.Threshold:.3f} | {r.Accuracy:.3f} | {r.Precision:.3f} | "
                     f"{r.Recall:.3f} | {r.F1:.3f} | {r.ROC_AUC:.3f} |")
    lines += [
        "",
        f"Tanlangan model xavf ostidagi talabalarning {best.Recall:.0%} qismini topadi; {int(best.FN):,} tasi "
        f"o'tkazib yuborilgan (False Negative), {int(best.FP):,} tasi ortiqcha belgilangan (False Positive). "
        "Modellar orasidagi farq kichik - natija bitta algoritmga bog'liq emas.", "",
        "## Topilmalar", "",
        f"1. **{w.FacultyName} fakulteti eng yuqori xavf zonasida.** Yuqori/kritik xavfdagilar ulushi "
        f"{w.HighRiskShare:.1%} ({int(w.HighRiskStudents)} talaba), o'rtacha GPA {w.AvgGPA:.2f}, davomat "
        f"{w.AttendanceRate:.1%}. Shu semestr bo'yicha GPA yildan yilga: "
        f"{' → '.join(f'{v:.2f}' for v in f['worst_gpa_trend'])}.",
        f"2. **Xavfni asosan akademik tarix tushuntiradi.** Xavf ostidagi talabalarda omillar ulushi: "
        + ", ".join(f"{g} {v:.0f}%" for g, v in f["factor_shares"].head(4).items())
        + ". Davomat va qarzning mustaqil hissasi kichik, chunki ularning ta'siri GPA orqali allaqachon aks etgan.",
    ]
    n = 3
    for _, a in f["anomalies"].head(4).iterrows():
        lines.append(f"{n}. **Anomaliya - {a.Where}, {a.When}:** {a.What.lower()} ({a.Before} → {a.After}, "
                     f"{a.Change}). {a.PossibleReason}")
        n += 1
    hi, lo = debt.index[-1], "Qarzi yo'q"
    lines += [
        f"{n}. **Moliyaviy va akademik xavf birga uchraydi.** «{hi}» guruhida akademik xavf ostidagilar "
        f"{debt.loc[hi, 'AtRiskShare']:.1%}, «{lo}» guruhida {debt.loc[lo, 'AtRiskShare']:.1%}. "
        "Bu bog'liqlik, sabab-oqibat isboti emas.",
        f"{n + 1}. **O'qituvchi yuklamasi va natijalar o'rtasida sezilarli bog'liqlik topilmadi.** Yuklamani "
        f"10% kamaytirish ssenariysi GPA ni {s['teacher_load']['d_gpa']:+.2f} ga o'zgartiradi (model xatoligi doirasida).",
        "", "## Ssenariylar natijasi", "",
        "| Ssenariy | Ta'sir doirasi | GPA | Xavf ostidagilar | Yiqilish | Bitirish ehtimoli |",
        "|---|---|---|---|---|---|",
    ]
    for v in s.values():
        lines.append(f"| {v['title']} | {v['affected']:,} | {v['d_gpa']:+.2f} | {v['d_risk']:+,} | "
                     f"{v['d_fail'] * 100:+.2f} f.p. | {v['d_grad'] * 100:+.2f} f.p. |")
    t, i = s["tutoring_30"], s["risk_intervention"]
    lines += [
        "", "Farazlar har bir ssenariy uchun dashboardda ko'rsatilgan va sozlanadi.", "",
        "## Tavsiyalar (ustuvorlik tartibida)", "",
        f"1. **{w.FacultyName} fakultetida maqsadli akademik qo'llab-quvvatlash dasturini boshlash.** "
        f"Birinchi navbatda {int(w.HighRiskStudents)} nafar yuqori/kritik xavfdagi talaba bilan ishlash; "
        "eng qiyin fanlar bo'yicha qo'shimcha konsultatsiyalar.",
        f"2. **Xavfi eng yuqori 30% talabaga tyutorlik dasturini pilot sifatida sinash.** Model bahosi: xavf "
        f"ostidagilar {t['d_risk']:+,} talabaga, yiqilish darajasi {t['d_fail'] * 100:+.2f} f.p. ga o'zgaradi. "
        "Pilot natijasi simulyatsiya farazlarini haqiqiy raqam bilan almashtiradi.",
        f"3. **Yuqori va kritik xavfdagi talabalarga maslahatchi biriktirish.** Model bahosi: yuqori/kritik "
        f"guruh {i['d_high']:+,} talabaga o'zgaradi.",
        "4. **Anomaliya aniqlangan fan(lar)da imtihon materiallari va baholash mezonlarini ko'rib chiqish.**",
        "5. **Qarzi katta talabalar bilan moliyaviy maslahat va to'lov jadvalini moslashtirish** - akademik "
        "yordam bilan birga, chunki ikkala xavf bir guruhda to'planadi.",
        "6. **Har semestr yakunida ro'yxatni yangilash:** `python run_pipeline.py` - xavf qayta hisoblanadi.", "",
        "## Kutilayotgan ta'sir", "",
        "- Xavf ostidagi talabalar semestr yakunida emas, keyingi semestr boshlanishidan oldin aniqlanadi.",
        "- Qarorlar ta'siri oldindan raqam bilan baholanadi; resurslar eng katta samara kutilgan joyga yo'naltiriladi.",
        "- Rahbariyat, dekanat va o'qituvchilar bir xil, yagona manbadagi raqamlar bilan ishlaydi.",
        "- Haqiqiy samara faqat haqiqiy ma'lumot va pilot tajriba asosida tasdiqlanadi.", "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    facts = collect()
    out = config.DOCS_DIR / "04_Natijalar_va_topilmalar.md"
    out.write_text(findings_markdown(facts), encoding="utf-8")
    print(f"written {out.relative_to(config.ROOT)}")
