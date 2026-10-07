"""What-if scenario simulation (PHASE 9).

How a scenario is computed
    1. Take every active student's latest-semester feature row.
    2. Change the LEVERS the scenario is about (attendance, assignment
       submission, assignment score, teacher workload) for the targeted students.
    3. Propagate the change to the same-semester GPA and failed courses using
       the within-student associations estimated in 06_ML (bundle["levers"]).
    4. Ask the trained models for next-semester outcomes with and without the
       change and report the difference.

What this is - and is not
    This is a MODEL-BASED simulation on synthetic data. Steps 3 and 4 rest on
    associations learned from observational data; they are not proof that
    changing a lever causes the outcome to change by that amount. The lever
    sizes of the programmes (e.g. "tutoring raises assignment scores by 8
    points") are stated ASSUMPTIONS that management can adjust.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import risk_model as rm  # noqa: E402

HIGH_RISK = ("Yuqori", "Kritik")

# The five scenarios from the project brief. target: who is affected.
SCENARIOS = {
    "attendance_drop": dict(
        title="Davomat 5 foiz punktga pasaysa",
        target="all", attendance=-0.05,
        assumptions="Barcha faol talabalarning davomati 5 foiz punktga kamayadi."),
    "tutoring_30": dict(
        title="Talabalarning 30 foiziga tyutorlik dasturi berilsa",
        target="top_risk", share=0.30, assignment_score=8, submission=0.05, attendance=0.02,
        assumptions="Dastur xavfi eng yuqori 30% talabaga beriladi. Faraz: topshiriq bali +8, "
                    "topshirish ulushi +5 f.p., davomat +2 f.p."),
    "risk_intervention": dict(
        title="Xavf ostidagi talabalarga maqsadli aralashuv qilinsa",
        target="high_risk", attendance=0.05, submission=0.10,
        assumptions="Yuqori va kritik xavfdagi talabalar bilan maslahatchi ishlaydi. Faraz: "
                    "davomat +5 f.p., topshiriq topshirish ulushi +10 f.p."),
    "teacher_load": dict(
        title="O'qituvchi yuklamasi 10 foizga kamaytirilsa",
        target="all", teacher_load_pct=-0.10,
        assumptions="Har bir talabaning o'qituvchilari o'rtacha 10% kam talabaga dars beradi."),
    "assignment_completion": dict(
        title="Topshiriqlarni bajarish 15 foiz punktga oshsa",
        target="all", submission=0.15,
        assumptions="Barcha talabalarning topshiriq topshirish ulushi 15 f.p. ga oshadi "
                    "(100% dan oshmaydi)."),
}

OUTCOMES = [  # key, label, format, True if higher is better
    ("predicted_gpa", "Bashorat qilingan o'rtacha GPA", "{:.2f}", True),
    ("at_risk_students", "Xavf ostidagi talabalar (model belgilagan)", "{:,.0f}", False),
    ("high_risk_students", "Yuqori va kritik xavfdagi talabalar", "{:,.0f}", False),
    ("failure_rate", "Yiqilish darajasi", "{:.1%}", False),
    ("retention", "Keyingi semestrga saqlanish", "{:.2%}", True),
    ("graduation_probability", "O'rtacha bitirish ehtimoli", "{:.1%}", True),
]


def population(engine, bundle: dict | None = None) -> pd.DataFrame:
    """Active students' latest-semester features plus their baseline risk."""
    bundle = bundle or rm.load_bundle()
    _, pop = rm.build_dataset(rm.load_snapshot(engine))
    pop = pop.reset_index(drop=True)
    pop["BaseRisk"] = rm.predict(bundle, pop)["RiskProbability"].to_numpy()
    pop["BaseLevel"] = rm.risk_level(pop["BaseRisk"])
    return pop


def target_mask(pop: pd.DataFrame, target: str, share: float = 0.3,
                faculty_key: int | None = None) -> pd.Series:
    if target == "high_risk":
        mask = pop["BaseLevel"].isin(HIGH_RISK)
    elif target == "top_risk":
        mask = pop["BaseRisk"].rank(ascending=False, method="first") <= round(len(pop) * share)
    else:
        mask = pd.Series(True, index=pop.index)
    if faculty_key:
        mask &= pop["FacultyKey"] == faculty_key
    return mask


