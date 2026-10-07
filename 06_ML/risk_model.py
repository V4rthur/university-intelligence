"""Shared ML code: dataset construction, prediction, explanation, scoring.

Prediction task (PHASE 7)
    Using what is known about a student at the END of semester t, predict
    whether the student will be academically at risk in semester t+1:
        semester GPA < 2.0  OR  2+ failed courses  OR  dropped out before t+1.
    Features come only from semester t and earlier, the label only from t+1,
    so there is no leakage from the future.

Explanation (PHASE 8)
    For each student and each factor group, the group's values are replaced by
    those of a typical not-at-risk student and the model is asked again. The
    drop in predicted risk is that group's contribution ("occlusion"). The
    positive contributions are normalised to percentages.
"""
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

MODEL_FILE = config.MODEL_DIR / "risk_model.joblib"

FEATURES = [
    "SemGPA", "PrevGPA", "CumGPA", "GPATrend", "AttendanceRate", "FailedCourses",
    "CumFailedCourses", "AvgAssignmentScore", "SubmissionRate", "WarningsCum",
    "DebtRatio", "StudySemester", "Credits", "AvgTeacherLoad",
]
FEATURE_LABELS = {
    "SemGPA": "Joriy semestr GPA", "PrevGPA": "Oldingi semestr GPA", "CumGPA": "Umumiy GPA",
    "GPATrend": "GPA o'zgarishi", "AttendanceRate": "Davomat",
    "FailedCourses": "Yiqilgan fanlar (semestr)", "CumFailedCourses": "Yiqilgan fanlar (jami)",
    "AvgAssignmentScore": "Topshiriq bali", "SubmissionRate": "Topshiriq topshirish ulushi",
    "WarningsCum": "Ogohlantirishlar soni", "DebtRatio": "To'lov qarzi ulushi",
    "StudySemester": "O'qish semestri", "Credits": "Kredit yuklamasi",
    "AvgTeacherLoad": "O'qituvchi yuklamasi",
}
# factor groups shown to management (brief: GPA, attendance, failed subjects, ...)
GROUPS = {
    "GPA": ["SemGPA", "PrevGPA", "CumGPA", "GPATrend"],
    "Davomat": ["AttendanceRate"],
    "Yiqilgan fanlar": ["FailedCourses", "CumFailedCourses"],
    "Topshiriqlar": ["AvgAssignmentScore", "SubmissionRate"],
    "Moliyaviy qarz": ["DebtRatio"],
    "Akademik tarix": ["WarningsCum", "StudySemester", "Credits"],
    "O'qituvchi yuklamasi": ["AvgTeacherLoad"],
}
GROUP_COLUMNS = {"GPA": "F_GPA", "Davomat": "F_Attendance", "Yiqilgan fanlar": "F_Failed",
                 "Topshiriqlar": "F_Assignments", "Moliyaviy qarz": "F_Debt",
                 "Akademik tarix": "F_History", "O'qituvchi yuklamasi": "F_TeacherLoad"}


def load_snapshot(engine) -> pd.DataFrame:
    if config.OFFLINE:
        import offline
        df = offline.table("ml_snapshot")
    else:
        df = pd.read_sql(text(
            "SELECT ss.*, s.Status FROM dw.FactStudentSemester ss "
            "JOIN dw.DimStudent s ON s.StudentKey = ss.StudentKey"), engine)
    num = [c for c in df.columns if c not in ("Status",)]
    df[num] = df[num].apply(pd.to_numeric)
    return add_features(df)


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["PrevGPA"] = df["PrevGPA"].fillna(df["SemGPA"])   # first semester: no history yet
    df["GPATrend"] = df["SemGPA"] - df["PrevGPA"]
    return df


