"""Synthetic university data generator (PHASE 2).

The data is SYNTHETIC. It is produced by a behavioural simulation, not by
independent random numbers, so realistic patterns exist for the analytics and
ML layers to find:

* every student has hidden traits (ability, engagement, financial stress);
* attendance, assignments and exam scores are all driven by those traits,
  the faculty, the difficulty of the course and the teacher's workload;
* some students decline over time, some faculties trend down or up;
* dropping out depends on GPA, failed courses, attendance and tuition debt;
* a few anomalies are planted on purpose (see ANOMALIES below);
* the raw files are deliberately dirty (duplicates, missing values, invalid
  records, orphan keys, mixed formats) so the ETL pipeline has real work to do.

Usage
    python 01_Data/generate_data.py --reset           # 4 academic years from scratch
    python 01_Data/generate_data.py --next-semester   # append one new semester
"""
import argparse
import json
import pickle
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import reference_uz as ref  # noqa: E402

BASE_YEAR = 2022
INITIAL_SEMESTERS = 8          # 2022-2023 Kuz ... 2025-2026 Bahor
COHORT_SIZE = 2600
SESSIONS = 10                  # attendance checkpoints per course per semester
STATE_FILE = config.STATE_DIR / "generator_state.pkl"

# Planted anomalies (documented so that findings can be verified against them)
ANOMALIES = {
    "attendance_drop": {"faculty_id": 2, "semester_index": 5, "logit_shift": -0.7},
    "exam_failure_spike": {"course_name": "Ma'lumotlar tahlili", "semester_index": 7,
                           "final_score_shift": -30},
}


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def semester_info(s: int) -> dict:
    year = BASE_YEAR + s // 2
    if s % 2 == 0:
        name, start, end = ref.SEMESTER_NAMES[0], date(year, 9, 5), date(year + 1, 1, 20)
    else:
        name, start, end = ref.SEMESTER_NAMES[1], date(year + 1, 2, 10), date(year + 1, 6, 20)
    return {"index": s, "year": year, "academic_year": f"{year}-{year + 1}",
            "name": name, "start": start, "end": end}


