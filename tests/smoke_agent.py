"""Smoke test of the agent tools, role restrictions, SQL guard and scenarios.

Run:  python tests/smoke_agent.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402,F401
import scenarios as sc  # noqa: E402
from agent import offline_answer  # noqa: E402
from agent_tools import Toolbox  # noqa: E402

tb = Toolbox()
checks = []


def check(name, ok, detail=""):
    ok = bool(ok)
    checks.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


def call(box, name, **args):
    out, err = box.run(name, args)
    return json.loads(out), err


r, err = call(tb, "university_overview")
check("university_overview", not err and 0 < r["health_score"] <= 100, f"health={r['health_score']}")
r, err = call(tb, "faculty_analytics", faculty="Iqtisod")
check("faculty_analytics with trend", not err and len(r["trend"]) >= 4 and r["hardest_courses"])
r, err = call(tb, "student_analytics", action="top_risk", limit=3)
check("student top_risk", not err and len(r["students"]) == 3, r["students"][0]["MainFactors"])
sid = r["students"][0]["StudentKey"]
r, err = call(tb, "student_analytics", action="profile", student_id=sid)
check("student profile", not err and r["semesters"] and "risk" in r)
r, err = call(tb, "ml_prediction", student_id=sid)
check("ml_prediction student", not err and 0 < r["RiskProbability"] < 1, str(r["factor_shares"]))
r, err = call(tb, "ml_prediction")
check("ml_prediction overall", not err and r["model"][0]["Recall"] > 0.5, str(r["risk_levels"]))
r, err = call(tb, "course_analytics")
check("course_analytics top", not err and len(r["courses"]) > 0, r["courses"][0]["CourseName"])
r, err = call(tb, "course_analytics", course="Ma'lumotlar tahlili")
print("   course history:", [(h["SemesterLabel"], h["Enrollment"], h["FailureRate"], h["MidtermPct"],
                              h["FinalPct"]) for h in r["history"]])
for by in ("faculty", "group", "course", "teacher", "semester"):
    r, err = call(tb, "exam_analytics", by=by)
    check(f"exam_analytics by {by}", not err and len(r["rows"]) > 0
          and 0 < r["overview"]["MidtermPct"] < 1 and 0 < r["overview"]["FinalPct"] < 1)
r, err = call(tb, "scenario_simulation", scenario="custom", target="high_risk", attendance=0.05)
check("custom scenario", not err and r["students_affected"] > 0)

r, err = call(tb, "sql_query", query="SELECT TOP 3 FacultyName FROM dw.DimFaculty ORDER BY 1")
check("sql select allowed", not err and r["row_count"] == 3)
for bad in ["DELETE FROM dw.DimFaculty", "SELECT 1; DROP TABLE dw.DimFaculty",
            "SELECT * INTO dw.X FROM dw.DimFaculty", "EXEC dw.usp_LoadFacts 1",
            "SELECT 1 -- hidden", "UPDATE dw.DimFaculty SET Dean = 'x'"]:
    r, err = call(tb, "sql_query", query=bad)
    check(f"sql blocked: {bad[:32]}", err)

teacher = Toolbox(role="oqituvchi", data=tb.data)
r, err = call(teacher, "student_analytics", action="top_risk")
check("teacher role: no student-level data", err and r["error"] == "RUXSAT YO'Q")
r, err = call(teacher, "sql_query", query="SELECT 1")
check("teacher role: no SQL", err)
r, err = call(teacher, "faculty_analytics")
check("teacher role: aggregates allowed", not err)
dean = Toolbox(role="dekan", own_faculty="Huquq", data=tb.data)
r, err = call(dean, "faculty_analytics", faculty="Iqtisodiyot")
check("dean role: other faculty blocked", err)
r, err = call(dean, "student_analytics", action="top_risk", limit=5)
check("dean role: own faculty only", not err and {s["FacultyName"] for s in r["students"]} == {"Huquq"})

pop, bundle = tb._simulation()
for key in sc.SCENARIOS:
    res = sc.run_scenario(pop, bundle, key)
    print(f"\n=== {res['title']} ({res['affected']:,}/{res['students']:,} talaba)")
    print(sc.format_table(res).to_string(index=False))
    check(f"scenario {key}", len(res["table"]) == 6)

print("\n" + offline_answer(tb, "risk_faculty")["text"])
print(f"\n{sum(checks)}/{len(checks)} checks passed")
sys.exit(0 if all(checks) else 1)
