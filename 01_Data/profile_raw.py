"""Quick profile of the generated raw files - used to sanity-check PHASE 2."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

raw = config.RAW_DIR
g = pd.concat(pd.read_csv(f) for f in raw.glob("grades_*.csv")).drop_duplicates("GradeID")
e = pd.concat(pd.read_csv(f) for f in raw.glob("enrollments_*.csv")).drop_duplicates("EnrollmentID")
p = pd.concat(pd.read_csv(f) for f in raw.glob("payments_*.csv")).drop_duplicates("PaymentID")
s = pd.read_csv(raw / "students.csv").drop_duplicates("StudentID")
c = pd.read_csv(raw / "courses.csv")

g = g.merge(e[["StudentID", "CourseID", "TeacherID", "Semester", "AcademicYear"]],
            on=["StudentID", "CourseID"]).merge(s[["StudentID", "FacultyID"]], on="StudentID")
g["fail"] = g.FinalGrade.astype(str) == "2"
g["total"] = g.CurrentScore + pd.to_numeric(g.MidtermScore, errors="coerce") + g.FinalScore
print(f"avg GPA {g.GPA.mean():.2f} | avg total {g.total.mean():.1f} | attendance "
      f"{g.AttendanceScore.mean():.1f}% | failure rate {g.fail.mean():.1%} | "
      f"not admitted to final {(g.ExamAdmitted != 'Ha').mean():.1%}")
print(f"current {g.CurrentScore.mean():.1f}/20 | midterm "
      f"{pd.to_numeric(g.MidtermScore, errors='coerce').mean():.1f}/30 | final "
      f"{g.FinalScore[g.ExamAdmitted == 'Ha'].clip(0, 50).mean():.1f}/50 (admitted only)")
print("\nGrade distribution:", g.FinalGrade.value_counts(normalize=True).round(3).to_dict())
print("\nBy faculty and academic year (GPA / attendance / failure):")
print(g.groupby(["FacultyID", "AcademicYear"]).agg(
    gpa=("GPA", "mean"), att=("AttendanceScore", "mean"), fail=("fail", "mean")
).round(3).unstack(0).to_string())
cf = g.groupby("CourseID").agg(n=("fail", "size"), fail=("fail", "mean")).join(
    c.set_index("CourseID").CourseName).sort_values("fail", ascending=False)
print("\nTop problem courses:\n", cf.head(8).round(3).to_string())
print("\nTeacher load per semester (students):")
print(e.groupby(["AcademicYear", "Semester", "TeacherID"]).size().describe().round(0).to_string())
pa = pd.to_numeric(p.PaidAmount.astype(str).str.replace(" ", ""), errors="coerce")
print(f"\ncollection rate {pa.sum() / p.TuitionAmount.sum():.1%} | "
      f"students with debt {(p.RemainingDebt > 0).mean():.1%}")
print("\nStatus by cohort:\n", pd.crosstab(s.EnrollmentYear, s.Status).to_string())
