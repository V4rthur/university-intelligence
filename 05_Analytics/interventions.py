"""Interventions: what staff did for a student at risk, and how it turned out.

The risk page finds the students; this is where the follow-up is written down
(table app.Intervention, see 03_SQL/04_interventions.sql). Over time the
recorded outcomes can replace the assumed effects in the what-if scenarios.
"""
import pandas as pd
from sqlalchemy import text

import config

TYPES = ["Suhbat (kurator / tyutor)", "Qo'shimcha dars (tyutorlik)", "Ota-ona bilan aloqa",
         "Psixolog maslahati", "To'lov rejasi", "Boshqa"]
STATUSES = ["Rejalashtirilgan", "Jarayonda", "Yakunlangan"]
OUTCOMES = ["Yaxshilandi", "O'zgarishsiz", "Yomonlashdi"]      # set when the work is finished
BACKUP = config.STATE_DIR / "interventions_backup.csv"
_COLUMNS = ["StudentKey", "SemesterKey", "Type", "Status", "Outcome", "Note", "CreatedBy", "CreatedAt",
            "UpdatedBy", "UpdatedAt"]


def _writable():
    if config.OFFLINE:
        raise PermissionError("Namoyish nusxasida choralar saqlanmaydi.")


def add(engine, student_key: int, semester_key: int, kind: str, note: str, user: str) -> None:
    _writable()
    if kind not in TYPES:
        raise ValueError(f"Noma'lum chora turi: {kind}")
    with engine.begin() as con:
        con.execute(text(
            "INSERT app.Intervention (StudentKey, SemesterKey, Type, Status, Note, CreatedBy) "
            "VALUES (:s, :sem, :t, :st, :n, :u)"),
            dict(s=int(student_key), sem=int(semester_key), t=kind, st=STATUSES[0],
                 n=(note or "").strip()[:1000] or None, u=user))


def update(engine, intervention_id: int, status: str, outcome: str | None, user: str) -> None:
    _writable()
    if status not in STATUSES or (outcome and outcome not in OUTCOMES):
        raise ValueError("Noto'g'ri holat yoki natija.")
    with engine.begin() as con:
        con.execute(text(
            "UPDATE app.Intervention SET Status = :st, Outcome = :o, UpdatedBy = :u, "
            "UpdatedAt = SYSDATETIME() WHERE InterventionID = :i"),
            dict(st=status, o=outcome or None, u=user, i=int(intervention_id)))


def for_student(engine, student_key: int) -> pd.DataFrame:
    """Every record of one student, newest first."""
    if config.OFFLINE:
        return pd.DataFrame(columns=["InterventionID", "CreatedAt", "Type", "Status", "Outcome", "Note",
                                     "CreatedBy"])
    return pd.read_sql(text(
        "SELECT InterventionID, CreatedAt, Type, Status, Outcome, Note, CreatedBy "
        "FROM app.Intervention WHERE StudentKey = :s ORDER BY CreatedAt DESC, InterventionID DESC"),
        engine, params=dict(s=int(student_key)))


def latest_by_student(engine) -> pd.DataFrame:
    """One row per student that has any record: its newest status and the number of records."""
    if config.OFFLINE:
        return pd.DataFrame(columns=["StudentKey", "Status", "Records"])
    return pd.read_sql(text(
        "SELECT StudentKey, Status, Records FROM ("
        "  SELECT StudentKey, Status, COUNT(*) OVER (PARTITION BY StudentKey) AS Records,"
        "         ROW_NUMBER() OVER (PARTITION BY StudentKey ORDER BY CreatedAt DESC, InterventionID DESC) AS rn"
        "  FROM app.Intervention) x WHERE rn = 1"), engine)


# ----------------------------------------------- surviving a database rebuild
def backup(engine) -> int:
    """Save every record to a file before the database is dropped. Returns the row count."""
    with engine.connect() as con:
        if con.execute(text("SELECT OBJECT_ID('app.Intervention')")).scalar() is None:
            return 0
    rows = pd.read_sql(text(f"SELECT {', '.join(_COLUMNS)} FROM app.Intervention ORDER BY InterventionID"),
                       engine)
    if len(rows):
        BACKUP.parent.mkdir(parents=True, exist_ok=True)
        rows.to_csv(BACKUP, index=False, encoding="utf-8")
    return len(rows)


def restore(engine) -> int:
    """Load the saved records into the rebuilt (empty) table, then set the file aside."""
    if not BACKUP.exists():
        return 0
    rows = pd.read_csv(BACKUP, encoding="utf-8", parse_dates=["CreatedAt", "UpdatedAt"])
    with engine.begin() as con:
        if con.execute(text("SELECT COUNT(*) FROM app.Intervention")).scalar():
            return 0                          # the table already has data: never mix a backup into it
        records = rows.astype(object).where(rows.notna(), None).to_dict("records")
        if records:
            con.execute(text(
                f"INSERT app.Intervention ({', '.join(_COLUMNS)}) "
                f"VALUES ({', '.join(':' + c for c in _COLUMNS)})"), records)
    BACKUP.replace(BACKUP.with_suffix(".restored.csv"))
    return len(rows)
