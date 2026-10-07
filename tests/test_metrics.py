"""Tests for the numbers management sees (05_Analytics/metrics.py, risk levels).

    python -m unittest discover tests

The first classes need no database: they feed small hand-made inputs to the
pure calculations, so a change that shifts a KPI fails here. The last class
checks the live warehouse and is skipped when SQL Server is not reachable.
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import metrics as m  # noqa: E402
import risk_model as rm  # noqa: E402

BEST = {k: best for k, (_, best) in config.HEALTH_SCALES.items()}
WORST = {k: worst for k, (worst, _) in config.HEALTH_SCALES.items()}


class HealthScore(unittest.TestCase):
    def test_weights_sum_to_one_and_have_scales(self):
        self.assertAlmostEqual(sum(config.HEALTH_WEIGHTS.values()), 1.0)
        self.assertEqual(set(config.HEALTH_WEIGHTS), set(config.HEALTH_SCALES))

    def test_best_values_give_100_and_worst_give_0(self):
        self.assertEqual(m.health_score(BEST)[0], 100.0)
        self.assertEqual(m.health_score(WORST)[0], 0.0)

    def test_midpoint_of_every_scale_gives_50(self):
        mid = {k: (WORST[k] + BEST[k]) / 2 for k in BEST}
        score, detail = m.health_score(mid)
        self.assertAlmostEqual(score, 50.0, delta=0.5)
        self.assertTrue((detail.SubScore.round() == 50).all())

    def test_values_outside_the_scale_are_clipped(self):
        beyond = {k: BEST[k] + (BEST[k] - WORST[k]) for k in BEST}       # twice as good as "best"
        below = {k: WORST[k] - (BEST[k] - WORST[k]) for k in BEST}
        self.assertEqual(m.health_score(beyond)[0], 100.0)
        self.assertEqual(m.health_score(below)[0], 0.0)

    def test_lower_is_better_components(self):
        """Overloaded teachers and problem courses: a smaller share scores higher."""
        for key in ("faculty_load", "course_health"):
            worst, best = config.HEALTH_SCALES[key]
            self.assertGreater(worst, best)
            detail = m.health_score({**WORST, key: best})[1].set_index("Key")
            self.assertEqual(detail.loc[key, "SubScore"], 100.0)

    def test_missing_component_is_left_out_and_weights_rescaled(self):
        values = {**BEST, "financial": None}
        score, detail = m.health_score(values)
        self.assertNotIn("financial", set(detail.Key))
        self.assertAlmostEqual(detail.Weight.sum(), 1.0, places=3)
        self.assertAlmostEqual(score, 100.0, delta=0.2)

    def test_one_weak_component_costs_exactly_its_weight(self):
        score, _ = m.health_score({**BEST, "academic": WORST["academic"]})
        self.assertAlmostEqual(score, 100 * (1 - config.HEALTH_WEIGHTS["academic"]), delta=0.2)


class ExamRates(unittest.TestCase):
    def setUp(self):
        # 100 course results, 90 admitted to the final control
        self.row = m.exam_rates(pd.DataFrame([dict(
            N=100, Failed=20, CurrentSum=1500, MidtermSum=2400, FinalSum=3600, Admitted=90,
            MidLow=25, FinLow=18, MidOkFailed=8, N5=10, N4=40, N3=30)])).iloc[0]

    def test_averages_are_a_share_of_each_controls_own_maximum(self):
        mx = config.SCORE_MAX
        self.assertAlmostEqual(self.row.CurrentPct, 15 / mx["current"])
        self.assertAlmostEqual(self.row.MidtermPct, 24 / mx["midterm"])
        self.assertAlmostEqual(self.row.FinalPct, 40 / mx["final"])        # 3600 / 90 admitted

    def test_final_counts_admitted_students_only(self):
        self.assertAlmostEqual(self.row.FinalAdmitted, 40.0)
        self.assertAlmostEqual(self.row.FinalPassRate, 1 - 18 / 90)
        self.assertEqual(self.row.NotAdmitted, 10)
        self.assertAlmostEqual(self.row.NotAdmittedRate, 0.10)

    def test_rates(self):
        self.assertAlmostEqual(self.row.FailureRate, 0.20)
        self.assertAlmostEqual(self.row.MidtermPassRate, 0.75)
        self.assertAlmostEqual(self.row.LostAfterMidterm, 0.08)
        self.assertAlmostEqual(self.row.ExcellentRate, 0.10)
        self.assertAlmostEqual(self.row.ExamGap, self.row.FinalPct - self.row.MidtermPct)

    def test_grades_and_failures_account_for_every_result(self):
        self.assertEqual(self.row.N5 + self.row.N4 + self.row.N3 + self.row.Failed, self.row.N)

    def test_input_frame_is_not_modified(self):
        g = pd.DataFrame([dict(N=1, Failed=0, CurrentSum=1, MidtermSum=1, FinalSum=1, Admitted=1,
                               MidLow=0, FinLow=0, MidOkFailed=0, N5=1, N4=0, N3=0)])
        before = list(g.columns)
        m.exam_rates(g)
        self.assertEqual(list(g.columns), before)


class RiskLevels(unittest.TestCase):
    def test_levels_follow_the_configured_bounds(self):
        levels = list(rm.risk_level(np.array([0.0, 0.10, 0.26, 0.49, 0.51, 0.74, 0.76, 1.0])))
        self.assertEqual(levels, ["Past", "Past", "O'rta", "O'rta", "Yuqori", "Yuqori", "Kritik", "Kritik"])

    def test_every_probability_gets_a_known_level(self):
        levels = set(rm.risk_level(np.linspace(0, 1, 201)))
        self.assertEqual(levels, set(config.RISK_ORDER))

    def test_config_is_consistent(self):
        bounds = [b for b, _ in config.RISK_LEVELS]
        self.assertEqual(bounds, sorted(bounds))
        self.assertGreater(bounds[-1], 1.0)                      # probability 1.0 is still covered
        self.assertEqual([lab for _, lab in config.RISK_LEVELS], config.RISK_ORDER)
        self.assertTrue(set(m.HIGH_RISK) <= set(config.RISK_ORDER))


class GradingScale(unittest.TestCase):
    def test_controls_add_up_to_100(self):
        self.assertEqual(sum(config.SCORE_MAX.values()), 100)

    def test_scale_is_descending_and_starts_at_the_pass_mark(self):
        mins = [lo for lo, _, _ in config.GRADE_SCALE]
        self.assertEqual(mins, sorted(mins, reverse=True))
        self.assertEqual(mins[-1], 0)
        passing = [lo for lo, grade, _ in config.GRADE_SCALE if grade != "2"]
        self.assertEqual(min(passing), config.PASS_MARK)


class RobustZ(unittest.TestCase):
    def test_constant_series_has_no_outliers(self):
        self.assertTrue((m._robust_z(pd.Series([5.0] * 6)) == 0).all())

    def test_one_jump_stands_out(self):
        z = m._robust_z(pd.Series([1.0, 1.1, 0.9, 1.0, 1.05, 0.95, 9.0]))
        self.assertGreater(z.iloc[-1], config.ANOMALY_Z)
        self.assertTrue((z.iloc[:-1].abs() < config.ANOMALY_Z).all())


def _warehouse():
    try:
        engine = config.get_engine()
        return m.load_all(engine)
    except Exception:
        return None


class LiveWarehouse(unittest.TestCase):
    """Sanity of the figures on the loaded warehouse (skipped without SQL Server)."""

    @classmethod
    def setUpClass(cls):
        cls.d = _warehouse()
        if cls.d is None:
            raise unittest.SkipTest("SQL Server ombori mavjud emas")

    def test_headline_kpis_are_in_range(self):
        k = m.kpis(self.d)
        self.assertGreater(k["total_students"], 0)
        self.assertTrue(2.0 <= k["avg_gpa"] <= 5.0)
        for key in ("attendance", "failure_rate", "collection_rate", "high_risk_share"):
            self.assertTrue(0.0 <= k[key] <= 1.0, key)
        self.assertLessEqual(k["high_risk_students"], k["total_students"])

    def test_health_score_matches_its_components(self):
        score, detail = m.university_health(self.d)
        self.assertTrue(0 <= score <= 100)
        self.assertAlmostEqual(score, detail.Points.sum(), delta=0.15)
        self.assertAlmostEqual(detail.Weight.sum(), 1.0, places=2)

    def test_every_active_student_has_exactly_one_risk_level(self):
        risk = self.d["risk"]
        self.assertFalse(risk.StudentKey.duplicated().any())
        self.assertTrue(set(risk.RiskLevel) <= set(config.RISK_ORDER))
        self.assertEqual(list(risk.RiskLevel), list(rm.risk_level(risk.RiskProbability.to_numpy())))

    def test_faculty_ranking_is_complete(self):
        fs = m.faculty_summary(self.d)
        self.assertEqual(len(fs), len(self.d["faculties"]))
        self.assertEqual(sorted(fs.Rank), list(range(1, len(fs) + 1)))
        # Faculty headcounts are "studied in this semester". The overview's "Faol talabalar"
        # (total_students) is a different figure: active today, without those who left since.
        self.assertEqual(int(fs.Students.sum()), m.kpis(self.d)["students_in_semester"])

    def test_exam_results_add_up_across_faculties(self):
        latest = self.d["latest"]
        total = m.exam_by(self.d, latest, "university").iloc[0]
        by_fac = m.exam_by(self.d, latest, "faculty")
        self.assertEqual(int(by_fac.N.sum()), int(total.N))
        self.assertEqual(int(by_fac.Failed.sum()), int(total.Failed))


if __name__ == "__main__":
    unittest.main()