def apply_levers(pop: pd.DataFrame, mask: pd.Series, levers: dict, attendance: float = 0.0,
                 submission: float = 0.0, assignment_score: float = 0.0,
                 teacher_load_pct: float = 0.0) -> pd.DataFrame:
    X = pop.copy()
    before = X[rm.LEVERS].astype(float).copy()
    m = mask.to_numpy()

    X.loc[m, "AttendanceRate"] = (X.loc[m, "AttendanceRate"] + attendance).clip(0, 1)
    new_sub = (X.loc[m, "SubmissionRate"] + submission).clip(0, 1)
    # the assignment average counts work that was not handed in as 0, so it
    # rises in proportion when more assignments are submitted
    ratio = (new_sub / X.loc[m, "SubmissionRate"].replace(0, np.nan)).fillna(1.0)
    X.loc[m, "AvgAssignmentScore"] = (X.loc[m, "AvgAssignmentScore"] * ratio
                                      + assignment_score).clip(0, 100)
    X.loc[m, "SubmissionRate"] = new_sub
    X.loc[m, "AvgTeacherLoad"] = X.loc[m, "AvgTeacherLoad"] * (1 + teacher_load_pct)

    delta = X[rm.LEVERS].astype(float) - before
    d_gpa = sum(delta[c] * levers["SemGPA"][c] for c in rm.LEVERS)
    d_fail = sum(delta[c] * levers["FailRate"][c] for c in rm.LEVERS) * X["CourseLoad"]
    new_gpa = (X["SemGPA"] + d_gpa).clip(2, 5)   # 5-point scale, a failed course counts as 2
    X["CumGPA"] = (X["CumGPA"] + (new_gpa - X["SemGPA"]) / X["StudySemester"]).clip(2, 5)
    X["SemGPA"] = new_gpa
    X["GPATrend"] = X["SemGPA"] - X["PrevGPA"]
    new_failed = (X["FailedCourses"] + d_fail).clip(0, X["CourseLoad"])
    X["CumFailedCourses"] = (X["CumFailedCourses"] + new_failed - X["FailedCourses"]).clip(lower=0)
    X["FailedCourses"] = new_failed
    return X


def outcomes(bundle: dict, X: pd.DataFrame) -> dict:
    p = rm.predict(bundle, X)
    remaining = (8 - X["StudySemester"]).clip(lower=0).to_numpy()
    return {
        "predicted_gpa": float(p["PredictedNextGPA"].mean()),
        "at_risk_students": int((p["RiskProbability"] >= bundle["threshold"]).sum()),
        "high_risk_students": int(np.isin(rm.risk_level(p["RiskProbability"]), HIGH_RISK).sum()),
        "failure_rate": float(p["PredictedFailRate"].mean()),
        "retention": float(1 - p["DropoutProbability"].mean()),
        # assumes the estimated per-semester dropout chance stays constant
        "graduation_probability": float(((1 - p["DropoutProbability"]) ** remaining).mean()),
    }


def simulate(pop: pd.DataFrame, bundle: dict, title: str = "Maxsus ssenariy",
             target: str = "all", share: float = 0.3, faculty_key: int | None = None,
             assumptions: str = "", **levers) -> dict:
    mask = target_mask(pop, target, share, faculty_key)
    base = outcomes(bundle, pop)
    scen = outcomes(bundle, apply_levers(pop, mask, bundle["levers"], **levers))
    table = pd.DataFrame([dict(
        Key=k, Outcome=label, Baseline=base[k], Scenario=scen[k], Change=scen[k] - base[k],
        Improves=(scen[k] - base[k]) * (1 if up else -1) > 0, Format=fmt)
        for k, label, fmt, up in OUTCOMES])
    return {"title": title, "assumptions": assumptions, "students": int(len(pop)),
            "affected": int(mask.sum()), "levers": levers, "table": table,
            "note": "Model asosidagi simulyatsiya (sintetik ma'lumot). Natijalar kuzatilgan "
                    "bog'liqliklarga tayanadi va kafolatlangan sabab-oqibat emas."}


def run_scenario(pop: pd.DataFrame, bundle: dict, key: str, faculty_key: int | None = None) -> dict:
    spec = dict(SCENARIOS[key])
    return simulate(pop, bundle, faculty_key=faculty_key, **spec)


def format_table(result: dict) -> pd.DataFrame:
    """Human-readable version of a simulation result."""
    t = result["table"]

    def fmt_change(r):
        if "%" in r.Format:
            return f"{r.Change * 100:+.2f} f.p."
        return f"{r.Change:+.2f}" if "f" in r.Format and "," not in r.Format else f"{r.Change:+,.0f}"

    return pd.DataFrame({
        "Ko'rsatkich": t.Outcome,
        "Hozirgi holat": [r.Format.format(r.Baseline) for r in t.itertuples()],
        "Ssenariy": [r.Format.format(r.Scenario) for r in t.itertuples()],
        "O'zgarish": [fmt_change(r) for r in t.itertuples()],
    })


if __name__ == "__main__":
    engine = config.get_engine()
    bundle = rm.load_bundle()
    pop = population(engine, bundle)
    for key in SCENARIOS:
        res = run_scenario(pop, bundle, key)
        print(f"\n=== {res['title']}  (ta'sir: {res['affected']:,} / {res['students']:,} talaba)")
        print(format_table(res).to_string(index=False))