# ------------------------------------------------------------ reference data
def build_reference(rng) -> dict:
    faculties = pd.DataFrame({
        "FacultyID": range(1, 7),
        "FacultyName": [f[0] for f in ref.FACULTIES],
        "Dean": [f[1] for f in ref.FACULTIES],
        "EstablishedYear": [f[2] for f in ref.FACULTIES],
    })
    departments = pd.DataFrame({
        "DepartmentID": range(1, 19),
        "DepartmentName": ref.DEPARTMENTS,
        "FacultyID": [i // 3 + 1 for i in range(18)],
    })

    t_rows, dept_teachers, tid = [], {}, 0
    for d in range(1, 19):
        dept_teachers[d] = []
        for _ in range(7 + (d % 3 == 0)):
            tid += 1
            female = rng.random() < 0.45
            first = rng.choice(ref.FEMALE_NAMES if female else ref.MALE_NAMES)
            last = rng.choice(ref.LAST_NAMES) + ("a" if female else "")
            t_rows.append((tid, f"{last} {first}", d, int(rng.integers(1, 36)),
                           rng.choice(ref.DEGREES, p=[0.35, 0.5, 0.15]),
                           rng.choice(ref.EMPLOYMENT, p=[0.7, 0.2, 0.1])))
            dept_teachers[d].append(tid)
    teachers = pd.DataFrame(t_rows, columns=[
        "TeacherID", "TeacherName", "DepartmentID", "ExperienceYears",
        "AcademicDegree", "EmploymentType"])

    c_rows = []
    for i, (name, dept) in enumerate(ref.GENERAL_COURSES):
        c_rows.append((i + 1, name, dept, i // 2 + 1, ref.COURSE_TYPE[0]))
    for f in range(6):
        for k, name in enumerate(ref.FACULTY_COURSES[f]):
            sem, j = k // 3 + 1, k % 3
            ctype = ref.COURSE_TYPE[1] if (sem >= 5 and j == 2) else ref.COURSE_TYPE[0]
            c_rows.append((16 + f * 24 + k + 1, name, f * 3 + j + 1, sem, ctype))
    courses = pd.DataFrame(c_rows, columns=[
        "CourseID", "CourseName", "DepartmentID", "Semester", "CourseType"])
    courses.insert(3, "Credits", rng.choice([4, 5, 6], len(courses), p=[0.4, 0.4, 0.2]))

    n_c = len(courses)
    difficulty = np.zeros(n_c + 1)
    difficulty[1:] = rng.normal(0, 0.4, n_c)
    hard = ["Oliy matematika II", "Ekonometrika", "Korporativ moliya", "Moliyaviy hisob",
            "Materiallar qarshiligi", "Elektr zanjirlari nazariyasi",
            "Ma'lumotlar tuzilmasi va algoritmlar", "Jinoyat protsessi",
            "Ehtimollar nazariyasi va statistika", "Sinxron tarjima"]
    difficulty[courses.loc[courses.CourseName.isin(hard), "CourseID"].to_numpy()] += 0.9

    # curriculum[faculty, semester] -> the 5 courses a student takes
    curriculum = np.zeros((6, 8, 5), dtype=int)
    for f in range(6):
        for sem in range(8):
            curriculum[f, sem] = [2 * sem + 1, 2 * sem + 2] + [
                16 + f * 24 + sem * 3 + j + 1 for j in range(3)]

    # every course is taught in sections; a student's section decides the teacher
    course_teachers = np.zeros((n_c + 1, 7), dtype=int)
    n_sections = np.ones(n_c + 1, dtype=int)
    for cid, dept in zip(courses.CourseID, courses.DepartmentID):
        pool = np.array(dept_teachers[dept])
        w = np.array([4, 3] + [1] * (len(pool) - 2), dtype=float)
        m = 7 if cid <= 16 else int(rng.integers(3, 5))
        picked = rng.choice(pool, size=m, replace=False, p=w / w.sum())
        course_teachers[cid, :m] = picked
        n_sections[cid] = m

    teacher_quality = np.zeros(len(teachers) + 1)
    teacher_quality[1:] = rng.normal(0, 0.12, len(teachers))

    return {
        "faculties": faculties, "departments": departments, "teachers": teachers,
        "courses": courses, "difficulty": difficulty, "curriculum": curriculum,
        "course_teachers": course_teachers, "n_sections": n_sections,
        "teacher_quality": teacher_quality,
        "credits": np.concatenate([[0], courses.Credits.to_numpy()]),
        "anomaly_course": int(courses.loc[
            courses.CourseName == ANOMALIES["exam_failure_spike"]["course_name"],
            "CourseID"].iloc[0]),
    }


# ------------------------------------------------------------------ students
def add_cohort(state: dict, year: int) -> None:
    rng = state["rng"]
    n = int(COHORT_SIZE * (1 + 0.03 * (year - BASE_YEAR)))
    first_id = state["counters"]["student"] + 1
    state["counters"]["student"] += n

    fac = rng.choice(6, n, p=ref.FACULTY_SHARE) + 1
    female = rng.random(n) < np.array(ref.FEMALE_SHARE)[fac - 1]
    ability = rng.normal(0, 1, n)
    grant = rng.random(n) < sigmoid(-1.35 + 0.9 * ability)
    finstress = rng.normal(0, 1, n) - 0.5 * grant
    engagement = 0.45 * ability - 0.25 * np.maximum(finstress, 0) + rng.normal(0, 0.85, n)
    stipend = (ability + rng.normal(0, 0.6, n)) > 0.6

    first = np.where(female, rng.choice(ref.FEMALE_NAMES, n), rng.choice(ref.MALE_NAMES, n))
    last = rng.choice(ref.LAST_NAMES, n)
    last = np.where(female, np.char.add(last.astype(str), "a"), last)
    dob = np.datetime64(f"{year - 20}-01-01") + rng.integers(0, 365 * 3, n).astype("timedelta64[D]")

    # academic groups of about 25 students, named like "IQ-22-03"
    per_faculty = np.bincount(fac, minlength=7)
    group_no = rng.integers(1, np.maximum(per_faculty[fac] // 25, 1) + 1)
    groups = [f"{ref.FACULTY_CODES[f - 1]}-{year % 100}-{g:02d}" for f, g in zip(fac, group_no)]

    cohort = pd.DataFrame({
        "StudentID": np.arange(first_id, first_id + n),
        "FirstName": first, "LastName": last, "GroupName": groups,
        "Gender": np.where(female, ref.GENDER[1], ref.GENDER[0]),
        "DateOfBirth": dob,
        "FacultyID": fac,
        "DepartmentID": (fac - 1) * 3 + rng.integers(1, 4, n),
        "EnrollmentYear": year,
        "ScholarshipStatus": np.where(stipend, ref.SCHOLARSHIP[0], ref.SCHOLARSHIP[1]),
        "TuitionStatus": np.where(grant, ref.TUITION_STATUS[0], ref.TUITION_STATUS[1]),
        "Status": ref.STUDENT_STATUS[0],
        "StatusDate": pd.NaT,
        # hidden traits - never written to the raw files
        "_ability": ability, "_engagement": engagement, "_finstress": finstress,
        "_decline": rng.random(n) < 0.12,
    })
    state["students"] = pd.concat([state["students"], cohort], ignore_index=True)
    state["cohorts"].append(year)


def _ids(state, key, n):
    start = state["counters"][key] + 1
    state["counters"][key] += n
    return np.arange(start, start + n)


# ------------------------------------------------------------- one semester
def gen_semester(state: dict, s: int) -> dict:
    rng, R = state["rng"], state["ref"]
    info = semester_info(s)
    if s % 2 == 0 and info["year"] not in state["cohorts"]:
        add_cohort(state, info["year"])

    st = state["students"]
    study_sem = s - 2 * (st["EnrollmentYear"].to_numpy() - BASE_YEAR) + 1
    idx = np.flatnonzero((st["Status"].to_numpy() == ref.STUDENT_STATUS[0])
                         & (study_sem >= 1) & (study_sem <= 8))
    n = len(idx)
    ss = study_sem[idx]
    sid = st["StudentID"].to_numpy()[idx]
    fac = st["FacultyID"].to_numpy()[idx]
    ability = st["_ability"].to_numpy()[idx]
    finstress = st["_finstress"].to_numpy()[idx]
    decline = st["_decline"].to_numpy()[idx]
    engagement = (st["_engagement"].to_numpy()[idx] - decline * 0.22 * (ss - 1)
                  + rng.normal(0, 0.25, n))

    fac_base = np.array([f[4] for f in ref.FACULTIES])
    fac_trend = np.array([f[5] for f in ref.FACULTIES])
    fac_eff = fac_base[fac - 1] + fac_trend[fac - 1] * max(0, s - 3)
    a1 = ANOMALIES["attendance_drop"]
    att_shock = np.where((fac == a1["faculty_id"]) & (s == a1["semester_index"]),
                         a1["logit_shift"], 0.0)

    start, end = np.datetime64(info["start"]), np.datetime64(info["end"])

    # ---- tuition invoices (one per contract student per semester)
    contract = st["TuitionStatus"].to_numpy()[idx] == ref.TUITION_STATUS[1]
    tuition = np.round(np.array([f[3] for f in ref.FACULTIES])[fac - 1]
                       * (1 + 0.08 * (info["year"] - BASE_YEAR)) / 2, -5)
    struggling = (finstress + rng.normal(0, 0.4, n)) > 0.75
    paid_frac = np.where(
        struggling,
        np.clip(1 - 0.3 * (finstress - 0.75) - rng.uniform(0, 0.55, n), 0, 0.95), 1.0)
    paid = np.round(tuition * paid_frac, -4)
    remaining = tuition - paid
    debt_ratio = np.where(contract, remaining / tuition, 0.0)
    pay_date = (start + rng.integers(0, 40, n).astype("timedelta64[D]")
                + np.where(struggling, rng.integers(20, 90, n), 0).astype("timedelta64[D]"))
    pay_status = np.select([remaining == 0, paid > 0],
                           [ref.PAYMENT_STATUS[0], ref.PAYMENT_STATUS[1]],
                           ref.PAYMENT_STATUS[2])
    c = contract
    payments = pd.DataFrame({
        "PaymentID": _ids(state, "payment", int(c.sum())), "StudentID": sid[c],
        "TuitionAmount": tuition[c], "PaidAmount": paid[c], "RemainingDebt": remaining[c],
        "PaymentDate": pay_date[c], "PaymentStatus": pay_status[c]})

    # ---- enrollments: 5 courses per student
    def rep(x):
        return np.repeat(x, 5)

    CID = R["curriculum"][fac - 1, ss - 1].ravel()
    SID = rep(sid)
    N = n * 5
    TID = R["course_teachers"][CID, SID % R["n_sections"][CID]]
    load = np.bincount(TID, minlength=len(R["teacher_quality"]))
    active = load > 0
    load_z = (load - load[active].mean()) / load[active].std()
    diff = R["difficulty"][CID]

    enrollments = pd.DataFrame({
        "EnrollmentID": _ids(state, "enrollment", N), "StudentID": SID, "CourseID": CID,
        "TeacherID": TID, "Semester": info["name"], "AcademicYear": info["academic_year"]})

    # ---- attendance
    p_att = sigmoid(3.0 + 0.95 * rep(engagement) + 0.45 * rep(fac_eff) + rep(att_shock)
                    - 0.2 * diff + rng.normal(0, 0.45, N))
    present = rng.random((N, SESSIONS)) < p_att[:, None]
    att_obs = present.mean(1)
    offsets = np.arange(SESSIONS) * 10 + 8
    att_dates = start + (offsets[None, :] + (CID % 5)[:, None]).astype("timedelta64[D]")
    weekday = (att_dates.astype("datetime64[D]").astype(np.int64) + 3) % 7
    att_dates = att_dates + np.where(weekday >= 5, 2, 0).astype("timedelta64[D]")
    excused = rng.random((N, SESSIONS)) < 0.35
    # attendance rule: too many unexcused absences -> no admission to the final control
    admitted = (~present & ~excused).mean(1) <= config.MAX_UNEXCUSED_ABSENCE
    att_status = np.where(present, ref.ATTENDANCE[0],
                          np.where(excused, ref.ATTENDANCE[2], ref.ATTENDANCE[1]))
    attendance = pd.DataFrame({
        "AttendanceID": _ids(state, "attendance", N * SESSIONS),
        "StudentID": np.repeat(SID, SESSIONS), "CourseID": np.repeat(CID, SESSIONS),
        "Date": att_dates.ravel(), "Status": att_status.ravel()})

    # ---- assignments: 2 per course
    p_sub = sigmoid(2.9 + 1.1 * rep(engagement) - 0.2 * diff + rng.normal(0, 0.5, N))
    submitted = rng.random((N, 2)) < p_sub[:, None]
    late = submitted & (rng.random((N, 2)) < 0.15)
    a_score = np.round(78 + 9 * (0.5 * rep(ability) + 0.7 * rep(engagement))[:, None]
                       - 4 * diff[:, None] + rng.normal(0, 8, (N, 2)))
    a_score = np.clip(np.where(late, a_score - 10, a_score), 0, 100)
    a_score = np.where(submitted, a_score, 0)
    due = start + np.array([45, 95]).astype("timedelta64[D]")
    sub_date = np.where(late, due[None, :] + rng.integers(1, 10, (N, 2)).astype("timedelta64[D]"),
                        due[None, :] - rng.integers(0, 6, (N, 2)).astype("timedelta64[D]"))
    sub_date = np.where(submitted, sub_date, np.datetime64("NaT", "D"))
    sub_status = np.where(late, ref.SUBMISSION[1],
                          np.where(submitted, ref.SUBMISSION[0], ref.SUBMISSION[2]))
    assignments = pd.DataFrame({
        "AssignmentID": _ids(state, "assignment", N * 2),
        "StudentID": np.repeat(SID, 2), "CourseID": np.repeat(CID, 2),
        "SubmissionDate": sub_date.ravel(), "Score": a_score.ravel(),
        "SubmissionStatus": sub_status.ravel(),
        "DueDate": np.tile(due, N)})

    # ---- grades
    perf = (0.8 * rep(ability) + 0.5 * rep(engagement) + 0.5 * rep(fac_eff) - 0.7 * diff
            - 0.12 * load_z[TID] + R["teacher_quality"][TID] + 1.5 * (att_obs - 0.90)
            + rng.normal(0, 0.45, N))
    a2 = ANOMALIES["exam_failure_spike"]
    exam_shock = np.where((CID == R["anomaly_course"]) & (s == a2["semester_index"]),
                          a2["final_score_shift"], 0)
    # 100-point system: joriy (current) + oraliq (midterm) + yakuniy (final) control.
    # Each control is simulated as a percentage and scaled to its maximum.
    mx = config.SCORE_MAX
    current = np.clip(np.round((a_score.mean(1) + 7 + rng.normal(0, 4, N)) / 100 * mx["current"]),
                      0, mx["current"])
    midterm = np.round(np.clip(82 + 10 * perf + rng.normal(0, 7, N), 0, 100) / 100 * mx["midterm"])
    final = np.round(np.clip(81 + 11 * perf + exam_shock + rng.normal(0, 8, N), 0, 100)
                     / 100 * mx["final"])
    final = np.where(admitted, final, 0)
    att_score = np.round(att_obs * 100, 1)
    total = current + midterm + final
    lowest = config.GRADE_SCALE[-1]
    letters = np.full(N, lowest[1], dtype=object)
    points = np.full(N, lowest[2])
    for lo, letter, pts in reversed(config.GRADE_SCALE):
        hit = total >= lo
        letters[hit], points[hit] = letter, pts
    grades = pd.DataFrame({
        "GradeID": _ids(state, "grade", N), "StudentID": SID, "CourseID": CID,
        "CurrentScore": current, "MidtermScore": midterm, "FinalScore": final,
        "AttendanceScore": att_score,
        "ExamAdmitted": np.where(admitted, ref.YES_NO[0], ref.YES_NO[1]),
        "FinalGrade": letters, "GPA": points})

    # ---- semester outcome per student -> warnings, dropout, graduation
    credits = R["credits"][CID].reshape(n, 5)
    gpa = (points.reshape(n, 5) * credits).sum(1) / credits.sum(1)
    fails = (points.reshape(n, 5) == lowest[2]).sum(1)
    att_s = att_obs.reshape(n, 5).mean(1)

    w_date = end + rng.integers(3, 12, n).astype("timedelta64[D]")
    issued = rng.random((n, 4)) < 0.85
    w_frames = []
    for k, (cond, severe) in enumerate([
            (gpa < config.AT_RISK_GPA, gpa < 2.6), (att_s < 0.75, att_s < 0.60),
            (fails >= 2, fails >= 3), (debt_ratio > 0.5, debt_ratio > 0.8)]):
        m = cond & issued[:, k]
        w_frames.append(pd.DataFrame({
            "StudentID": sid[m], "WarningType": ref.WARNING_TYPES[k], "WarningDate": w_date[m],
            "Severity": np.where(severe[m], ref.SEVERITY[1], ref.SEVERITY[0])}))
    warnings = pd.concat(w_frames, ignore_index=True)
    warnings.insert(0, "WarningID", _ids(state, "warning", len(warnings)))

    p_drop = sigmoid(-5.9 + 1.7 * (gpa < 2.8) + 0.9 * (fails >= 2) + 1.2 * (att_s < 0.70)
                     + 0.9 * (debt_ratio > 0.4) + 0.5 * decline)
    dropped = rng.random(n) < p_drop
    graduated = (ss == 8) & ~dropped
    status = st["Status"].to_numpy().copy()
    status_date = st["StatusDate"].to_numpy().copy()
    status[idx[dropped]] = ref.STUDENT_STATUS[1]
    status_date[idx[dropped]] = end + np.timedelta64(10, "D")
    status[idx[graduated]] = ref.STUDENT_STATUS[2]
    status_date[idx[graduated]] = end + np.timedelta64(15, "D")
    st["Status"], st["StatusDate"] = status, status_date

    state["next_s"] = s + 1
    return {"enrollments": enrollments, "grades": grades, "attendance": attendance,
            "assignments": assignments, "payments": payments,
            "academic_warnings": warnings}


# ---------------------------------------------------------- dirty raw files
def inject_dirt(frames: dict, rng) -> dict:
    """Plant realistic data-quality problems for the ETL pipeline to catch."""
    out = {k: v.copy() for k, v in frames.items()}

    def dup(df, frac):
        k = max(1, int(len(df) * frac))
        return pd.concat([df, df.sample(k, random_state=int(rng.integers(1e9)))],
                         ignore_index=True)

    def pick(df, frac):
        return rng.choice(len(df), max(1, int(len(df) * frac)), replace=False)

    g = out["grades"]
    g["MidtermScore"] = g["MidtermScore"].astype(object)
    g.iloc[pick(g, 0.0015), g.columns.get_loc("MidtermScore")] = None       # missing
    g.iloc[pick(g, 0.0004), g.columns.get_loc("FinalScore")] = 150          # out of range
    g.iloc[pick(g, 0.0002), g.columns.get_loc("FinalScore")] = -10
    out["grades"] = dup(g, 0.002)

    a = out["attendance"]
    a["Status"] = a["Status"].astype(object)
    a["Date"] = a["Date"].dt.strftime("%Y-%m-%d")
    col = a.columns.get_loc("Status")
    for variant, frac in ((str.upper, 0.004), (str.lower, 0.004), (lambda x: f" {x} ", 0.004)):
        rows = pick(a, frac)
        a.iloc[rows, col] = [variant(v) for v in a.iloc[rows, col]]
    a.iloc[pick(a, 0.0003), a.columns.get_loc("StudentID")] = 9_000_000 + rng.integers(1, 999)
    a.iloc[pick(a, 0.0002), a.columns.get_loc("Date")] = "2099-12-31"       # impossible date
    a.iloc[pick(a, 0.0002), a.columns.get_loc("Date")] = "noma'lum"         # not a date
    out["attendance"] = dup(a, 0.002)

    p = out["payments"]
    p["PaidAmount"] = p["PaidAmount"].astype(object)
    col = p.columns.get_loc("PaidAmount")
    rows = pick(p, 0.01)
    p.iloc[rows, col] = [f"{int(v):,}".replace(",", " ") for v in p.iloc[rows, col]]  # "8 000 000"
    p.iloc[pick(p, 0.0005), col] = -500000                                   # negative
    out["payments"] = dup(p, 0.001)

    s = out["assignments"]
    s.iloc[pick(s, 0.0004), s.columns.get_loc("Score")] = 1000              # outlier
    s.iloc[pick(s, 0.0002), s.columns.get_loc("CourseID")] = 9999           # orphan course
    out["assignments"] = dup(s, 0.001)

    out["enrollments"] = dup(out["enrollments"], 0.001)
    return out


def dirty_students(students: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(7)  # fixed: the same rows are dirty in every snapshot
    s = students.copy()
    s["DateOfBirth"] = s["DateOfBirth"].dt.strftime("%Y-%m-%d")
    n = len(s)
    rows = rng.choice(n, int(n * 0.02), replace=False)                      # dd.mm.yyyy
    s.iloc[rows, s.columns.get_loc("DateOfBirth")] = pd.to_datetime(
        s.iloc[rows]["DateOfBirth"]).dt.strftime("%d.%m.%Y").to_numpy()
    s.iloc[rng.choice(n, int(n * 0.005), replace=False), s.columns.get_loc("Gender")] = None
    rows = rng.choice(n, int(n * 0.01), replace=False)
    s.iloc[rows, s.columns.get_loc("FirstName")] = [
        f"  {v.lower()} " for v in s.iloc[rows]["FirstName"]]
    return pd.concat([s, s.iloc[rng.choice(n, 15, replace=False)]], ignore_index=True)


# -------------------------------------------------------------------- output
def write_reference(R: dict) -> None:
    for name in ("faculties", "departments"):
        (config.RAW_DIR / f"{name}.json").write_text(
            json.dumps(R[name].to_dict("records"), ensure_ascii=False, indent=2),
            encoding="utf-8")
    R["teachers"].to_excel(config.RAW_DIR / "teachers.xlsx", index=False)
    R["courses"].to_csv(config.RAW_DIR / "courses.csv", index=False, encoding="utf-8")


def write_students(state: dict) -> None:
    st = state["students"]
    out = st[[c for c in st.columns if not c.startswith("_")]].copy()
    last_s = state["next_s"] - 1
    out.insert(8, "StudyYear", np.clip(
        (last_s - 2 * (out["EnrollmentYear"] - BASE_YEAR)) // 2 + 1, 1, 4))
    dirty_students(out).to_csv(config.RAW_DIR / "students.csv", index=False, encoding="utf-8")


def write_batch(frames: dict, tag: str) -> None:
    for name, df in frames.items():
        df.to_csv(config.RAW_DIR / f"{name}_{tag}.csv", index=False, encoding="utf-8",
                  date_format="%Y-%m-%d")
        print(f"  {name}_{tag}.csv: {len(df):,} rows")


def reset() -> None:
    for d in (config.RAW_DIR, config.STATE_DIR):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    rng = np.random.default_rng(42)
    state = {"rng": rng, "ref": build_reference(rng), "students": pd.DataFrame(),
             "cohorts": [], "next_s": 0,
             "counters": dict.fromkeys(
                 ["student", "enrollment", "grade", "attendance", "assignment",
                  "payment", "warning"], 0)}
    batches = [gen_semester(state, s) for s in range(INITIAL_SEMESTERS)]
    frames = {k: pd.concat([b[k] for b in batches], ignore_index=True) for k in batches[0]}
    write_reference(state["ref"])
    write_students(state)
    write_batch(inject_dirt(frames, rng), "2022-2026")
    STATE_FILE.write_bytes(pickle.dumps(state))
    st = state["students"]
    print(f"students: {len(st):,} | status: {st['Status'].value_counts().to_dict()}")


def next_semester() -> None:
    state = pickle.loads(STATE_FILE.read_bytes())
    s = state["next_s"]
    info = semester_info(s)
    print(f"Generating {info['academic_year']} {info['name']} (semester index {s})")
    frames = gen_semester(state, s)
    write_students(state)
    write_batch(inject_dirt(frames, state["rng"]),
                f"{info['academic_year']}_{info['name'].lower()}")
    STATE_FILE.write_bytes(pickle.dumps(state))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--reset", action="store_true", help="regenerate everything")
    grp.add_argument("--next-semester", action="store_true", help="append one semester")
    args = ap.parse_args()
    reset() if args.reset else next_semester()
