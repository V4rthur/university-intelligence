"""Analytics layer (PHASE 6): one definition of every KPI.

The dashboard pages and the AI agent tools both call these functions, so a
number shown on a chart and a number quoted by the agent can never disagree.

    data = load_all(engine)          # a few aggregate queries against dw / ml / etl
    kpis(data), faculty_summary(data), health_score(...), alerts(data), anomalies(data) ...

Descriptive  -> kpis, semester_trend, faculty_summary, course_summary, teacher_summary
Diagnostic   -> anomalies, risk_vs_debt, course trend, drill-down profiles
Predictive   -> ml.StudentRisk (joined in load_all)
Prescriptive -> alerts + recommendations (see 09_Simulation and 07_AI_Agent)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

HIGH_RISK = ("Yuqori", "Kritik")


# ------------------------------------------------------------------ loading
def data_version(engine) -> str:
    """Changes whenever the ETL or the ML scoring has produced new data."""
    with engine.connect() as con:
        run = con.execute(text(
            "SELECT MAX(RunID) FROM etl.RunLog WHERE Status = N'SUCCESS'")).scalar()
        scored = con.execute(text(
            "SELECT CASE WHEN OBJECT_ID('ml.StudentRisk') IS NULL THEN NULL ELSE "
            "(SELECT CONVERT(VARCHAR(19), MAX(ScoredAt), 120) FROM ml.StudentRisk) END")).scalar()
    return f"{run}-{scored}"


def _q(engine, sql: str) -> pd.DataFrame:
    return pd.read_sql(text(sql), engine)


def load_all(engine) -> dict:
    d = {}
    d["semesters"] = _q(engine, """
        SELECT SemesterKey, AcademicYear, SemesterName, SemesterLabel, StartDate, EndDate
        FROM dw.DimSemester
        WHERE SemesterKey IN (SELECT DISTINCT SemesterKey FROM dw.FactStudentSemester)
        ORDER BY SemesterKey""")
    d["faculties"] = _q(engine, "SELECT * FROM dw.DimFaculty ORDER BY FacultyKey")
    d["departments"] = _q(engine, "SELECT * FROM dw.DimDepartment")
    d["teachers"] = _q(engine, """
        SELECT t.*, d.DepartmentName, d.FacultyKey FROM dw.DimTeacher t
        JOIN dw.DimDepartment d ON d.DepartmentKey = t.DepartmentKey""")
    d["courses"] = _q(engine, """
        SELECT c.*, d.DepartmentName, d.FacultyKey FROM dw.DimCourse c
        JOIN dw.DimDepartment d ON d.DepartmentKey = c.DepartmentKey""")
    d["students"] = _q(engine, """
        SELECT StudentKey, FullName, GroupName, Gender, DateOfBirth, FacultyKey, DepartmentKey, EnrollmentYear,
               StudyYear, ScholarshipStatus, TuitionStatus, Status, StatusDate
        FROM dw.DimStudent""")

    snap = _q(engine, "SELECT * FROM dw.FactStudentSemester")
    num = [c for c in snap.columns]
    snap[num] = snap[num].apply(pd.to_numeric)
    # retention: is the student still enrolled in the following semester?
    nxt = snap[["StudentKey", "SemesterKey"]].assign(SemesterKey=lambda x: x.SemesterKey - 1,
                                                     Retained=1.0)
    snap = snap.merge(nxt, on=["StudentKey", "SemesterKey"], how="left")
    latest = int(snap["SemesterKey"].max())
    eligible = (snap["StudySemester"] < 8) & (snap["SemesterKey"] < latest)
    snap["Retained"] = np.where(eligible, snap["Retained"].fillna(0.0), np.nan)
    d["snap"], d["latest"] = snap, latest

    d["course_sem"] = _q(engine, f"""
        SELECT g.SemesterKey, g.CourseKey, g.TeacherKey, {_EXAM_SUMS},
               SUM(g.GradePoints) AS Points, SUM(g.TotalScore) AS Total,
               SUM(g.FinalScore) AS Final, SUM(g.AttendanceScore) AS Attendance
        FROM dw.FactGrades g
        GROUP BY g.SemesterKey, g.CourseKey, g.TeacherKey""").astype(float).astype(
            {"SemesterKey": int, "CourseKey": int, "TeacherKey": int})
    # the same exam measures by the STUDENT's faculty and academic group
    d["exam_group"] = _q(engine, f"""
        SELECT g.SemesterKey, s.FacultyKey, s.GroupName, {_EXAM_SUMS}
        FROM dw.FactGrades g JOIN dw.DimStudent s ON s.StudentKey = g.StudentKey
        GROUP BY g.SemesterKey, s.FacultyKey, s.GroupName""")
    d["exam_group"][_EXAM_COLS] = d["exam_group"][_EXAM_COLS].astype(float)
    # joint distribution of midterm and final results in 10-percent bands
    mx = config.SCORE_MAX
    d["exam_dist"] = _q(engine, f"""
        SELECT g.SemesterKey, s.FacultyKey,
               CASE WHEN g.MidtermScore >= {mx['midterm']} THEN 9
                    ELSE FLOOR(g.MidtermScore * 10 / {mx['midterm']}) END AS MidBin,
               CASE WHEN g.IsAdmitted = 0 THEN -1 WHEN g.FinalScore >= {mx['final']} THEN 9
                    ELSE FLOOR(g.FinalScore * 10 / {mx['final']}) END AS FinBin,
               COUNT(*) AS N
        FROM dw.FactGrades g JOIN dw.DimStudent s ON s.StudentKey = g.StudentKey
        GROUP BY g.SemesterKey, s.FacultyKey,
               CASE WHEN g.MidtermScore >= {mx['midterm']} THEN 9
                    ELSE FLOOR(g.MidtermScore * 10 / {mx['midterm']}) END,
               CASE WHEN g.IsAdmitted = 0 THEN -1 WHEN g.FinalScore >= {mx['final']} THEN 9
                    ELSE FLOOR(g.FinalScore * 10 / {mx['final']}) END""").astype(int)
    d["payments"] = _q(engine, """
        SELECT p.SemesterKey, s.FacultyKey, COUNT(*) AS Invoices,
               SUM(CASE WHEN p.RemainingDebt > 0 THEN 1 ELSE 0 END) AS WithDebt,
               SUM(p.TuitionAmount) AS Tuition, SUM(p.PaidAmount) AS Paid,
               SUM(p.RemainingDebt) AS Debt
        FROM dw.FactPayments p JOIN dw.DimStudent s ON s.StudentKey = p.StudentKey
        GROUP BY p.SemesterKey, s.FacultyKey""").astype(float).astype(
            {"SemesterKey": int, "FacultyKey": int})
    d["payments_month"] = _q(engine, """
        SELECT d.[Year], d.[Month], SUM(p.PaidAmount) AS Paid, SUM(p.TuitionAmount) AS Tuition
        FROM dw.FactPayments p JOIN dw.DimDate d ON d.DateKey = p.DateKey
        GROUP BY d.[Year], d.[Month] ORDER BY 1, 2""").astype(float)
    d["student_debt"] = _q(engine, """
        SELECT StudentKey, SUM(RemainingDebt) AS TotalDebt, SUM(TuitionAmount) AS TotalTuition
        FROM dw.FactPayments GROUP BY StudentKey""").astype(float).astype({"StudentKey": int})

    has_risk = _q(engine, "SELECT OBJECT_ID('ml.StudentRisk') AS id")["id"].iloc[0] is not None
    d["risk"] = _q(engine, "SELECT * FROM ml.StudentRisk") if has_risk else pd.DataFrame(
        columns=["StudentKey", "SemesterKey", "FacultyKey", "RiskProbability", "RiskLevel"])
    d["model_metrics"] = _q(engine, "SELECT * FROM ml.ModelMetrics") if has_risk else pd.DataFrame()
    d["feature_importance"] = (_q(engine, "SELECT * FROM ml.FeatureImportance")
                               if has_risk else pd.DataFrame())
    return d


# ------------------------------------------------------------ exam measures
# Additive counts and sums over dw.FactGrades; every exam table is built from
# them, so the rates agree at course, teacher, group, faculty and university level.
_MID_PASS = config.SCORE_MAX["midterm"] * config.CONTROL_PASS_SHARE
_FIN_PASS = config.SCORE_MAX["final"] * config.CONTROL_PASS_SHARE
_EXAM_SUMS = f"""COUNT(*) AS N,
               SUM(CAST(g.IsFailed AS INT)) AS Failed,
               SUM(g.CurrentScore) AS CurrentSum, SUM(g.MidtermScore) AS MidtermSum,
               SUM(CASE WHEN g.IsAdmitted = 1 THEN g.FinalScore ELSE 0 END) AS FinalSum,
               SUM(CAST(g.IsAdmitted AS INT)) AS Admitted,
               SUM(CASE WHEN g.MidtermScore < {_MID_PASS} THEN 1 ELSE 0 END) AS MidLow,
               SUM(CASE WHEN g.IsAdmitted = 1 AND g.FinalScore < {_FIN_PASS} THEN 1 ELSE 0 END) AS FinLow,
               SUM(CASE WHEN g.MidtermScore >= {_MID_PASS} AND g.IsFailed = 1 THEN 1 ELSE 0 END) AS MidOkFailed,
               SUM(CASE WHEN g.FinalGrade = N'5' THEN 1 ELSE 0 END) AS N5,
               SUM(CASE WHEN g.FinalGrade = N'4' THEN 1 ELSE 0 END) AS N4,
               SUM(CASE WHEN g.FinalGrade = N'3' THEN 1 ELSE 0 END) AS N3"""
_EXAM_COLS = ["N", "Failed", "CurrentSum", "MidtermSum", "FinalSum", "Admitted", "MidLow",
              "FinLow", "MidOkFailed", "N5", "N4", "N3"]


def exam_rates(g: pd.DataFrame) -> pd.DataFrame:
    """Turn the additive exam sums into averages and rates.

    Percentages are of each control's own maximum, so midterm (max 30) and
    final (max 50) can be compared directly. The final average and pass rate
    count admitted students only; non-admission is reported separately.
    """
    mx = config.SCORE_MAX
    g = g.copy()
    g["Current"] = g["CurrentSum"] / g["N"]
    g["Midterm"] = g["MidtermSum"] / g["N"]
    g["FinalAdmitted"] = g["FinalSum"] / g["Admitted"]
    g["CurrentPct"] = g["Current"] / mx["current"]
    g["MidtermPct"] = g["Midterm"] / mx["midterm"]
    g["FinalPct"] = g["FinalAdmitted"] / mx["final"]
    g["ExamGap"] = g["FinalPct"] - g["MidtermPct"]          # negative: final weaker than midterm
    g["MidtermPassRate"] = 1 - g["MidLow"] / g["N"]
    g["FinalPassRate"] = 1 - g["FinLow"] / g["Admitted"]
    g["NotAdmitted"] = g["N"] - g["Admitted"]
    g["NotAdmittedRate"] = g["NotAdmitted"] / g["N"]
    g["FailureRate"] = g["Failed"] / g["N"]
    g["LostAfterMidterm"] = g["MidOkFailed"] / g["N"]       # passed midterm, failed the course
    g["ExcellentRate"] = g["N5"] / g["N"]
    return g


def exam_by(d: dict, semester: int | None, by: str = "faculty") -> pd.DataFrame:
    """Exam results for one semester (None = all semesters) by faculty, group,
    course or teacher."""
    if by in ("faculty", "group", "university", "semester"):
        src = d["exam_group"]
        keys = {"faculty": ["FacultyKey"], "group": ["FacultyKey", "GroupName"],
                "university": [], "semester": ["SemesterKey"]}[by]
    else:
        src = d["course_sem"]
        keys = {"course": ["CourseKey"], "teacher": ["TeacherKey"]}[by]
    if semester is not None and by != "semester":
        src = src[src.SemesterKey == semester]
    if keys:
        g = src.groupby(keys)[_EXAM_COLS].sum().reset_index()
    else:
        g = src[_EXAM_COLS].sum().to_frame().T
    g = exam_rates(g)
    if "FacultyKey" in g:
        g = g.merge(d["faculties"][["FacultyKey", "FacultyName"]], on="FacultyKey")
    if by == "course":
        g = g.merge(d["courses"][["CourseKey", "CourseName", "CurriculumSemester", "FacultyKey"]],
                    on="CourseKey").merge(d["faculties"][["FacultyKey", "FacultyName"]], on="FacultyKey")
    if by == "teacher":
        g = g.merge(d["teachers"][["TeacherKey", "TeacherName", "DepartmentName"]], on="TeacherKey")
    if by == "semester":
        g = g.merge(d["semesters"][["SemesterKey", "SemesterLabel"]], on="SemesterKey").sort_values(
            "SemesterKey")
    return g


def exam_overview(d: dict, semester: int | None = None) -> dict:
    """Headline exam figures of a semester and of the same semester a year earlier."""
    semester = d["latest"] if semester is None else semester
    cur = exam_by(d, semester, "university").iloc[0]
    has_prev = (d["exam_group"].SemesterKey == semester - 2).any()
    prev = exam_by(d, semester - 2, "university").iloc[0] if has_prev else None
    keys = ["N", "CurrentPct", "MidtermPct", "FinalPct", "ExamGap", "MidtermPassRate", "FinalPassRate",
            "NotAdmitted", "NotAdmittedRate", "FailureRate", "LostAfterMidterm", "ExcellentRate"]
    out = {k: float(cur[k]) for k in keys}
    out["previous"] = {k: float(prev[k]) for k in keys} if prev is not None else None
    out["semester"] = semester_label(d, semester)
    out["compared_with"] = semester_label(d, semester - 2) if has_prev else None
    out["grades"] = {"5": int(cur.N5), "4": int(cur.N4), "3": int(cur.N3), "2": int(cur.Failed)}
    return out


def exam_distribution(d: dict, semester: int, faculty_key: int | None = None) -> dict:
    """Histograms of midterm and final results (share of results per 10% band)
    and how students moved between the two controls."""
    x = d["exam_dist"][d["exam_dist"].SemesterKey == semester]
    if faculty_key:
        x = x[x.FacultyKey == faculty_key]
    bands = [f"{i * 10}-{i * 10 + 9 if i < 9 else 100}%" for i in range(10)]
    mid = x.groupby("MidBin")["N"].sum().reindex(range(10), fill_value=0)
    fin = x[x.FinBin >= 0].groupby("FinBin")["N"].sum().reindex(range(10), fill_value=0)
    hist = pd.DataFrame({"Band": bands, "Midterm": (mid / mid.sum()).to_numpy(),
                         "Final": (fin / max(fin.sum(), 1)).to_numpy()})
    # movement between the controls: three result levels on each side
    def level(b):
        return np.select([b < 0, b < 6, b < 8], ["Qo'yilmagan", "60% dan past", "60-79%"], "80% va yuqori")
    m = x.assign(Mid=level(x.MidBin.to_numpy()), Fin=level(x.FinBin.to_numpy()))
    flow = m.groupby(["Mid", "Fin"])["N"].sum().unstack(fill_value=0)
    order_m = ["80% va yuqori", "60-79%", "60% dan past"]
    order_f = ["80% va yuqori", "60-79%", "60% dan past", "Qo'yilmagan"]
    flow = flow.reindex(index=order_m, columns=order_f, fill_value=0)
    return {"hist": hist, "flow": flow, "flow_share": flow.div(flow.sum(axis=1).replace(0, np.nan), axis=0)}


def semester_label(d: dict, key: int) -> str:
    s = d["semesters"]
    return s.loc[s.SemesterKey == key, "SemesterLabel"].iloc[0]


# -------------------------------------------------------------- aggregation
def aggregate(d: dict, by: list[str]) -> pd.DataFrame:
    """Core KPIs of the student-semester snapshot grouped by `by`."""
    s = d["snap"]
    g = s.groupby(by)
    out = pd.DataFrame({
        "Students": g.size(),
        "AvgGPA": g.apply(lambda x: np.average(x.SemGPA, weights=x.Credits), include_groups=False),
        "AttendanceRate": g["AttendanceRate"].mean(),
        "FailureRate": g["FailedCourses"].sum() / g["CourseLoad"].sum(),
        "SubmissionRate": g["SubmissionRate"].mean(),
        "AtRiskShare": g["IsAtRisk"].mean(),
        "Retention": g["Retained"].mean(),
    }).reset_index()
    pay = d["payments"]
    pay_by = [c for c in by if c in ("SemesterKey", "FacultyKey")]
    if pay_by:
        p = pay.groupby(pay_by)[["Tuition", "Paid", "Debt"]].sum().reset_index()
        p["CollectionRate"] = p["Paid"] / p["Tuition"]
        out = out.merge(p, on=pay_by, how="left")
    return out


def semester_trend(d: dict) -> pd.DataFrame:
    return aggregate(d, ["SemesterKey"]).merge(
        d["semesters"][["SemesterKey", "SemesterLabel"]], on="SemesterKey")


def faculty_trend(d: dict) -> pd.DataFrame:
    return (aggregate(d, ["SemesterKey", "FacultyKey"])
            .merge(d["semesters"][["SemesterKey", "SemesterLabel"]], on="SemesterKey")
            .merge(d["faculties"][["FacultyKey", "FacultyName"]], on="FacultyKey"))


def course_summary(d: dict, semester: int | None = None) -> pd.DataFrame:
    """One row per course and semester (or pooled over all semesters)."""
    cs = d["course_sem"]
    keys = ["CourseKey"] + ([] if semester == -1 else ["SemesterKey"])
    g = cs.groupby(keys)[_EXAM_COLS + ["Points", "Total", "Final", "Attendance"]].sum().reset_index()
    g = exam_rates(g)
    for c in ("Points", "Total", "Final", "Attendance"):
        g[c] = g[c] / g["N"]
    g["Teachers"] = cs.groupby(keys)["TeacherKey"].nunique().to_numpy()
    g = g.merge(d["courses"], on="CourseKey").merge(
        d["faculties"][["FacultyKey", "FacultyName"]], on="FacultyKey")
    g["Difficulty"] = pd.cut(g["FailureRate"], [-1, 0.10, 0.20, 0.30, 2],
                             labels=["Yengil", "O'rtacha", "Qiyin", "Juda qiyin"]).astype(str)
    if semester is not None and semester != -1:
        g = g[g.SemesterKey == semester]
    return g.rename(columns={"N": "Enrollment", "Points": "AvgGPA", "Total": "AvgScore"})


def teacher_summary(d: dict, semester: int) -> pd.DataFrame:
    cs = d["course_sem"][d["course_sem"].SemesterKey == semester]
    g = cs.groupby("TeacherKey").agg(
        Students=("N", "sum"), Courses=("CourseKey", "nunique"), Failed=("Failed", "sum"),
        Points=("Points", "sum"), Attendance=("Attendance", "sum")).reset_index()
    g["AvgGPA"] = g["Points"] / g["Students"]
    g["AttendanceRate"] = g["Attendance"] / g["Students"] / 100
    g["FailureRate"] = g["Failed"] / g["Students"]
    g["Overloaded"] = g["Students"] > config.TEACHER_OVERLOAD_STUDENTS
    g = g.merge(d["teachers"], on="TeacherKey").merge(
        d["faculties"][["FacultyKey", "FacultyName"]], on="FacultyKey")
    return g.drop(columns=["Points", "Attendance", "Failed"])


# -------------------------------------------------------------- health score
def health_score(values: dict) -> tuple[float, pd.DataFrame]:
    """Weighted 0-100 score. Each component is scaled linearly between the
    'worst' and 'best' reference values in config.HEALTH_SCALES."""
    labels = {"academic": "Akademik natija (o'rtacha GPA)",
              "engagement": "Talaba faolligi (topshiriq topshirish)",
              "attendance": "Davomat", "retention": "Talabalarni saqlab qolish",
              "faculty_load": "O'qituvchi yuklamasi (ortiqcha yuklanganlar ulushi)",
              "financial": "Moliyaviy barqarorlik (to'lov yig'ilishi)",
              "course_health": "Fanlar holati (muammoli fanlar ulushi)"}
    # a component without a value (not applicable at this level) is left out
    # and the remaining weights are rescaled to sum to 1
    used = {k: w for k, w in config.HEALTH_WEIGHTS.items()
            if values.get(k) is not None and not pd.isna(values.get(k))}
    total = sum(used.values())
    rows = []
    for key, weight in used.items():
        weight = round(weight / total, 4)
        worst, best = config.HEALTH_SCALES[key]
        v = values[key]
        sub = float(np.clip((v - worst) / (best - worst), 0, 1) * 100)
        rows.append(dict(Key=key, Component=labels[key], Value=v, Worst=worst, Best=best,
                         SubScore=round(sub, 1), Weight=weight, Points=round(sub * weight, 1)))
    detail = pd.DataFrame(rows)
    return round(float(detail["Points"].sum()), 1), detail


def _health_inputs(row, teachers: pd.DataFrame, courses: pd.DataFrame) -> dict:
    big = courses[courses.Enrollment >= config.ALERTS["min_course_enrollment"]]
    return dict(
        academic=row["AvgGPA"], engagement=row["SubmissionRate"], attendance=row["AttendanceRate"],
        retention=row["Retention"], financial=row.get("CollectionRate"),
        faculty_load=float(teachers["Overloaded"].mean()) if len(teachers) else None,
        course_health=float((big.FailureRate > config.ALERTS["course_failure_attention"]).mean())
        if len(big) else None)


def _with_last_retention(table: pd.DataFrame, d: dict, by: list[str], semester: int) -> pd.DataFrame:
    """Retention is unknown for the latest semester (nobody has had a chance to
    return yet), so the most recent completed value is used instead."""
    if table["Retention"].notna().all():
        return table
    prev = aggregate(d, ["SemesterKey"] + by)
    prev = prev[(prev.SemesterKey < semester) & prev.Retention.notna()]
    prev = prev[prev.SemesterKey == prev.SemesterKey.max()]
    if by:
        table = table.drop(columns="Retention").merge(prev[by + ["Retention"]], on=by, how="left")
    else:
        table = table.assign(Retention=prev["Retention"].iloc[0] if len(prev) else np.nan)
    return table


def university_health(d: dict, semester: int | None = None) -> tuple[float, pd.DataFrame]:
    semester = d["latest"] if semester is None else semester
    row = aggregate(d, ["SemesterKey"])
    row = _with_last_retention(row[row.SemesterKey == semester], d, [], semester).iloc[0]
    return health_score(_health_inputs(row, teacher_summary(d, semester),
                                       course_summary(d, semester)))


def faculty_summary(d: dict, semester: int | None = None) -> pd.DataFrame:
    """Faculty comparison for one semester, with predicted risk and health score."""
    semester = d["latest"] if semester is None else semester
    t = aggregate(d, ["SemesterKey", "FacultyKey"])
    t = _with_last_retention(t[t.SemesterKey == semester], d, ["FacultyKey"], semester)
    t = t.merge(d["faculties"][["FacultyKey", "FacultyName"]], on="FacultyKey")
    risk = d["risk"]
    if len(risk):
        r = risk.assign(High=risk.RiskLevel.isin(HIGH_RISK)).groupby("FacultyKey").agg(
            ScoredStudents=("High", "size"), HighRiskStudents=("High", "sum"),
            HighRiskShare=("High", "mean"), AvgRiskProbability=("RiskProbability", "mean")
        ).reset_index()
        t = t.merge(r, on="FacultyKey", how="left")
    teachers, courses = teacher_summary(d, semester), course_summary(d, semester)
    # Teacher workload is left out of the faculty score: teachers of general
    # courses serve every faculty, so their load is not attributable to one.
    t["HealthScore"] = [
        health_score(_health_inputs(row, teachers.iloc[0:0],
                                    courses[courses.FacultyKey == row["FacultyKey"]]))[0]
        for _, row in t.iterrows()]
    t["Rank"] = t["HealthScore"].rank(ascending=False, method="min").astype(int)
    return t.sort_values("Rank")


# ---------------------------------------------------------------------- KPIs
def kpis(d: dict) -> dict:
    """Headline numbers for the latest semester, compared with the same semester
    one year earlier (Kuz and Bahor have different courses, so comparing
    neighbouring semesters would mostly show seasonality)."""
    tr = semester_trend(d).set_index("SemesterKey")
    base = d["latest"] - 2 if d["latest"] - 2 in tr.index else d["latest"] - 1
    cur, prev = tr.loc[d["latest"]], tr.loc[base]
    st, risk = d["students"], d["risk"]
    grad_cohorts = st[st.EnrollmentYear.isin(st.loc[st.Status == "Bitirgan", "EnrollmentYear"])]
    retention = tr["Retention"].dropna()
    high = int(risk.RiskLevel.isin(HIGH_RISK).sum()) if len(risk) else 0
    return {
        "semester": semester_label(d, d["latest"]),
        "compared_with": semester_label(d, base),
        "total_students": int((st.Status == "Faol").sum()),
        "students_in_semester": int(cur.Students),
        "avg_gpa": float(cur.AvgGPA), "avg_gpa_prev": float(prev.AvgGPA),
        "attendance": float(cur.AttendanceRate), "attendance_prev": float(prev.AttendanceRate),
        "failure_rate": float(cur.FailureRate), "failure_rate_prev": float(prev.FailureRate),
        "collection_rate": float(cur.CollectionRate), "collection_rate_prev": float(prev.CollectionRate),
        "retention": float(retention.iloc[-1]),
        "retention_prev": float(retention.iloc[-2]) if len(retention) > 1 else None,
        "graduation_rate": float((grad_cohorts.Status == "Bitirgan").mean())
        if len(grad_cohorts) else None,
        "high_risk_students": high,
        "high_risk_share": high / len(risk) if len(risk) else None,
        "flagged_students": int(risk["IsFlagged"].sum()) if len(risk) else 0,
        "outstanding_debt": float(d["payments"]["Debt"].sum()),
    }


def risk_table(d: dict) -> pd.DataFrame:
    """Scored students with names and current indicators (student-level, sensitive)."""
    cur = d["snap"][d["snap"].SemesterKey == d["latest"]][[
        "StudentKey", "StudySemester", "SemGPA", "CumGPA", "AttendanceRate", "FailedCourses",
        "CumFailedCourses", "SubmissionRate", "AvgAssignmentScore", "WarningsCum", "DebtRatio"]]
    return (d["risk"].merge(cur, on="StudentKey", how="left")
            .merge(d["students"][["StudentKey", "FullName", "GroupName", "StudyYear", "TuitionStatus"]],
                   on="StudentKey")
            .merge(d["faculties"][["FacultyKey", "FacultyName"]], on="FacultyKey")
            .merge(d["departments"][["DepartmentKey", "DepartmentName"]], on="DepartmentKey")
            .sort_values("RiskProbability", ascending=False))


def risk_vs_debt(d: dict) -> pd.DataFrame:
    """Academic outcomes by tuition-debt band (an association, not a cause)."""
    s = d["snap"][d["snap"].SemesterKey == d["latest"]].merge(
        d["students"][["StudentKey", "TuitionStatus"]], on="StudentKey")
    band = np.select(
        [s.TuitionStatus == "Grant", s.DebtRatio == 0, s.DebtRatio <= 0.3, s.DebtRatio <= 0.6],
        ["Grant (to'lov yo'q)", "Qarzi yo'q", "Qarz 1-30%", "Qarz 31-60%"], "Qarz 60% dan yuqori")
    out = s.assign(DebtBand=band).groupby("DebtBand").agg(
        Students=("StudentKey", "size"), AvgGPA=("SemGPA", "mean"),
        AttendanceRate=("AttendanceRate", "mean"), AtRiskShare=("IsAtRisk", "mean")).reset_index()
    order = ["Grant (to'lov yo'q)", "Qarzi yo'q", "Qarz 1-30%", "Qarz 31-60%", "Qarz 60% dan yuqori"]
    return out.set_index("DebtBand").reindex(order).dropna(how="all").reset_index()


def student_profile(d: dict, engine, student_key: int) -> dict | None:
    st = d["students"][d["students"].StudentKey == student_key]
    if st.empty:
        return None
    info = (st.merge(d["faculties"][["FacultyKey", "FacultyName"]], on="FacultyKey")
            .merge(d["departments"][["DepartmentKey", "DepartmentName"]], on="DepartmentKey").iloc[0])
    history = d["snap"][d["snap"].StudentKey == student_key].merge(
        d["semesters"][["SemesterKey", "SemesterLabel"]], on="SemesterKey").sort_values("SemesterKey")
    grades = pd.read_sql(text("""
        SELECT s.SemesterLabel, c.CourseName, t.TeacherName, g.CurrentScore, g.MidtermScore,
               g.FinalScore, g.TotalScore, g.FinalGrade, g.AttendanceScore,
               IIF(g.IsAdmitted = 1, N'Ha', N'Yo''q') AS Admitted, g.SemesterKey
        FROM dw.FactGrades g
        JOIN dw.DimCourse c ON c.CourseKey = g.CourseKey
        JOIN dw.DimTeacher t ON t.TeacherKey = g.TeacherKey
        JOIN dw.DimSemester s ON s.SemesterKey = g.SemesterKey
        WHERE g.StudentKey = :k ORDER BY g.SemesterKey, c.CourseName"""), engine,
        params={"k": int(student_key)})
    warnings = pd.read_sql(text("""
        SELECT d.[Date] AS WarningDate, w.WarningType, w.Severity FROM dw.FactWarnings w
        JOIN dw.DimDate d ON d.DateKey = w.DateKey WHERE w.StudentKey = :k ORDER BY 1"""),
        engine, params={"k": int(student_key)})
    risk = d["risk"][d["risk"].StudentKey == student_key]
    return {"info": info, "history": history, "grades": grades, "warnings": warnings,
            "risk": risk.iloc[0] if len(risk) else None}


# ------------------------------------------------------------------- alerts
def alerts(d: dict) -> list[dict]:
    """Rule-based alerts for the latest semester. Thresholds: config.ALERTS."""
    A, out = config.ALERTS, []
    latest, label = d["latest"], semester_label(d, d["latest"])
    k = kpis(d)
    if k["high_risk_share"] is not None and k["high_risk_share"] >= A["high_risk_share_critical"]:
        out.append(dict(level="critical", metric="risk", value=k["high_risk_students"], text=(
            f"{k['high_risk_students']:,} nafar talaba yuqori yoki kritik xavf darajasida "
            f"(faol talabalarning {k['high_risk_share']:.1%} qismi).").replace(",", " ")))

    ft = faculty_trend(d)
    cur = ft[ft.SemesterKey == latest].set_index("FacultyKey")
    base = latest - 2 if (ft.SemesterKey == latest - 2).any() else latest - 1
    prev = ft[ft.SemesterKey == base].set_index("FacultyKey")
    since = semester_label(d, base)
    for fk, row in cur.iterrows():
        if fk not in prev.index:
            continue
        p = prev.loc[fk]
        # multi-year direction: the same semester in each of the last three years
        hist = ft[(ft.FacultyKey == fk) & (ft.SemesterKey % 2 == latest % 2)].sort_values(
            "SemesterKey")["AvgGPA"].tail(3).to_numpy()
        if len(hist) == 3 and abs(hist[-1] / hist[0] - 1) >= 0.03:
            if hist[0] > hist[1] > hist[2]:
                out.append(dict(level="warning", metric="gpa_trend", value=hist[-1] / hist[0] - 1,
                                text=(f"{row.FacultyName} fakultetida o'rtacha GPA uch yil ketma-ket "
                                      f"pasaymoqda ({hist[0]:.2f} → {hist[1]:.2f} → {hist[2]:.2f}).")))
            elif hist[0] < hist[1] < hist[2]:
                out.append(dict(level="positive", metric="gpa_trend", value=hist[-1] / hist[0] - 1,
                                text=(f"{row.FacultyName} fakultetida o'rtacha GPA uch yil ketma-ket "
                                      f"o'smoqda ({hist[0]:.2f} → {hist[1]:.2f} → {hist[2]:.2f}).")))
        drop = p.AttendanceRate - row.AttendanceRate
        if drop >= A["attendance_drop_warning"]:
            out.append(dict(level="warning", metric="attendance", value=drop, text=(
                f"{row.FacultyName} fakultetida davomat {drop * 100:.1f} foiz punktga pasaydi "
                f"({since}: {p.AttendanceRate:.1%} → {row.AttendanceRate:.1%}).")))
        change = row.AvgGPA / p.AvgGPA - 1
        if change >= A["gpa_improvement_positive"]:
            out.append(dict(level="positive", metric="gpa", value=change, text=(
                f"{row.FacultyName} fakultetida o'rtacha GPA {since} semestriga nisbatan {change:.1%} ga oshdi "
                f"({p.AvgGPA:.2f} → {row.AvgGPA:.2f}).")))
        elif change <= -A["gpa_improvement_positive"]:
            out.append(dict(level="warning", metric="gpa", value=change, text=(
                f"{row.FacultyName} fakultetida o'rtacha GPA {since} semestriga nisbatan {abs(change):.1%} ga pasaydi "
                f"({p.AvgGPA:.2f} → {row.AvgGPA:.2f}).")))
        if pd.notna(row.CollectionRate) and row.CollectionRate < A["collection_rate_warning"]:
            out.append(dict(level="warning", metric="finance", value=row.CollectionRate, text=(
                f"{row.FacultyName} fakultetida to'lov yig'ilishi {row.CollectionRate:.1%} "
                f"(chegara {A['collection_rate_warning']:.0%}).")))

    cs = course_summary(d, latest)
    hot = cs[(cs.Enrollment >= A["min_course_enrollment"])
             & (cs.FailureRate > A["course_failure_attention"])].sort_values(
                 "FailureRate", ascending=False)
    for _, c in hot.iterrows():
        out.append(dict(level="attention", metric="course", value=c.FailureRate, text=(
            f"\"{c.CourseName}\" fanida yiqilish darajasi {c.FailureRate:.1%} "
            f"({int(c.Enrollment)} talaba, {c.FacultyName}).")))
    order = {"critical": 0, "warning": 1, "attention": 2, "positive": 3}
    for a in out:
        a["semester"] = label
    return sorted(out, key=lambda a: order[a["level"]])


# ---------------------------------------------------------------- anomalies
def _robust_z(x: pd.Series) -> pd.Series:
    med = x.median()
    mad = (x - med).abs().median()
    return (x - med) / (1.4826 * mad) if mad > 0 else x * 0.0


def anomalies(d: dict) -> pd.DataFrame:
    """Unusual changes, each described as what / where / when / how large.

    A faculty-level change is flagged when it is far outside the usual spread
    of semester-to-semester changes (robust z-score >= config.ANOMALY_Z).
    'PossibleReason' is a data-based hint for investigation, not a conclusion.
    """
    Z, rows = config.ANOMALY_Z, []
    ft = faculty_trend(d).sort_values(["FacultyKey", "SemesterKey"])
    specs = [("AttendanceRate", "Davomat", "{:.1%}"), ("AvgGPA", "O'rtacha GPA", "{:.2f}"),
             ("FailureRate", "Yiqilish darajasi", "{:.1%}"),
             ("CollectionRate", "To'lov yig'ilishi", "{:.1%}")]
    for col, name, fmt in specs:
        t = ft.assign(Prev=ft.groupby("FacultyKey")[col].shift(), Delta=lambda x: x[col] - x.Prev)
        t = t.dropna(subset=["Delta"])
        t["Z"] = _robust_z(t["Delta"])
        for _, r in t[t.Z.abs() >= Z].iterrows():
            others = t[(t.SemesterKey == r.SemesterKey) & (t.FacultyKey != r.FacultyKey)]["Delta"]
            if col == "CollectionRate":
                hint = "To'lov intizomi yoki to'lov muddatlaridagi o'zgarishni tekshirish kerak."
            elif others.abs().median() < abs(r.Delta) / 3:
                hint = ("O'zgarish faqat shu fakultetda kuzatilgan — fakultet ichidagi omil "
                        "(jadval, o'qituvchilar tarkibi, tashkiliy o'zgarish) bo'lishi mumkin.")
            else:
                hint = "O'zgarish boshqa fakultetlarda ham kuzatilgan — umumuniversitet omili bo'lishi mumkin."
            rows.append(dict(
                Type="Fakultet", What=f"{name} keskin {'pasaydi' if r.Delta < 0 else 'oshdi'}",
                Where=r.FacultyName, When=r.SemesterLabel, SemesterKey=r.SemesterKey,
                Before=fmt.format(r.Prev), After=fmt.format(r[col]),
                Change=(f"{r.Delta * 100:+.1f} f.p." if "%" in fmt else f"{r.Delta:+.2f}"),
                Z=round(float(r.Z), 1), PossibleReason=hint))

    # course: failure rate far above the same course's own history
    cs = course_summary(d).sort_values(["CourseKey", "SemesterKey"])
    cs = cs[cs.Enrollment >= config.ALERTS["min_course_enrollment"]]
    cs["PrevFail"] = cs.groupby("CourseKey")["Failed"].transform(lambda x: x.shift().expanding().sum())
    cs["PrevN"] = cs.groupby("CourseKey")["Enrollment"].transform(lambda x: x.shift().expanding().sum())
    cs["PrevFinal"] = cs.groupby("CourseKey")["FinalPct"].shift()
    cs["PrevMid"] = cs.groupby("CourseKey")["MidtermPct"].shift()
    cs = cs.dropna(subset=["PrevN"])
    p0 = cs.PrevFail / cs.PrevN
    cs["Z"] = (cs.FailureRate - p0) / np.sqrt((p0 * (1 - p0)).clip(lower=1e-4) / cs.Enrollment)
    labels = d["semesters"].set_index("SemesterKey")["SemesterLabel"]
    for _, r in cs[(cs.Z >= Z + 1) & (cs.FailureRate - p0 >= 0.07)].iterrows():
        before = r.PrevFail / r.PrevN
        d_final = (r.FinalPct - r.PrevFinal) * 100      # change in percentage points
        d_mid = (r.MidtermPct - r.PrevMid) * 100
        hint = ("Yakuniy nazorat natijasi oraliq nazoratga nisbatan ancha ko'p tushgan "
                f"({d_final:+.1f} va {d_mid:+.1f} f.p.) — imtihon murakkabligi yoki baholash "
                "mezoni o'zgargan bo'lishi mumkin." if d_final < d_mid - 8 else
                "Ballar semestr davomida ham past bo'lgan — fan mazmuni, o'qitish yoki talabalar "
                "tayyorgarligidagi o'zgarishni tekshirish kerak.")
        rows.append(dict(
            Type="Fan", What="Yiqilish darajasi odatdagidan keskin yuqori",
            Where=f"{r.CourseName} ({r.FacultyName})", When=labels[r.SemesterKey],
            SemesterKey=r.SemesterKey, Before=f"{before:.1%}", After=f"{r.FailureRate:.1%}",
            Change=f"{(r.FailureRate - before) * 100:+.1f} f.p.", Z=round(float(r.Z), 1),
            PossibleReason=hint))

    # teacher: workload far above colleagues in the latest semester
    ts = teacher_summary(d, d["latest"])
    ts["Z"] = _robust_z(ts["Students"])
    for _, r in ts[ts.Z >= Z].iterrows():
        rows.append(dict(
            Type="O'qituvchi yuklamasi", What="Yuklama hamkasblarga nisbatan juda yuqori",
            Where=f"{r.TeacherName} ({r.DepartmentName})", When=labels[d["latest"]],
            SemesterKey=d["latest"], Before=f"mediana {ts.Students.median():.0f}",
            After=f"{r.Students:.0f} talaba", Change=f"{r.Students / ts.Students.median():.1f}x",
            Z=round(float(r.Z), 1),
            PossibleReason="Umumta'lim fanlari bir necha fakultetga o'qitiladi — guruhlarni "
                           "qayta taqsimlash imkonini ko'rib chiqish kerak."))
    out = pd.DataFrame(rows)
    return out.sort_values(["SemesterKey", "Z"], ascending=[False, False]) if len(out) else out


# ------------------------------------------------------------- data quality
def data_quality(engine) -> dict:
    files = _q(engine, "SELECT * FROM etl.FileLog ORDER BY ProcessedAt DESC")
    checks = _q(engine, "SELECT * FROM etl.DataQualityLog")
    runs = _q(engine, "SELECT TOP 20 * FROM etl.RunLog ORDER BY RunID DESC")
    rows = float(files["RowsRead"].sum())
    by_check = checks.groupby(["CheckName", "Action"])["IssueCount"].sum().reset_index()
    # FLAGGED rows are informational and usually also counted by a REJECTED rule
    issues = float(checks.loc[checks.Action != "FLAGGED", "IssueCount"].sum())
    by_table = files.groupby("TableName").agg(
        Files=("FileName", "size"), RowsRead=("RowsRead", "sum"), RowsLoaded=("RowsLoaded", "sum"),
        RowsRejected=("RowsRejected", "sum")).reset_index()
    t_issues = checks[checks.Action != "FLAGGED"].groupby("TableName")["IssueCount"].sum()
    by_table["Issues"] = by_table["TableName"].map(t_issues).fillna(0)
    by_table["QualityScore"] = 1 - by_table["Issues"] / by_table["RowsRead"]
    ok = runs[runs.Status == "SUCCESS"]

    def count(check):
        return int(by_check.loc[by_check.CheckName == check, "IssueCount"].sum())

    return {
        "score": 1 - issues / rows if rows else None,
        "total_rows": int(rows), "issues": int(issues),
        "missing": count("missing_filled") + count("missing_imputed") + count("missing_required"),
        "duplicates": count("duplicate"),
        "invalid": count("invalid_category") + count("invalid_number") + count("invalid_date")
        + count("out_of_range"),
        "orphans": count("orphan_key"),
        "rejected": int(files["RowsRejected"].sum()),
        "last_run": ok.iloc[0].to_dict() if len(ok) else None,
        "by_check": by_check.sort_values("IssueCount", ascending=False),
        "by_table": by_table, "files": files, "runs": runs,
    }
