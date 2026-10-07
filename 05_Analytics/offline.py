"""Offline copy of the warehouse, for running the dashboard where SQL Server
cannot be reached (the hosted demo).

    python 05_Analytics/offline.py        # export the current warehouse to 01_Data/offline

The export saves exactly what the dashboard reads from the database - the
frames of metrics.load_all(), the per-student grades and warnings, the ETL
logs and the model's input snapshot - as Parquet files. When config.OFFLINE
is on, the loading functions in metrics.py and risk_model.py read these files
instead of querying, so every page shows the same figures as on the day of
the export. Nothing can be written back: the pipeline, free SQL and
intervention records are switched off in that mode.
"""
import json
import sys
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

DIR = config.OFFLINE_DIR
META = DIR / "meta.json"


@lru_cache(maxsize=None)
def meta() -> dict:
    return json.loads(META.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _table(name: str) -> pd.DataFrame:
    return pd.read_parquet(DIR / f"{name}.parquet")


def table(name: str) -> pd.DataFrame:
    """One saved table. A copy, so callers can change it as they would a query result."""
    return _table(name).copy()


def load_all() -> dict:
    """What metrics.load_all(engine) returned when the export was made."""
    d = {key: table(f"all_{key}") for key in meta()["frames"]}
    d.update(meta()["scalars"])
    return d


def for_student(name: str, student_key: int) -> pd.DataFrame:
    """Rows of one student from a per-student table (grades, warnings)."""
    t = _table(name)
    return t[t.StudentKey == student_key].drop(columns="StudentKey").reset_index(drop=True)


def export(engine) -> dict:
    """Save the warehouse as it is now. Returns {file: rows}."""
    from sqlalchemy import text

    import metrics as m

    assert not config.OFFLINE, "export needs the live warehouse"
    DIR.mkdir(parents=True, exist_ok=True)
    for old in DIR.glob("*.parquet"):
        old.unlink()
    written, frames, scalars = {}, [], {}

    def save(name: str, df: pd.DataFrame):
        df.to_parquet(DIR / f"{name}.parquet", index=False, compression="zstd")
        written[name] = len(df)

    for key, value in m.load_all(engine).items():
        if isinstance(value, pd.DataFrame):
            save(f"all_{key}", value)
            frames.append(key)
        else:
            scalars[key] = value

    # the two per-student queries of metrics.student_profile, for every student
    save("grades", pd.read_sql(text("""
        SELECT g.StudentKey, s.SemesterLabel, c.CourseName, t.TeacherName, g.CurrentScore, g.MidtermScore,
               g.FinalScore, g.TotalScore, g.FinalGrade, g.AttendanceScore,
               IIF(g.IsAdmitted = 1, N'Ha', N'Yo''q') AS Admitted, g.SemesterKey
        FROM dw.FactGrades g
        JOIN dw.DimCourse c ON c.CourseKey = g.CourseKey
        JOIN dw.DimTeacher t ON t.TeacherKey = g.TeacherKey
        JOIN dw.DimSemester s ON s.SemesterKey = g.SemesterKey
        ORDER BY g.StudentKey, g.SemesterKey, c.CourseName"""), engine))
    save("warnings", pd.read_sql(text("""
        SELECT w.StudentKey, d.[Date] AS WarningDate, w.WarningType, w.Severity FROM dw.FactWarnings w
        JOIN dw.DimDate d ON d.DateKey = w.DateKey ORDER BY w.StudentKey, 2"""), engine))
    # metrics.data_quality
    save("etl_files", pd.read_sql(text("SELECT * FROM etl.FileLog ORDER BY ProcessedAt DESC"), engine))
    save("etl_checks", pd.read_sql(text("SELECT * FROM etl.DataQualityLog"), engine))
    save("etl_runs", pd.read_sql(text("SELECT TOP 20 * FROM etl.RunLog ORDER BY RunID DESC"), engine))
    # risk_model.load_snapshot (input of the what-if simulation)
    save("ml_snapshot", pd.read_sql(text(
        "SELECT ss.*, s.Status FROM dw.FactStudentSemester ss "
        "JOIN dw.DimStudent s ON s.StudentKey = ss.StudentKey"), engine))

    META.write_text(json.dumps({
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "version": m.data_version(engine), "frames": frames, "scalars": scalars,
        "rows": written}, ensure_ascii=False, indent=1), encoding="utf-8")
    meta.cache_clear()
    _table.cache_clear()
    return written


if __name__ == "__main__":
    out = export(config.get_engine())
    size = sum(f.stat().st_size for f in DIR.glob("*.parquet")) / 1e6
    for name, rows in out.items():
        print(f"{name:<24}{rows:>10,}")
    print(f"\n{len(out)} files, {size:.1f} MB -> {DIR}")
