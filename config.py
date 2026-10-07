"""Central configuration for the University Intelligence & AI Decision System.

Every module (data generator, ETL, analytics, ML, simulation, AI agent,
dashboard) imports this file, so paths, the database connection and all
business thresholds live in exactly one place.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

DATA_DIR = ROOT / "01_Data"
RAW_DIR = DATA_DIR / "raw"
STATE_DIR = DATA_DIR / "_state"
ETL_DIR = ROOT / "02_ETL"
SQL_DIR = ROOT / "03_SQL"
DW_DIR = ROOT / "04_Data_Warehouse"
ANALYTICS_DIR = ROOT / "05_Analytics"
ML_DIR = ROOT / "06_ML"
MODEL_DIR = ML_DIR / "models"
AGENT_DIR = ROOT / "07_AI_Agent"
DASHBOARD_DIR = ROOT / "08_Dashboard"
SIM_DIR = ROOT / "09_Simulation"
DOCS_DIR = ROOT / "10_Documentation"
REPORTS_DIR = DOCS_DIR / "reports"
PRESENTATION_DIR = ROOT / "11_Presentation"

# Folder names start with digits, so they cannot be Python packages.
# Adding them to sys.path lets any module do e.g. `import metrics`.
for _p in (ROOT, DATA_DIR, ETL_DIR, ANALYTICS_DIR, ML_DIR, AGENT_DIR, SIM_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# ---------------------------------------------------------------- database
SQL_SERVER = os.environ.get("UIS_SQL_SERVER", "localhost")
SQL_DATABASE = os.environ.get("UIS_SQL_DATABASE", "UniversityIntelligence")
SQL_DRIVER = os.environ.get("UIS_SQL_DRIVER", "ODBC Driver 17 for SQL Server")


# Offline copy. Where SQL Server cannot be reached (the hosted demo runs on Linux), the
# dashboard reads a saved export of the warehouse instead: see 05_Analytics/offline.py.
# UIS_OFFLINE=1 forces it (to try it on this machine), UIS_OFFLINE=0 forbids it.
_offline = os.environ.get("UIS_OFFLINE", "auto")
OFFLINE = _offline == "1" or (_offline == "auto" and sys.platform != "win32")
OFFLINE_DIR = DATA_DIR / "offline"


def connection_url(database: str | None = None) -> str:
    db = database or SQL_DATABASE
    return (
        f"mssql+pyodbc://@{SQL_SERVER}/{db}"
        f"?driver={SQL_DRIVER.replace(' ', '+')}&trusted_connection=yes"
    )


def get_engine(database: str | None = None):
    from sqlalchemy import create_engine

    return create_engine(connection_url(database), fast_executemany=True, pool_pre_ping=True)


# ------------------------------------------------------------ grading scale
# The credit-module system used by universities in Uzbekistan: every course is
# graded out of 100 points collected from three controls, and the total is
# converted to the 5-point grade. The split between the controls differs from
# university to university - change SCORE_MAX to match yours.
SCORE_MAX = {"current": 20, "midterm": 30, "final": 50}   # joriy / oraliq / yakuniy nazorat
PASS_MARK = 60             # total below this is "qoniqarsiz" (academic debt)
CONTROL_PASS_SHARE = 0.60  # a single control counts as passed from 60% of its maximum
GRADE_SCALE = [  # (minimum total score, grade, grade points)
    (90, "5", 5.0),   # a'lo
    (70, "4", 4.0),   # yaxshi
    (60, "3", 3.0),   # qoniqarli
    (0, "2", 2.0),    # qoniqarsiz
]
GRADE_NAMES = {"5": "5 (a'lo)", "4": "4 (yaxshi)", "3": "3 (qoniqarli)", "2": "2 (qoniqarsiz)"}
# A student whose unexcused absences exceed this share of a course's classes
# is not admitted to the final control of that course.
MAX_UNEXCUSED_ABSENCE = 0.25

# ---------------------------------------------------------- risk definition
# A student is "at risk" in a semester when any of these holds. The ML model
# predicts this outcome for the NEXT semester (or dropping out before it).
AT_RISK_GPA = 3.0   # semester GPA on the 5-point scale (a failed course counts as 2)
AT_RISK_FAILED = 2

RISK_LEVELS = [  # (upper probability bound, label)
    (0.25, "Past"),
    (0.50, "O'rta"),
    (0.75, "Yuqori"),
    (1.01, "Kritik"),
]
RISK_ORDER = ["Past", "O'rta", "Yuqori", "Kritik"]
# Minimum recall the chosen model must reach on at-risk students: missing a
# struggling student (false negative) costs more than a needless check-in.
TARGET_RECALL = 0.80

# --------------------------------------------------------- alert thresholds
ALERTS = {
    "high_risk_share_critical": 0.08,   # share of active students Yuqori/Kritik
    "attendance_drop_warning": 0.02,    # drop vs the same semester last year (abs.)
    "course_failure_attention": 0.25,   # course failure rate
    "gpa_improvement_positive": 0.03,   # relative GPA change vs the same semester last year
    "collection_rate_warning": 0.85,
    "min_course_enrollment": 30,        # ignore tiny courses in alerts
}
ANOMALY_Z = 3.0  # robust z-score above which a change is flagged

# ---------------------------------------------------- university health score
# Each component is scaled to 0-100 between (worst, best) and then weighted.
HEALTH_WEIGHTS = {
    "academic": 0.25,
    "engagement": 0.10,
    "attendance": 0.15,
    "retention": 0.15,
    "faculty_load": 0.10,
    "financial": 0.15,
    "course_health": 0.10,
}
HEALTH_SCALES = {
    "academic": (3.0, 4.5),        # average GPA (5-point scale)
    "engagement": (0.60, 0.98),    # assignment submission rate
    "attendance": (0.60, 0.95),    # attendance rate
    "retention": (0.80, 0.99),     # semester-to-semester retention
    "faculty_load": (0.40, 0.0),   # share of teachers that are overloaded
    "financial": (0.60, 1.0),      # tuition collection rate
    "course_health": (0.30, 0.0),  # share of courses with failure rate > 30%
}
TEACHER_OVERLOAD_STUDENTS = 700  # students per semester

# ------------------------------------------------------------------ AI agent
AGENT_MODEL = os.environ.get("UIS_AGENT_MODEL", "claude-opus-5-5")
SQL_TOOL_MAX_ROWS = 200