def build_dataset(snap: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (labelled rows, rows to score).

    labelled: semester t rows whose outcome in t+1 is known.
    to score: the latest semester of students who are still active.
    """
    nxt = snap[["StudentKey", "SemesterKey", "IsAtRisk", "SemGPA", "FailedCourses", "CourseLoad"]].copy()
    nxt["SemesterKey"] -= 1
    nxt.columns = ["StudentKey", "SemesterKey", "NextAtRisk", "NextGPA", "NextFailed", "NextLoad"]
    df = snap.merge(nxt, on=["StudentKey", "SemesterKey"], how="left")

    has_next = df["NextAtRisk"].notna()
    dropped = ~has_next & (df["IsLastSemester"] == 1) & (df["Status"] == "Chetlashtirilgan")
    df["Dropout"] = dropped.astype(int)
    df["Target"] = np.where(dropped, 1, df["NextAtRisk"])
    df["NextFailRate"] = df["NextFailed"] / df["NextLoad"]

    # The latest semester is excluded from training: its only known outcomes are
    # the students who already dropped out, so every label there would be positive.
    latest = snap["SemesterKey"].max()
    labelled = df[(has_next | dropped) & (df["SemesterKey"] < latest)].copy()
    labelled["Target"] = labelled["Target"].astype(int)
    to_score = df[(df["SemesterKey"] == latest) & (df["Status"] == "Faol")].copy()
    return labelled, to_score


def risk_level(prob) -> np.ndarray:
    bounds = [b for b, _ in config.RISK_LEVELS]
    labels = np.array([lab for _, lab in config.RISK_LEVELS])
    return labels[np.searchsorted(bounds, np.asarray(prob), side="right")]


def load_bundle() -> dict:
    return joblib.load(MODEL_FILE)


def predict(bundle: dict, X: pd.DataFrame) -> pd.DataFrame:
    """All model outputs for a feature frame (used by scoring and simulation)."""
    X = X[FEATURES]
    out = pd.DataFrame(index=X.index)
    # a probability is an estimate, never a certainty: keep it inside (0, 1)
    out["RiskProbability"] = np.clip(bundle["risk"].predict_proba(X)[:, 1], 0.01, 0.99)
    out["PredictedNextGPA"] = np.clip(bundle["gpa"].predict(X), 2, 5)
    out["PredictedFailRate"] = np.clip(bundle["fail"].predict(X), 0, 1)
    out["DropoutProbability"] = bundle["dropout"].predict_proba(X)[:, 1]
    return out


def explain(bundle: dict, X: pd.DataFrame) -> pd.DataFrame:
    """Per-student share (0-100) of each factor group in the predicted risk."""
    X = X[FEATURES]
    base = bundle["risk"].predict_proba(X)[:, 1]
    contrib = {}
    for group, cols in GROUPS.items():
        Xr = X.copy()
        for c in cols:
            Xr[c] = bundle["baseline"][c]
        contrib[group] = np.maximum(base - bundle["risk"].predict_proba(Xr)[:, 1], 0)
    contrib = pd.DataFrame(contrib, index=X.index)
    total = contrib.sum(axis=1).replace(0, np.nan)
    return (contrib.div(total, axis=0) * 100).fillna(0).round(1)


def main_factors(shares: pd.DataFrame, top: int = 4) -> pd.Series:
    def fmt(row):
        best = row[row >= 1].sort_values(ascending=False).head(top)
        return " · ".join(f"{k} {v:.0f}%" for k, v in best.items()) or "Sezilarli omil yo'q"
    return shares.apply(fmt, axis=1)


def score_students(engine, bundle: dict | None = None) -> pd.DataFrame:
    """Score every active student on their latest semester and write ml.StudentRisk."""
    bundle = bundle or load_bundle()
    _, to_score = build_dataset(load_snapshot(engine))
    pred = predict(bundle, to_score)
    shares = explain(bundle, to_score)
    out = pd.concat([to_score[["StudentKey", "SemesterKey", "FacultyKey", "DepartmentKey"]],
                     pred.round(4)], axis=1)
    out["RiskLevel"] = risk_level(out["RiskProbability"])
    out["IsFlagged"] = (out["RiskProbability"] >= bundle["threshold"]).astype(int)
    for group, col in GROUP_COLUMNS.items():
        out[col] = shares[group]
    out["MainFactors"] = main_factors(shares)
    out["ModelName"] = bundle["model_name"]
    out["ScoredAt"] = pd.Timestamp.now().floor("s")
    with engine.begin() as con:
        out.to_sql("StudentRisk", con, schema="ml", if_exists="replace", index=False,
                   chunksize=1000)
    return out

LEVERS = ["AttendanceRate", "SubmissionRate", "AvgAssignmentScore", "AvgTeacherLoad"]


def estimate_levers(snap: pd.DataFrame) -> dict:
    """Within-student association between the controllable levers and the
    same-semester outcomes (GPA, share of failed courses).

    Each student is compared with their own average across semesters, which
    removes stable differences between students (ability, background). The
    coefficients are still ASSOCIATIONS from observational data - they are an
    assumption of the what-if simulation, not proven causal effects.
    """
    df = snap[snap.groupby("StudentKey")["SemesterKey"].transform("size") >= 2].copy()
    df["FailRate"] = df["FailedCourses"] / df["CourseLoad"]
    cols = LEVERS + ["SemGPA", "FailRate"]
    dm = df[cols] - df.groupby("StudentKey")[cols].transform("mean")
    A = dm[LEVERS].to_numpy(float)
    out = {}
    for target in ("SemGPA", "FailRate"):
        coef, *_ = np.linalg.lstsq(A, dm[target].to_numpy(float), rcond=None)
        out[target] = dict(zip(LEVERS, coef.round(6).tolist()))
    return out
