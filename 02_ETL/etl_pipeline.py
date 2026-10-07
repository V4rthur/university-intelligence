"""Python ETL pipeline (PHASE 4): raw files -> staging -> SQL Server warehouse.

    RAW FILES (CSV / Excel / JSON in 01_Data/raw)
        |  1. EXTRACT       read new or changed files only (MD5 hash in etl.FileLog)
        |  2. CLEAN         trim, standardise categories, fix types and date formats,
        |                   fill or impute missing values, remove duplicates
        |  3. VALIDATE      range rules, outlier flags, referential integrity;
        |                   bad rows are quarantined in etl.RejectedRecords
        |  4. STAGE         load the clean rows into stg.* tables
        |  5. TRANSFORM +   MERGE staging into the star schema (dw.*), deriving
        |     LOAD          keys and columns; then rebuild the analytical snapshot
        |  6. TEST          post-load checks; results in etl.RunLog / etl.LoadAudit
        v
    DATA WAREHOUSE  ->  dashboard, ML models, AI agent

Idempotent: every warehouse load is a MERGE on the primary key and unchanged
files are skipped, so running the pipeline again never duplicates data.

Usage
    python 02_ETL/etl_pipeline.py            # incremental: new / changed files
    python 02_ETL/etl_pipeline.py --full     # re-process every file
    python 02_ETL/etl_pipeline.py --rebuild  # drop the database and load from scratch
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import reference_uz as ref  # noqa: E402

FACT_DATES = ("2022-01-01", "2033-08-31")   # range covered by dw.DimDate
MAX_REJECT_SAMPLES = 300                    # rejected rows kept per file and reason
SCORE = (0, 100)

# Declarative cleaning / validation rules, in load order (parents first).
SPECS = {
    "faculties": dict(stg="Faculties", pk="FacultyID", ints=["FacultyID", "EstablishedYear"],
                      required=["FacultyID", "FacultyName"]),
    "departments": dict(stg="Departments", pk="DepartmentID", ints=["DepartmentID", "FacultyID"],
                        required=["DepartmentID", "DepartmentName", "FacultyID"],
                        fks={"FacultyID": "faculties"}),
    "teachers": dict(stg="Teachers", pk="TeacherID",
                     ints=["TeacherID", "DepartmentID", "ExperienceYears"],
                     cats={"AcademicDegree": ref.DEGREES, "EmploymentType": ref.EMPLOYMENT},
                     required=["TeacherID", "TeacherName", "DepartmentID"],
                     fks={"DepartmentID": "departments"}),
    "courses": dict(stg="Courses", pk="CourseID",
                    ints=["CourseID", "DepartmentID", "Credits", "Semester"],
                    cats={"CourseType": ref.COURSE_TYPE},
                    required=["CourseID", "CourseName", "DepartmentID", "Credits", "Semester"],
                    ranges={"Semester": (1, 8), "Credits": (1, 12)},
                    fks={"DepartmentID": "departments"}),
    "students": dict(stg="Students", pk="StudentID",
                     ints=["StudentID", "FacultyID", "DepartmentID", "EnrollmentYear", "StudyYear"],
                     dates=["DateOfBirth", "StatusDate"], names=["FirstName", "LastName"],
                     cats={"Gender": ref.GENDER, "ScholarshipStatus": ref.SCHOLARSHIP,
                           "TuitionStatus": ref.TUITION_STATUS, "Status": ref.STUDENT_STATUS},
                     defaults={"Gender": "Ko'rsatilmagan"},
                     required=["StudentID", "FirstName", "LastName", "GroupName", "FacultyID", "DepartmentID",
                               "EnrollmentYear", "StudyYear", "Status"],
                     ranges={"StudyYear": (1, 4)},
                     fks={"FacultyID": "faculties", "DepartmentID": "departments"}),
    "enrollments": dict(stg="Enrollments", pk="EnrollmentID",
                        ints=["EnrollmentID", "StudentID", "CourseID", "TeacherID"],
                        cats={"Semester": ref.SEMESTER_NAMES},
                        required=["EnrollmentID", "StudentID", "CourseID", "TeacherID",
                                  "Semester", "AcademicYear"],
                        fks={"StudentID": "students", "CourseID": "courses",
                             "TeacherID": "teachers"}),
    "grades": dict(stg="Grades", pk="GradeID", ints=["GradeID", "StudentID", "CourseID"],
                   floats=["CurrentScore", "MidtermScore", "FinalScore", "AttendanceScore", "GPA"],
                   cats={"FinalGrade": [g[1] for g in config.GRADE_SCALE],
                         "ExamAdmitted": ref.YES_NO},
                   impute_median={"MidtermScore": "CourseID"},
                   required=["GradeID", "StudentID", "CourseID", "CurrentScore", "MidtermScore",
                             "FinalScore", "AttendanceScore", "ExamAdmitted", "FinalGrade", "GPA"],
                   outliers=["MidtermScore", "FinalScore"],
                   # each control is valid only up to its own maximum (20 / 30 / 50)
                   ranges={"CurrentScore": (0, config.SCORE_MAX["current"]),
                           "MidtermScore": (0, config.SCORE_MAX["midterm"]),
                           "FinalScore": (0, config.SCORE_MAX["final"]),
                           "AttendanceScore": SCORE, "GPA": (2, 5)},
                   fks={"StudentID": "students", "CourseID": "courses"}),
    "attendance": dict(stg="Attendance", pk="AttendanceID",
                       ints=["AttendanceID", "StudentID", "CourseID"], dates=["Date"],
                       cats={"Status": ref.ATTENDANCE},
                       required=["AttendanceID", "StudentID", "CourseID", "Date", "Status"],
                       date_ranges={"Date": FACT_DATES},
                       fks={"StudentID": "students", "CourseID": "courses"}),
    "payments": dict(stg="Payments", pk="PaymentID", ints=["PaymentID", "StudentID"],
                     floats=["TuitionAmount", "PaidAmount", "RemainingDebt"],
                     dates=["PaymentDate"], cats={"PaymentStatus": ref.PAYMENT_STATUS},
                     required=["PaymentID", "StudentID", "TuitionAmount", "PaidAmount", "PaymentDate"],
                     outliers=["PaidAmount"],
                     ranges={"TuitionAmount": (1, 1e9), "PaidAmount": (0, 1e9)},
                     date_ranges={"PaymentDate": FACT_DATES}, fks={"StudentID": "students"}),
    "assignments": dict(stg="Assignments", pk="AssignmentID",
                        ints=["AssignmentID", "StudentID", "CourseID"], floats=["Score"],
                        dates=["SubmissionDate", "DueDate"], cats={"SubmissionStatus": ref.SUBMISSION},
                        required=["AssignmentID", "StudentID", "CourseID", "Score",
                                  "SubmissionStatus", "DueDate"],
                        outliers=["Score"], ranges={"Score": SCORE},
                        date_ranges={"DueDate": FACT_DATES},
                        fks={"StudentID": "students", "CourseID": "courses"}),
    "academic_warnings": dict(stg="AcademicWarnings", pk="WarningID",
                              ints=["WarningID", "StudentID"], dates=["WarningDate"],
                              cats={"WarningType": ref.WARNING_TYPES, "Severity": ref.SEVERITY},
                              required=["WarningID", "StudentID", "WarningType", "WarningDate",
                                        "Severity"],
                              date_ranges={"WarningDate": FACT_DATES},
                              fks={"StudentID": "students"}),
}
DW_KEYS = {"faculties": ("DimFaculty", "FacultyKey"), "departments": ("DimDepartment", "DepartmentKey"),
           "teachers": ("DimTeacher", "TeacherKey"), "courses": ("DimCourse", "CourseKey"),
           "students": ("DimStudent", "StudentKey")}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ----------------------------------------------------------------- database
def ensure_database() -> None:
    eng = config.get_engine("master")
    with eng.connect().execution_options(isolation_level="AUTOCOMMIT") as con:
        con.execute(text(
            f"IF DB_ID('{config.SQL_DATABASE}') IS NULL BEGIN "
            f"CREATE DATABASE [{config.SQL_DATABASE}]; "
            f"ALTER DATABASE [{config.SQL_DATABASE}] SET RECOVERY SIMPLE; END"))
    eng.dispose()


def drop_database() -> None:
    """Remove this project's own database so it can be rebuilt from the raw files."""
    eng = config.get_engine("master")
    with eng.connect().execution_options(isolation_level="AUTOCOMMIT") as con:
        con.execute(text(
            f"IF DB_ID('{config.SQL_DATABASE}') IS NOT NULL BEGIN "
            f"ALTER DATABASE [{config.SQL_DATABASE}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; "
            f"DROP DATABASE [{config.SQL_DATABASE}]; END"))
    eng.dispose()


