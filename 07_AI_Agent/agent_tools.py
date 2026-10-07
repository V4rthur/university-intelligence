"""Tools the AI agent can call (PHASE 10).

The agent never answers from memory. Every number it quotes must come from
one of these tools, which read the warehouse, the analytics layer, the ML
outputs or the simulation engine - the same code the dashboard uses.

Role-based access (concept)
    rahbariyat  university management: everything, including named students
    dekan       one faculty only; named students of that faculty
    oqituvchi   aggregated indicators only: no student names, no free SQL
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import metrics as m  # noqa: E402
import risk_model as rm  # noqa: E402
import scenarios as sc  # noqa: E402

ROLES = {
    "rahbariyat": dict(label="Universitet rahbariyati", students=True, sql=True, faculty=None),
    "dekan": dict(label="Fakultet dekani", students=True, sql=False, faculty="own"),
    "oqituvchi": dict(label="Professor-o'qituvchi", students=False, sql=False, faculty=None),
}

SCHEMA_DOC = """
dw.DimStudent(StudentKey, FirstName, LastName, FullName, GroupName, Gender, DateOfBirth, FacultyKey, DepartmentKey, EnrollmentYear, StudyYear, ScholarshipStatus, TuitionStatus, Status['Faol'|'Chetlashtirilgan'|'Bitirgan'], StatusDate)
dw.DimFaculty(FacultyKey, FacultyName, Dean, EstablishedYear)
dw.DimDepartment(DepartmentKey, DepartmentName, FacultyKey)
dw.DimTeacher(TeacherKey, TeacherName, DepartmentKey, ExperienceYears, AcademicDegree, EmploymentType)
dw.DimCourse(CourseKey, CourseName, DepartmentKey, Credits, CurriculumSemester, CourseType)
dw.DimSemester(SemesterKey, AcademicYear, SemesterName['Kuz'|'Bahor'], SemesterLabel, StartDate, EndDate)
dw.DimDate(DateKey yyyymmdd, Date, Year, Quarter, Month, MonthName, Day, WeekdayName, IsWeekend, SemesterKey)
dw.FactEnrollments(EnrollmentID, StudentKey, CourseKey, TeacherKey, SemesterKey)
dw.FactGrades(GradeID, StudentKey, CourseKey, TeacherKey, SemesterKey, CurrentScore[joriy nazorat, max 20], MidtermScore[oraliq nazorat, max 30], FinalScore[yakuniy nazorat, max 50], AttendanceScore[%], TotalScore[max 100, pass mark 60], IsAdmitted[admitted to the final control], FinalGrade['5'|'4'|'3'|'2'], GradePoints[5..2], Credits, IsFailed, IsMidtermImputed)
dw.FactAttendance(AttendanceID, StudentKey, CourseKey, DateKey, SemesterKey, Status['Keldi'|'Kelmadi'|'Sababli'], IsPresent)
dw.FactPayments(PaymentID, StudentKey, DateKey, SemesterKey, TuitionAmount, PaidAmount, RemainingDebt, PaymentStatus)
dw.FactAssignments(AssignmentID, StudentKey, CourseKey, SemesterKey, DueDateKey, SubmissionDateKey, Score, SubmissionStatus, IsSubmitted, IsLate)
dw.FactWarnings(WarningID, StudentKey, DateKey, SemesterKey, WarningType, Severity)
dw.FactStudentSemester(StudentKey, SemesterKey, FacultyKey, DepartmentKey, StudySemester, CourseLoad, Credits, SemGPA, CumGPA, PrevGPA, AttendanceRate, FailedCourses, CumFailedCourses, AvgAssignmentScore, SubmissionRate, WarningsCum, DebtRatio, AvgTeacherLoad, IsAtRisk, IsLastSemester)
ml.StudentRisk(StudentKey, SemesterKey, FacultyKey, DepartmentKey, RiskProbability, PredictedNextGPA, PredictedFailRate, DropoutProbability, RiskLevel['Past'|'O''rta'|'Yuqori'|'Kritik'], IsFlagged, F_GPA, F_Attendance, F_Failed, F_Assignments, F_Debt, F_History, F_TeacherLoad, MainFactors, ModelName, ScoredAt)
ml.ModelMetrics(Model, Split, Rule, Threshold, Accuracy, Precision, Recall, F1, ROC_AUC, TN, FP, FN, TP, IsBest)
etl.RunLog, etl.FileLog, etl.DataQualityLog, etl.LoadAudit
""".strip()

TOOLS = [
    {
        "name": "university_overview",
        "description": "Headline KPIs of the latest semester, the University Health Score with its "
                       "weighted components, active alerts and detected anomalies. Call this first "
                       "for any question about the overall state of the university or 'what is happening'.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "faculty_analytics",
        "description": "Compare faculties in the latest semester (students, GPA, attendance, failure "
                       "rate, retention, tuition collection, predicted high-risk share, health score, "
                       "rank). Pass `faculty` to also get that faculty's semester-by-semester trend "
                       "and its most problematic courses - use this to explain WHY a faculty is "
                       "declining.",
        "input_schema": {"type": "object", "properties": {
            "faculty": {"type": "string", "description": "Faculty name or part of it, e.g. 'Iqtisodiyot'. Omit to compare all faculties."}},
            "additionalProperties": False},
    },
    {
        "name": "student_analytics",
        "description": "Student-level analytics. action='top_risk': the students with the highest "
                       "predicted risk and the main factors behind each score. action='profile': full "
                       "profile of one student (semester history, grades, warnings, risk). "
                       "action='search': find students by name.",
        "input_schema": {"type": "object", "properties": {
            "action": {"type": "string", "enum": ["top_risk", "profile", "search"]},
            "faculty": {"type": "string", "description": "Optional faculty filter for top_risk."},
            "limit": {"type": "integer", "description": "Rows for top_risk/search (default 20, max 50)."},
            "student_id": {"type": "integer", "description": "StudentKey, required for profile."},
            "name": {"type": "string", "description": "Name fragment, required for search."}},
            "required": ["action"], "additionalProperties": False},
    },
    {
        "name": "course_analytics",
        "description": "Course-level analytics: enrollment, average score, failure rate, attendance, "
                       "difficulty label and number of teachers. Without `course` returns the courses "
                       "with the highest failure rate; with `course` returns that course's history "
                       "by semester.",
        "input_schema": {"type": "object", "properties": {
            "course": {"type": "string", "description": "Course name or part of it."},
            "faculty": {"type": "string"},
            "period": {"type": "string", "enum": ["latest", "all"],
                       "description": "latest semester (default) or pooled over all semesters."},
            "limit": {"type": "integer"}},
            "additionalProperties": False},
    },
    {
        "name": "exam_analytics",
        "description": "Midterm (oraliq nazorat) and final (yakuniy nazorat) exam results: average "
                       "result of each control as a share of its maximum, pass rates, the gap between "
                       "final and midterm, students not admitted to the final because of absences, "
                       "students who passed the midterm but failed the course, and the grade "
                       "distribution (5/4/3/2). Break down by faculty, academic group, course, "
                       "teacher or semester. Rows are sorted by failure rate, highest first.",
        "input_schema": {"type": "object", "properties": {
            "by": {"type": "string", "enum": ["faculty", "group", "course", "teacher", "semester"]},
            "faculty": {"type": "string", "description": "Optional faculty filter."},
            "period": {"type": "string", "enum": ["latest", "all"]},
            "limit": {"type": "integer"}},
            "additionalProperties": False},
    },
    {
        "name": "ml_prediction",
        "description": "Machine-learning risk predictions. Without arguments: the risk-level "
                       "distribution of all active students, the average contribution of each factor "
                       "group, and the model's test metrics (precision, recall, ROC-AUC, confusion "
                       "matrix). With `student_id`: that student's risk probability, level and "
                       "factor breakdown. With `faculty`: the distribution for one faculty.",
        "input_schema": {"type": "object", "properties": {
            "student_id": {"type": "integer"}, "faculty": {"type": "string"}},
            "additionalProperties": False},
    },
    {
        "name": "scenario_simulation",
        "description": "Model-based what-if simulation of next-semester outcomes (predicted GPA, "
                       "at-risk students, failure rate, retention, graduation probability). Use a "
                       "predefined `scenario`, or scenario='custom' with lever changes. Results are "
                       "estimates from observed associations, not guaranteed causal effects.",
        "input_schema": {"type": "object", "properties": {
            "scenario": {"type": "string", "enum": list(sc.SCENARIOS) + ["custom"]},
            "faculty": {"type": "string", "description": "Limit the affected students to one faculty."},
            "target": {"type": "string", "enum": ["all", "high_risk", "top_risk"],
                       "description": "custom only: who is affected."},
            "share": {"type": "number", "description": "custom + top_risk: share of students, e.g. 0.3."},
            "attendance": {"type": "number", "description": "custom: change in attendance rate, e.g. -0.05."},
            "submission": {"type": "number", "description": "custom: change in assignment submission rate."},
            "assignment_score": {"type": "number", "description": "custom: change in assignment score (points)."},
            "teacher_load_pct": {"type": "number", "description": "custom: relative change, e.g. -0.10."}},
            "required": ["scenario"], "additionalProperties": False},
    },
    {
        "name": "sql_query",
        "description": "Run ONE read-only SELECT against the SQL Server data warehouse (T-SQL) for "
                       "questions the other tools cannot answer. Returns at most "
                       f"{config.SQL_TOOL_MAX_ROWS} rows. Schema:\n" + SCHEMA_DOC,
        "input_schema": {"type": "object", "properties": {
            "query": {"type": "string", "description": "A single SELECT (or WITH ... SELECT) statement."}},
            "required": ["query"], "additionalProperties": False},
    },
    {
        "name": "generate_report",
        "description": "Save an executive report as a Markdown file in 10_Documentation/reports. "
                       "Gather the facts with the other tools FIRST, then pass the finished report "
                       "text. Returns the file path.",
        "input_schema": {"type": "object", "properties": {
            "title": {"type": "string"},
            "markdown": {"type": "string", "description": "Full report body in Markdown."}},
            "required": ["title", "markdown"], "additionalProperties": False},
    },
]

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|alter|create|truncate|exec|execute|grant|revoke|deny|"
    r"backup|restore|shutdown|openrowset|opendatasource|bulk|into|xp_\w+|sp_\w+|dbcc|waitfor|"
    r"revert|setuser)\b",
    re.IGNORECASE)
SQL_READER = "uis_agent_reader"      # read-only database user, see 03_SQL/03_agent_reader.sql


def _records(df: pd.DataFrame, digits: int = 3) -> list[dict]:
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_float_dtype(df[c]):
            df[c] = df[c].round(digits)
    return json.loads(df.to_json(orient="records", date_format="iso", force_ascii=False))


class Toolbox:
    """Executes tool calls for one user role against one snapshot of the data."""

    def __init__(self, engine=None, role: str = "rahbariyat", own_faculty: str | None = None,
                 data: dict | None = None):
        self.engine = engine or config.get_engine()
        self.role, self.perm = role, ROLES[role]
        self.data = data or m.load_all(self.engine)
        self.own_faculty = self._faculty_key(own_faculty) if own_faculty else None
        self._bundle = self._pop = None
        self.trace: list[dict] = []          # every call, for the audit trail shown in the UI

    # ------------------------------------------------------------- helpers
    def _faculty_key(self, name: str | None) -> int | None:
        if not name:
            return None
        f = self.data["faculties"]
        hit = f[f.FacultyName.str.lower().str.contains(name.strip().lower(), regex=False)]
        if hit.empty:
            raise ValueError(f"Fakultet topilmadi: '{name}'. Mavjud: {', '.join(f.FacultyName)}")
        return int(hit.FacultyKey.iloc[0])

    def _scope(self, faculty: str | None) -> int | None:
        """Faculty filter after applying the role's restriction."""
        key = self._faculty_key(faculty)
        if self.perm["faculty"] == "own":
            if key and key != self.own_faculty:
                raise PermissionError("Bu rol faqat o'z fakulteti ma'lumotlarini ko'ra oladi.")
            return self.own_faculty
        return key

    def _need_students(self):
        if not self.perm["students"]:
            raise PermissionError(
                "Bu rol uchun talaba darajasidagi shaxsiy ma'lumotlar yopiq. "
                "Faqat umumlashtirilgan ko'rsatkichlar mavjud.")

    def _simulation(self):
        if self._pop is None:
            self._bundle = rm.load_bundle()
            self._pop = sc.population(self.engine, self._bundle)
        return self._pop, self._bundle

    # --------------------------------------------------------------- tools
    def university_overview(self) -> dict:
        d = self.data
        score, detail = m.university_health(d)
        an = m.anomalies(d)
        return {
            "kpis": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in m.kpis(d).items()},
            "health_score": score,
            "health_components": _records(detail[["Component", "Value", "SubScore", "Weight", "Points"]]),
            "alerts": [{"level": a["level"], "text": a["text"]} for a in m.alerts(d)],
            "anomalies": _records(an.drop(columns=["SemesterKey"]).head(10)) if len(an) else [],
            "semester_trend": _records(m.semester_trend(d)[[
                "SemesterLabel", "Students", "AvgGPA", "AttendanceRate", "FailureRate",
                "AtRiskShare", "Retention", "CollectionRate"]]),
        }

    def faculty_analytics(self, faculty: str | None = None) -> dict:
        d, key = self.data, self._scope(faculty)
        cols = ["FacultyName", "Students", "AvgGPA", "AttendanceRate", "FailureRate", "SubmissionRate",
                "Retention", "CollectionRate", "HighRiskStudents", "HighRiskShare", "HealthScore", "Rank"]
        summary = m.faculty_summary(d)
        out = {"semester": m.semester_label(d, d["latest"]),
               "faculties": _records(summary[[c for c in cols if c in summary.columns]])}
        if key:
            trend = m.faculty_trend(d)
            out["trend"] = _records(trend[trend.FacultyKey == key][[
                "SemesterLabel", "Students", "AvgGPA", "AttendanceRate", "FailureRate",
                "AtRiskShare", "Retention", "CollectionRate"]])
            courses = m.course_summary(d, -1)
            courses = courses[(courses.FacultyKey == key) & (courses.Enrollment >= 30)]
            out["hardest_courses"] = _records(courses.nlargest(8, "FailureRate")[[
                "CourseName", "CurriculumSemester", "Enrollment", "AvgScore", "FailureRate", "Difficulty"]])
            risk = m.risk_table(d)
            risk = risk[risk.FacultyKey == key]
            if len(risk):
                out["risk_by_study_year"] = _records(risk.assign(
                    High=risk.RiskLevel.isin(m.HIGH_RISK)).groupby("StudyYear").agg(
                        Students=("High", "size"), HighRiskShare=("High", "mean")).reset_index())
                out["avg_factor_shares_high_risk"] = (
                    risk[risk.RiskLevel.isin(m.HIGH_RISK)][list(rm.GROUP_COLUMNS.values())]
                    .mean().round(1).rename({v: k for k, v in rm.GROUP_COLUMNS.items()}).to_dict())
        return out

    def student_analytics(self, action: str, faculty: str | None = None, limit: int = 20,
                          student_id: int | None = None, name: str | None = None) -> dict:
        self._need_students()
        d, key = self.data, self._scope(faculty)
        limit = int(min(max(limit or 20, 1), 50))
        if action == "top_risk":
            t = m.risk_table(d)
            if key:
                t = t[t.FacultyKey == key]
            return {"students": _records(t.head(limit)[[
                "StudentKey", "FullName", "FacultyName", "StudyYear", "RiskProbability", "RiskLevel",
                "MainFactors", "SemGPA", "AttendanceRate", "FailedCourses", "SubmissionRate",
                "DebtRatio", "PredictedNextGPA"]]),
                "note": "RiskProbability - keyingi semestr uchun model bahosi, kafolat emas."}
        if action == "search":
            s = d["students"]
            hit = s[s.FullName.str.lower().str.contains((name or "").lower(), regex=False)]
            if key:
                hit = hit[hit.FacultyKey == key]
            return {"students": _records(hit.head(limit)[[
                "StudentKey", "FullName", "FacultyKey", "StudyYear", "Status"]])}
        p = m.student_profile(d, self.engine, int(student_id or 0))
        if p is None:
            return {"error": f"Talaba topilmadi: {student_id}"}
        if key and int(p["info"].FacultyKey) != key:
            raise PermissionError("Bu talaba sizning fakultetingizga tegishli emas.")
        info = p["info"]
        out = {"student": {k: (str(info[k]) if k.endswith("Date") else info[k]) for k in [
            "StudentKey", "FullName", "GroupName", "Gender", "FacultyName", "DepartmentName", "EnrollmentYear",
            "StudyYear", "TuitionStatus", "ScholarshipStatus", "Status"]},
            "semesters": _records(p["history"][[
                "SemesterLabel", "SemGPA", "CumGPA", "AttendanceRate", "FailedCourses",
                "SubmissionRate", "AvgAssignmentScore", "DebtRatio", "WarningsCum"]]),
            "latest_grades": _records(p["grades"][p["grades"].SemesterKey == p["grades"].SemesterKey.max()]
                                      .drop(columns=["SemesterKey"])),
            "warnings": _records(p["warnings"])}
        out["student"] = json.loads(json.dumps(out["student"], default=str))
        if p["risk"] is not None:
            r = p["risk"]
            out["risk"] = {"RiskProbability": round(float(r.RiskProbability), 3),
                           "RiskLevel": r.RiskLevel, "MainFactors": r.MainFactors,
                           "PredictedNextGPA": round(float(r.PredictedNextGPA), 2),
                           "factor_shares": {g: float(r[c]) for g, c in rm.GROUP_COLUMNS.items()}}
        return out

    def course_analytics(self, course: str | None = None, faculty: str | None = None,
                         period: str = "latest", limit: int = 10) -> dict:
        d, key = self.data, self._scope(faculty)
        cols = ["CourseName", "FacultyName", "Enrollment", "AvgScore", "AvgGPA", "FailureRate",
                "Attendance", "Teachers", "Difficulty"]
        if course:
            t = m.course_summary(d)
            t = t[t.CourseName.str.lower().str.contains(course.lower(), regex=False)]
            if t.empty:
                return {"error": f"Fan topilmadi: '{course}'"}
            t = t.merge(d["semesters"][["SemesterKey", "SemesterLabel"]], on="SemesterKey")
            return {"history": _records(t.sort_values(["CourseName", "SemesterKey"])[
                ["SemesterLabel"] + cols + ["MidtermPct", "FinalPct", "NotAdmittedRate"]])}
        t = m.course_summary(d, d["latest"] if period == "latest" else -1)
        t = t[t.Enrollment >= config.ALERTS["min_course_enrollment"]]
        if key:
            t = t[t.FacultyKey == key]
        return {"period": m.semester_label(d, d["latest"]) if period == "latest" else "barcha semestrlar",
                "courses": _records(t.nlargest(int(min(limit or 10, 30)), "FailureRate")[cols])}

    def exam_analytics(self, by: str = "faculty", faculty: str | None = None,
                       period: str = "latest", limit: int = 15) -> dict:
        d, key = self.data, self._scope(faculty)
        sem = d["latest"] if period == "latest" else None
        cols = ["N", "CurrentPct", "MidtermPct", "FinalPct", "ExamGap", "MidtermPassRate",
                "FinalPassRate", "NotAdmitted", "NotAdmittedRate", "FailureRate", "LostAfterMidterm",
                "ExcellentRate"]
        out = {"period": m.semester_label(d, d["latest"]) if sem is not None else "barcha semestrlar",
               "scale": "Joriy nazorat max 20, oraliq max 30, yakuniy max 50; o'tish bali 60. "
                        "Foizlar har bir nazoratning o'z maksimumiga nisbatan. Yakuniy nazorat "
                        "ko'rsatkichlari faqat qo'yilgan talabalar bo'yicha.",
               "overview": {k: v for k, v in m.exam_overview(d).items() if k != "previous"}}
        if by == "semester":
            t = m.exam_by(d, None, "semester")
            out["rows"] = _records(t[["SemesterLabel"] + cols])
            return out
        t = m.exam_by(d, sem, by)
        if key and "FacultyKey" in t:
            t = t[t.FacultyKey == key]
        t = t[t.N >= (20 if by == "group" else config.ALERTS["min_course_enrollment"])]
        label = {"faculty": ["FacultyName"], "group": ["GroupName", "FacultyName"],
                 "course": ["CourseName", "FacultyName"], "teacher": ["TeacherName", "DepartmentName"]}[by]
        t = t.sort_values("FailureRate", ascending=False).head(int(min(limit or 15, 40)))
        out["rows"] = _records(t[label + cols])
        return out

    def ml_prediction(self, student_id: int | None = None, faculty: str | None = None) -> dict:
        d = self.data
        if student_id:
            self._need_students()
            r = d["risk"][d["risk"].StudentKey == int(student_id)]
            if r.empty:
                return {"error": "Bu talaba uchun bashorat yo'q (faol emas yoki topilmadi)."}
            r = r.iloc[0]
            if self.own_faculty and int(r.FacultyKey) != self.own_faculty:
                raise PermissionError("Bu talaba sizning fakultetingizga tegishli emas.")
            return {"StudentKey": int(r.StudentKey), "RiskProbability": round(float(r.RiskProbability), 3),
                    "RiskLevel": r.RiskLevel, "MainFactors": r.MainFactors,
                    "factor_shares": {g: float(r[c]) for g, c in rm.GROUP_COLUMNS.items()},
                    "PredictedNextGPA": round(float(r.PredictedNextGPA), 2),
                    "DropoutProbability": round(float(r.DropoutProbability), 4),
                    "note": "Ehtimollik - model bahosi; kafolat emas."}
        risk, key = d["risk"], self._scope(faculty)
        if key:
            risk = risk[risk.FacultyKey == key]
        mm = d["model_metrics"]
        best = mm[(mm.IsBest == 1) & (mm.Split == "test") & (mm.Rule == "recall target")]
        return {
            "scored_students": int(len(risk)),
            "risk_levels": risk.RiskLevel.value_counts().reindex(config.RISK_ORDER).fillna(0)
            .astype(int).to_dict(),
            "flagged_by_threshold": int(risk.IsFlagged.sum()),
            "avg_factor_shares_high_risk": (
                risk[risk.RiskLevel.isin(m.HIGH_RISK)][list(rm.GROUP_COLUMNS.values())].mean()
                .round(1).rename({v: k for k, v in rm.GROUP_COLUMNS.items()}).to_dict()),
            "model": _records(best[["Model", "Threshold", "Accuracy", "Precision", "Recall", "F1",
                                    "ROC_AUC", "TN", "FP", "FN", "TP"]]),
            "note": "Model sintetik ma'lumotda o'qitilgan va keyingi semestrda sinovdan o'tkazilgan. "
                    "FN - model o'tkazib yuborgan xavf ostidagi talabalar.",
        }

    def scenario_simulation(self, scenario: str, faculty: str | None = None, target: str = "all",
                            share: float = 0.3, **levers) -> dict:
        pop, bundle = self._simulation()
        key = self._scope(faculty)
        if scenario == "custom":
            levers = {k: float(v) for k, v in levers.items()
                      if k in ("attendance", "submission", "assignment_score", "teacher_load_pct") and v}
            res = sc.simulate(pop, bundle, target=target, share=share, faculty_key=key,
                              assumptions=f"Maxsus ssenariy: {levers}", **levers)
        else:
            res = sc.run_scenario(pop, bundle, scenario, faculty_key=key)
        return {"title": res["title"], "assumptions": res["assumptions"],
                "students_total": res["students"], "students_affected": res["affected"],
                "outcomes": _records(res["table"][["Outcome", "Baseline", "Scenario", "Change", "Improves"]], 4),
                "note": res["note"]}

    def sql_query(self, query: str) -> dict:
        if not self.perm["sql"]:
            raise PermissionError("Bu rol uchun erkin SQL so'rovlari yopiq.")
        q = query.strip().rstrip(";").strip()
        if ";" in q or not re.match(r"(?is)^\s*(select|with)\b", q) or _FORBIDDEN.search(q) \
                or "--" in q or "/*" in q:
            raise ValueError("Faqat bitta, faqat o'qish uchun SELECT so'roviga ruxsat berilgan.")
        with self.engine.connect() as con:
            con.exec_driver_sql("SET TRANSACTION ISOLATION LEVEL READ COMMITTED; SET LOCK_TIMEOUT 15000")
            # Second lock, inside the database: the query runs as a user that can only SELECT
            # (03_SQL/03_agent_reader.sql). The cookie is needed to switch back, and the
            # query cannot see it, so it cannot leave that identity.
            try:
                cookie = con.exec_driver_sql(
                    "SET NOCOUNT ON; DECLARE @c varbinary(8000); "
                    f"EXECUTE AS USER = '{SQL_READER}' WITH COOKIE INTO @c; SELECT @c").scalar()
            except Exception as exc:
                raise RuntimeError(
                    "Faqat o'qish uchun ma'lumotlar bazasi foydalanuvchisi topilmadi. Sxemani yangilang: "
                    "`python run_pipeline.py`.") from exc
            try:
                result = con.exec_driver_sql(q)
                rows = result.fetchmany(config.SQL_TOOL_MAX_ROWS + 1)
                df = pd.DataFrame(rows, columns=list(result.keys()))
                result.close()
            finally:                         # also after a refused query: switch back, or drop the connection
                try:
                    con.rollback()
                    con.exec_driver_sql(
                        f"DECLARE @c varbinary(8000) = 0x{cookie.hex()}; REVERT WITH COOKIE = @c")
                except Exception:
                    con.invalidate()         # never hand a half-switched connection back to the pool
        truncated = len(df) > config.SQL_TOOL_MAX_ROWS
        return {"row_count": int(min(len(df), config.SQL_TOOL_MAX_ROWS)), "truncated": truncated,
                "rows": _records(df.head(config.SQL_TOOL_MAX_ROWS))}

    def generate_report(self, title: str, markdown: str) -> dict:
        config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:50] or "hisobot"
        path = config.REPORTS_DIR / f"{datetime.now():%Y%m%d_%H%M}_{slug}.md"
        footer = ("\n\n---\n*Hisobot University Intelligence & AI Decision System tomonidan "
                  f"{datetime.now():%Y-%m-%d %H:%M} da tayyorlandi. Ma'lumotlar sintetik; "
                  "bashoratlar ehtimollik bo'lib, kafolat emas.*\n")
        path.write_text(f"# {title}\n\n{markdown.strip()}{footer}", encoding="utf-8")
        return {"saved_to": str(path.relative_to(config.ROOT)), "characters": len(markdown)}

    # ------------------------------------------------------------- dispatch
    def run(self, name: str, args: dict) -> tuple[str, bool]:
        """Execute one tool call. Returns (JSON result, is_error)."""
        try:
            if name not in {t["name"] for t in TOOLS}:
                raise ValueError(f"Noma'lum vosita: {name}")
            result, error = getattr(self, name)(**(args or {})), False
        except PermissionError as exc:
            result, error = {"error": "RUXSAT YO'Q", "detail": str(exc)}, True
        except Exception as exc:  # the model sees the message and can correct its call
            result, error = {"error": type(exc).__name__, "detail": str(exc)[:500]}, True
        payload = json.dumps(result, ensure_ascii=False, default=_json_default)
        self.trace.append({"tool": name, "input": args, "is_error": error,
                           "result_chars": len(payload)})
        return payload, error


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return str(o)