def run_sql_file(engine, path: Path) -> None:
    batches, cur = [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().upper() == "GO":
            batches.append("\n".join(cur))
            cur = []
        else:
            cur.append(line)
    batches.append("\n".join(cur))
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as con:
        for b in batches:
            if b.strip():
                con.exec_driver_sql(b)


def deploy_schema(engine) -> None:
    for folder in (config.SQL_DIR, config.DW_DIR):
        for f in sorted(folder.glob("*.sql")):
            run_sql_file(engine, f)


# ------------------------------------------------------------------ extract
def file_hash(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_raw(path: Path) -> pd.DataFrame:
    """Read any supported source format as text; typing happens in clean()."""
    if path.suffix == ".csv":
        return pd.read_csv(path, dtype=str, encoding="utf-8")
    if path.suffix == ".json":
        return pd.DataFrame(json.loads(path.read_text(encoding="utf-8"))).astype(str)
    if path.suffix == ".xlsx":
        return pd.read_excel(path, dtype=str)
    raise ValueError(f"unsupported file type: {path.name}")


def discover(table: str) -> list[Path]:
    files = [p for p in sorted(config.RAW_DIR.iterdir())
             if p.suffix in (".csv", ".json", ".xlsx")
             and (p.stem == table or p.stem.startswith(table + "_"))]
    return files


# --------------------------------------------------------- clean + validate
def clean(table: str, raw: pd.DataFrame, keys: dict) -> tuple[pd.DataFrame, pd.DataFrame, list]:
    """Return (clean rows, rejected raw rows with a Reason column, DQ records)."""
    spec = SPECS[table]
    df = raw.copy()
    dq: list[tuple[str, str, int]] = []           # (check, action, count)
    reason = pd.Series(pd.NA, index=df.index, dtype="object")

    def reject(mask, why):
        mask = mask & reason.isna()
        reason[mask] = why
        if mask.any():
            dq.append((why, "REJECTED", int(mask.sum())))

    def fixed(mask, what):
        if mask.any():
            dq.append((what, "FIXED", int(mask.sum())))

    # 1. whitespace: trim every text value, empty string -> missing
    untrimmed = pd.Series(False, index=df.index)
    for c in df.columns:
        s = df[c].astype("string")
        t = s.str.strip()
        untrimmed |= (s != t).fillna(False)
        t = t.mask(t == "")
        df[c] = t.astype(object).where(t.notna(), None)
    fixed(untrimmed, "whitespace_trimmed")

    # 2. duplicates on the primary key (keep the last occurrence)
    dup = df.duplicated(spec["pk"], keep="last") & df[spec["pk"]].notna()
    if dup.any():
        dq.append(("duplicate", "FIXED", int(dup.sum())))
        df, reason = df[~dup], reason[~dup]

    # 3. standardise text: names in proper case, categories to canonical labels
    recased = pd.Series(False, index=df.index)
    for c in spec.get("names", []):
        proper = df[c].map(lambda v: v.capitalize() if isinstance(v, str) and v.islower() else v)
        recased |= (proper != df[c]) & df[c].notna()
        df[c] = proper
    for c, allowed in spec.get("cats", {}).items():
        lookup = {a.lower(): a for a in allowed}
        canon = df[c].map(lambda v: lookup.get(v.lower()) if isinstance(v, str) else None)
        recased |= canon.notna() & (canon != df[c])
        reject(df[c].notna() & canon.isna(), "invalid_category")
        df[c] = canon
    fixed(recased, "format_standardised")

    # 4. type correction: numbers written as text ("8 000 000"), mixed date formats
    retyped = pd.Series(False, index=df.index)
    for c in spec.get("ints", []) + spec.get("floats", []):
        compact = df[c].map(lambda v: v.replace(" ", "") if isinstance(v, str) else v)
        retyped |= (compact != df[c]) & df[c].notna()
        num = pd.to_numeric(compact, errors="coerce")
        reject(df[c].notna() & num.isna(), "invalid_number")
        df[c] = num
    for c in spec.get("dates", []):
        iso = pd.to_datetime(df[c], format="%Y-%m-%d", errors="coerce")
        local = pd.to_datetime(df[c], format="%d.%m.%Y", errors="coerce")
        retyped |= iso.isna() & local.notna()
        parsed = iso.fillna(local)
        reject(df[c].notna() & parsed.isna(), "invalid_date")
        df[c] = parsed
    fixed(retyped, "type_corrected")

    # 5. missing values: default, impute, or reject when the field is required
    for c, value in spec.get("defaults", {}).items():
        miss = df[c].isna() & reason.isna()
        fixed(miss, "missing_filled")
        df.loc[miss, c] = value
    for c, by in spec.get("impute_median", {}).items():
        miss = df[c].isna() & reason.isna()
        df["Is" + c.replace("Score", "") + "Imputed"] = miss
        fixed(miss, "missing_imputed")
        df.loc[miss, c] = df.groupby(by)[c].transform("median")[miss].round(0)
    for c in spec["required"]:
        reject(df[c].isna(), "missing_required")

    # 6. outliers: flag values far outside the robust spread (median +/- 6 MAD)
    for c in spec.get("outliers", []):
        v = df.loc[reason.isna(), c].astype(float)
        mad = (v - v.median()).abs().median()
        if mad > 0:
            n_out = int((((v - v.median()).abs() / (1.4826 * mad)) > 6).sum())
            if n_out:
                dq.append((f"outlier_{c}", "FLAGGED", n_out))

    # 7. validity rules
    for c, (lo, hi) in spec.get("ranges", {}).items():
        reject(df[c].notna() & ~df[c].between(lo, hi), "out_of_range")
    for c, (lo, hi) in spec.get("date_ranges", {}).items():
        reject(df[c].notna() & ~df[c].between(pd.Timestamp(lo), pd.Timestamp(hi)), "out_of_range")

    # 8. referential integrity against the parent tables
    for c, parent in spec.get("fks", {}).items():
        reject(df[c].notna() & ~df[c].isin(keys[parent]), "orphan_key")

    # 9. derived columns
    if table == "payments":
        df["RemainingDebt"] = (df["TuitionAmount"] - df["PaidAmount"]).clip(lower=0)
        over = df["PaidAmount"] > df["TuitionAmount"]
        reject(over, "out_of_range")
        df["PaymentStatus"] = np.select(
            [df["RemainingDebt"] == 0, df["PaidAmount"] > 0],
            [ref.PAYMENT_STATUS[0], ref.PAYMENT_STATUS[1]], ref.PAYMENT_STATUS[2])

    ok = reason.isna()
    good = df[ok].copy()
    for c in spec.get("ints", []):
        good[c] = good[c].astype("Int64")
    for c in spec.get("dates", []):
        good[c] = good[c].dt.date.where(good[c].notna(), None)
    rejected = raw.loc[reason.index[~ok]].copy()
    rejected["Reason"] = reason[~ok]
    return good, rejected, dq


# --------------------------------------------------------------------- load
def stg_columns(engine, stg: str) -> list[str]:
    with engine.connect() as con:
        return [r[0] for r in con.execute(text(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA='stg' AND TABLE_NAME=:t ORDER BY ORDINAL_POSITION"), {"t": stg})]


def existing_keys(engine, parent: str) -> set:
    table, col = DW_KEYS[parent]
    with engine.connect() as con:
        return {r[0] for r in con.execute(text(f"SELECT {col} FROM dw.{table}"))}


def post_load_tests(con) -> list[tuple[str, bool, str]]:
    """Checks that must hold after every run (PHASE 4/5 exit criteria)."""
    tests = []

    def scalar(sql):
        return con.execute(text(sql)).scalar()

    for fact, pk in [("FactEnrollments", "EnrollmentID"), ("FactGrades", "GradeID"),
                     ("FactAttendance", "AttendanceID"), ("FactPayments", "PaymentID"),
                     ("FactAssignments", "AssignmentID"), ("FactWarnings", "WarningID")]:
        n, d = con.execute(text(f"SELECT COUNT(*), COUNT(DISTINCT {pk}) FROM dw.{fact}")).one()
        tests.append((f"{fact}: no duplicate keys", n == d and n > 0, f"{n:,} rows"))
    n = scalar("SELECT COUNT(*) FROM dw.FactGrades g LEFT JOIN dw.FactEnrollments e "
               "ON e.StudentKey=g.StudentKey AND e.CourseKey=g.CourseKey WHERE e.EnrollmentID IS NULL")
    tests.append(("every grade has an enrollment", n == 0, f"{n} orphans"))
    mx = config.SCORE_MAX
    n = scalar(f"SELECT COUNT(*) FROM dw.FactGrades WHERE CurrentScore NOT BETWEEN 0 AND {mx['current']} "
               f"OR MidtermScore NOT BETWEEN 0 AND {mx['midterm']} "
               f"OR FinalScore NOT BETWEEN 0 AND {mx['final']} OR GradePoints NOT BETWEEN 2 AND 5")
    tests.append(("scores within valid range", n == 0, f"{n} violations"))
    n = scalar("SELECT COUNT(*) FROM dw.FactGrades WHERE (TotalScore >= "
               f"{config.PASS_MARK} AND IsFailed = 1) OR (TotalScore < {config.PASS_MARK} AND IsFailed = 0)")
    tests.append(("grade agrees with the pass mark", n == 0, f"{n} mismatches"))
    n = scalar("SELECT COUNT(*) FROM dw.FactPayments WHERE PaidAmount + RemainingDebt <> TuitionAmount")
    tests.append(("payments: paid + debt = tuition", n == 0, f"{n} violations"))
    a, b = con.execute(text(
        "SELECT (SELECT COUNT(*) FROM dw.FactStudentSemester), "
        "(SELECT COUNT(*) FROM (SELECT DISTINCT StudentKey, SemesterKey FROM dw.FactGrades) x)")).one()
    tests.append(("snapshot covers every student-semester", a == b, f"{a:,} of {b:,}"))
    n = scalar("SELECT COUNT(*) FROM dw.FactStudentSemester WHERE AttendanceRate IS NULL "
               "OR SubmissionRate IS NULL OR StudySemester NOT BETWEEN 1 AND 8")
    tests.append(("snapshot has complete measures", n == 0, f"{n} incomplete rows"))
    return tests


def run(full: bool = False) -> dict:
    t0 = time.time()
    ensure_database()
    engine = config.get_engine()
    deploy_schema(engine)

    with engine.begin() as con:
        run_id = con.execute(text(
            "INSERT etl.RunLog OUTPUT INSERTED.RunID DEFAULT VALUES")).scalar()
        known = dict(con.execute(text("SELECT FileName, FileHash FROM etl.FileLog")).all())
        for spec in SPECS.values():
            con.execute(text(f"TRUNCATE TABLE stg.{spec['stg']}"))
    log(f"run {run_id} started ({'full' if full else 'incremental'})")

    totals = dict(files=0, read=0, loaded=0, rejected=0)
    keys: dict[str, set] = {}
    try:
        for table, spec in SPECS.items():
            parts = []
            for path in discover(table):
                digest = file_hash(path)
                if not full and known.get(path.name) == digest:
                    continue
                raw = read_raw(path)
                for parent in spec.get("fks", {}).values():
                    if parent not in keys:
                        keys[parent] = existing_keys(engine, parent)
                good, rejected, dq = clean(table, raw, keys)
                parts.append(good)
                totals["files"] += 1
                totals["read"] += len(raw)
                totals["rejected"] += len(rejected)
                log(f"  {path.name}: read {len(raw):,} | clean {len(good):,} | "
                    f"rejected {len(rejected):,} | "
                    + ", ".join(f"{c}={n}" for c, _, n in dq))
                with engine.begin() as con:
                    con.execute(text("DELETE etl.DataQualityLog WHERE FileName=:f"), {"f": path.name})
                    checks: dict[str, list] = {}
                    for c, a, n in dq:      # one row per check, even if it fired twice
                        checks.setdefault(c, [a, 0])[1] += n
                    if checks:
                        con.execute(text(
                            "INSERT etl.DataQualityLog VALUES (:f, :t, :c, :a, :n, :r)"),
                            [dict(f=path.name, t=table, c=c, a=a, n=n, r=run_id)
                             for c, (a, n) in checks.items()])
                    sample = rejected.groupby("Reason").head(MAX_REJECT_SAMPLES)
                    if len(sample):
                        con.execute(text(
                            "INSERT etl.RejectedRecords (RunID, FileName, TableName, Reason, RawRecord) "
                            "VALUES (:r, :f, :t, :why, :raw)"),
                            [dict(r=run_id, f=path.name, t=table, why=row["Reason"],
                                  raw=json.dumps(row.drop("Reason").dropna().to_dict(),
                                                 ensure_ascii=False))
                             for _, row in sample.iterrows()])
                    con.execute(text(
                        "MERGE etl.FileLog t USING (SELECT :f AS FileName) s ON t.FileName=s.FileName "
                        "WHEN MATCHED THEN UPDATE SET FileHash=:h, RowsRead=:n, RowsLoaded=:g, "
                        "RowsRejected=:x, RunID=:r, ProcessedAt=SYSDATETIME() "
                        "WHEN NOT MATCHED THEN INSERT (FileName, TableName, FileHash, RowsRead, "
                        "RowsLoaded, RowsRejected, RunID) VALUES (:f, :t, :h, :n, :g, :x, :r);"),
                        dict(f=path.name, t=table, h=digest, n=len(raw), g=len(good),
                             x=len(rejected), r=run_id))
            if not parts:
                continue
            staged = pd.concat(parts, ignore_index=True).drop_duplicates(spec["pk"], keep="last")
            if table in DW_KEYS:      # children validate against old + newly staged parents
                keys[table] = keys.get(table) or existing_keys(engine, table)
                keys[table] |= set(staged[spec["pk"]].astype(int))
            staged[stg_columns(engine, spec["stg"])].to_sql(
                spec["stg"], engine, schema="stg", if_exists="append", index=False,
                chunksize=100_000)
            totals["loaded"] += len(staged)


        log("merging staging into the warehouse")
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as con:
            con.exec_driver_sql("EXEC dw.usp_LoadDimensions ?", (run_id,))
            con.exec_driver_sql("EXEC dw.usp_LoadFacts ?", (run_id,))
            con.exec_driver_sql("EXEC dw.usp_BuildStudentSemester ?, ?",
                                (config.AT_RISK_GPA, config.AT_RISK_FAILED))
            audit = pd.read_sql(text("SELECT TableName, RowsStaged, RowsInserted, RowsUpdated, "
                                     "RowsOrphaned FROM etl.LoadAudit WHERE RunID=:r"),
                                con, params={"r": run_id})
            tests = post_load_tests(con)
        print(audit.to_string(index=False))
        for name, passed, detail in tests:
            log(f"  TEST {'PASS' if passed else 'FAIL'}  {name} ({detail})")
        failed = [t[0] for t in tests if not t[1]]
        status = "FAILED" if failed else "SUCCESS"
        message = "; ".join(failed) or f"{len(tests)} tests passed"
    except Exception as exc:
        status, message, tests = "FAILED", str(exc)[:1900], []
        raise
    finally:
        with engine.begin() as con:
            con.execute(text(
                "UPDATE etl.RunLog SET FinishedAt=SYSDATETIME(), Status=:s, FilesProcessed=:f, "
                "RowsRead=:n, RowsLoaded=:g, RowsRejected=:x, Message=:m WHERE RunID=:r"),
                dict(s=status, f=totals["files"], n=totals["read"], g=totals["loaded"],
                     x=totals["rejected"], m=message, r=run_id))
    log(f"run {run_id} {status}: {totals['files']} files, {totals['read']:,} rows read, "
        f"{totals['loaded']:,} staged, {totals['rejected']:,} rejected "
        f"in {time.time() - t0:.0f}s")
    return {"run_id": run_id, "status": status, **totals}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="University Intelligence ETL pipeline")
    ap.add_argument("--full", action="store_true", help="re-process every raw file")
    ap.add_argument("--rebuild", action="store_true",
                    help="drop the project database first, then load everything")
    args = ap.parse_args()
    if args.rebuild:
        drop_database()
    result = run(full=args.full or args.rebuild)
    sys.exit(0 if result["status"] == "SUCCESS" else 1)
