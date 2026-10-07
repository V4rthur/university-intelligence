"""Tests for the dashboard's own logic: accounts and roles, number formats,
and the text filter in front of the AI agent's SQL tool. No database needed.

    python -m unittest discover tests
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "08_Dashboard"))
import config  # noqa: E402
import agent_tools as at  # noqa: E402
import auth  # noqa: E402
import ui  # noqa: E402


class Accounts(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self._real, auth.SECRETS = auth.SECRETS, Path(self._dir.name) / "secrets.toml"
        self._offline, config.OFFLINE = config.OFFLINE, False

    def tearDown(self):
        auth.SECRETS, config.OFFLINE = self._real, self._offline
        self._dir.cleanup()

    def test_no_file_means_no_accounts_and_no_login(self):
        self.assertEqual(auth.accounts(), {})
        self.assertIsNone(auth.check("admin", "anything"))

    def test_right_password_returns_the_account_with_its_role(self):
        auth.write_account("Rektor", "correct horse", "rahbariyat")
        acc = auth.check("rektor ", "correct horse")              # login: case and spaces ignored
        self.assertEqual((acc["username"], acc["role"]), ("Rektor", "rahbariyat"))

    def test_wrong_password_or_unknown_login_is_refused(self):
        auth.write_account("rektor", "correct horse", "rahbariyat")
        self.assertIsNone(auth.check("rektor", "Correct horse"))
        self.assertIsNone(auth.check("rektor", ""))
        self.assertIsNone(auth.check("nobody", "correct horse"))

    def test_password_is_not_stored(self):
        auth.write_account("rektor", "correct horse", "rahbariyat")
        self.assertNotIn("correct horse", auth.SECRETS.read_text(encoding="utf-8"))

    def test_dean_needs_a_faculty_and_keeps_it(self):
        with self.assertRaises(ValueError):
            auth.write_account("dekan", "password1", "dekan")
        auth.write_account("dekan", "password1", "dekan", "Iqtisodiyot")
        self.assertEqual(auth.check("dekan", "password1")["faculty"], "Iqtisodiyot")

    def test_unknown_role_is_rejected(self):
        with self.assertRaises(ValueError):
            auth.write_account("x", "password1", "admin")

    def test_accounts_are_independent(self):
        auth.write_account("a", "password-a", "rahbariyat")
        auth.write_account("b", "password-b", "oqituvchi")
        auth.write_account("a", "password-a2", "rahbariyat")       # change one password
        self.assertIsNone(auth.check("a", "password-a"))
        self.assertEqual(auth.check("a", "password-a2")["role"], "rahbariyat")
        self.assertEqual(auth.check("b", "password-b")["role"], "oqituvchi")
        self.assertIsNone(auth.check("a", "password-b"))

    def test_delete(self):
        auth.write_account("a", "password-a", "rahbariyat")
        self.assertTrue(auth.delete_account("A"))
        self.assertFalse(auth.delete_account("a"))
        self.assertIsNone(auth.check("a", "password-a"))

    def test_first_version_single_account_still_works_and_is_migrated(self):
        salt = "ab" * 16
        auth.SECRETS.write_text(
            f'[auth]\nusername = "admin"\nsalt = "{salt}"\n'
            f'password_hash = "{auth.hash_password("old password", salt)}"\n', encoding="utf-8")
        self.assertEqual(auth.check("admin", "old password")["role"], "rahbariyat")
        auth.write_account("dekan", "password1", "dekan", "Huquq")
        self.assertNotIn("[auth]", auth.SECRETS.read_text(encoding="utf-8"))
        self.assertEqual(auth.check("admin", "old password")["role"], "rahbariyat")

    def test_an_account_with_a_broken_role_is_ignored(self):
        auth.write_account("a", "password-a", "oqituvchi")
        text = auth.SECRETS.read_text(encoding="utf-8").replace('"oqituvchi"', '"superuser"')
        auth.SECRETS.write_text(text, encoding="utf-8")
        self.assertIsNone(auth.check("a", "password-a"))


class SessionTokens(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self._real, auth.SECRETS = auth.SECRETS, Path(self._dir.name) / "secrets.toml"
        self._offline, config.OFFLINE = config.OFFLINE, False
        auth.write_account("rektor", "correct horse", "rahbariyat")
        self.acc = auth.check("rektor", "correct horse")

    def tearDown(self):
        auth.SECRETS, config.OFFLINE = self._real, self._offline
        self._dir.cleanup()

    def test_a_fresh_token_brings_the_account_back(self):
        self.assertEqual(auth.account_from_token(auth.session_token(self.acc))["username"], "rektor")

    def test_expired_or_garbled_tokens_are_refused(self):
        self.assertIsNone(auth.account_from_token(auth.session_token(self.acc, hours=-1)))
        for bad in ["", "abc", "a.b.c", "..", auth.session_token(self.acc) + "0"]:
            self.assertIsNone(auth.account_from_token(bad), bad)

    def test_a_token_cannot_be_edited(self):
        user, expires, signature = auth.session_token(self.acc).split(".")
        self.assertIsNone(auth.account_from_token(f"{user}.{int(expires) + 99999}.{signature}"))
        auth.write_account("dekan", "password1", "dekan", "Huquq")
        other = auth.session_token(auth.check("dekan", "password1")).split(".")[0]
        self.assertIsNone(auth.account_from_token(f"{other}.{expires}.{signature}"))

    def test_changing_the_password_or_deleting_the_account_ends_the_session(self):
        token = auth.session_token(self.acc)
        auth.write_account("rektor", "another password", "rahbariyat")
        self.assertIsNone(auth.account_from_token(token))
        token = auth.session_token(auth.check("rektor", "another password"))
        auth.delete_account("rektor")
        self.assertIsNone(auth.account_from_token(token))

    def test_the_role_comes_from_the_account_not_the_token(self):
        token = auth.session_token(self.acc)
        doc = auth._read()
        doc["users"]["rektor"]["role"] = "oqituvchi"          # demoted, same password
        auth._write(doc)
        self.assertEqual(auth.account_from_token(token)["role"], "oqituvchi")

    def test_a_token_signed_with_another_key_is_refused(self):
        token = auth.session_token(self.acc)
        doc = auth._read()
        doc["session"]["key"] = "11" * 32
        auth._write(doc)
        self.assertIsNone(auth.account_from_token(token))


class Themes(unittest.TestCase):
    def test_both_themes_define_the_same_constants_and_a_full_stylesheet(self):
        dark, light = ui._PALETTES["dark"], ui._PALETTES["light"]
        self.assertEqual(set(dark), set(light))
        for palette in (dark, light):
            self.assertNotIn("$", palette["CSS"])                  # no unfilled placeholder
            self.assertEqual(set(palette["RISK_COLORS"]), set(config.RISK_ORDER))
            self.assertEqual(set(palette["RISK_TAG"]), set(config.RISK_ORDER))

    def test_the_theme_belongs_to_the_run_not_to_the_module(self):
        import threading
        seen = {}

        def run(name):
            ui.apply_theme(name)
            seen[name] = (ui.THEME, ui.INK, ui.P.BG)

        threads = [threading.Thread(target=run, args=(name,)) for name in ("light", "dark")]
        [t.start() for t in threads]
        [t.join() for t in threads]
        for name in ("light", "dark"):
            self.assertEqual(seen[name], (name, ui.THEMES[name]["INK"], ui.THEMES[name]["BG"]))


class Formats(unittest.TestCase):
    def test_percent(self):
        self.assertEqual(ui.pct(0.9174), "91.7%")
        self.assertEqual(ui.pct(0.5, 0), "50%")
        self.assertEqual(ui.pct(None), "-")
        self.assertEqual(ui.pct(float("nan")), "-")

    def test_number_uses_a_space_for_thousands(self):
        self.assertEqual(ui.num(10681), "10 681")
        self.assertEqual(ui.num(999), "999")
        self.assertEqual(ui.num(None), "-")

    def test_money_is_in_milliard(self):
        self.assertEqual(ui.money(91_800_000_000), "91.8 mlrd")
        self.assertEqual(ui.money(None), "-")

    def test_percentage_point_change(self):
        self.assertEqual(ui.pp(0.917, 0.918), "-0.1 f.p.")
        self.assertEqual(ui.pp(0.50, 0.45), "+5.0 f.p.")
        self.assertIsNone(ui.pp(0.5, None))

    def test_side_by_side_charts_share_the_tallest_height(self):
        self.assertEqual(ui.bar_h_height([1] * 6, [1] * 5), ui.bar_h_height([1] * 6))
        self.assertGreater(ui.bar_h_height([1] * 7), ui.bar_h_height([1] * 5))


class _Card:
    """Stands in for a Streamlit column: keeps the HTML a KPI card renders."""
    def markdown(self, html, **_):
        self.html = html


class KpiChange(unittest.TestCase):
    def colour(self, delta, inverse=False):
        card = _Card()
        ui.kpi(card, "Label", "1", delta, inverse=inverse)
        return ui.RED if f"color:{ui.RED}" in card.html else ui.CYAN if f"color:{ui.CYAN}" in card.html else None

    def test_a_drop_is_bad_and_a_rise_is_good(self):
        self.assertEqual(self.colour("-0.1 f.p."), ui.RED)
        self.assertEqual(self.colour("+0.1 f.p."), ui.CYAN)

    def test_for_failure_rates_it_is_the_other_way_round(self):
        self.assertEqual(self.colour("+0.1 f.p.", inverse=True), ui.RED)
        self.assertEqual(self.colour("-0.1 f.p.", inverse=True), ui.CYAN)

    def test_no_change_is_neither(self):
        self.assertIsNone(self.colour("+0.00"))
        self.assertIsNone(self.colour("-0.0 f.p.", inverse=True))


class _NoDatabase(at.Toolbox):
    """A toolbox whose engine explodes: the filter must refuse before touching it."""
    def __init__(self, role="rahbariyat"):
        self.engine, self.role, self.perm = None, role, at.ROLES[role]


class SqlToolFilter(unittest.TestCase):
    def setUp(self):
        self._offline, config.OFFLINE = config.OFFLINE, False

    def tearDown(self):
        config.OFFLINE = self._offline

    def refuse(self, query):
        with self.assertRaises(ValueError, msg=query):
            _NoDatabase().sql_query(query)

    def test_only_a_single_select_gets_past_the_filter(self):
        for query in ["DELETE FROM dw.DimStudent", "UPDATE dw.DimStudent SET FullName = 'x'",
                      "SELECT 1; DROP TABLE dw.DimStudent", "SELECT * INTO dw.Copy FROM dw.DimFaculty",
                      "EXEC sp_who", "SELECT 1 -- comment", "SELECT 1 /* comment */",
                      "WITH x AS (SELECT 1 AS a) DELETE FROM x", "select 1 where 1 = 1 revert",
                      "TRUNCATE TABLE etl.RunLog", ""]:
            self.refuse(query)

    def test_a_select_reaches_the_database_step(self):
        # engine is None, so getting as far as the connection proves the filter let it through
        for query in ["SELECT TOP 5 * FROM dw.DimFaculty", "  with x as (select 1 as a) select * from x ;"]:
            with self.assertRaises(AttributeError, msg=query):
                _NoDatabase().sql_query(query)

    def test_roles_without_sql_rights_are_refused_first(self):
        for role in ("dekan", "oqituvchi"):
            with self.assertRaises(PermissionError):
                _NoDatabase(role).sql_query("SELECT 1")

    def test_role_table_matches_the_dashboard_accounts(self):
        self.assertEqual(set(at.ROLES), set(auth.ROLES))


@unittest.skipUnless((config.OFFLINE_DIR / "meta.json").exists(), "offline nusxa eksport qilinmagan")
class OfflineCopy(unittest.TestCase):
    """The hosted demo: reads the saved export, never the database, and writes nothing."""

    def setUp(self):
        self._offline, config.OFFLINE = config.OFFLINE, True

    def tearDown(self):
        config.OFFLINE = self._offline

    def test_everything_loads_without_an_engine(self):
        import metrics as m
        d = m.load_all(None)
        self.assertGreater(m.kpis(d)["total_students"], 0)
        self.assertTrue(0 <= m.university_health(d)[0] <= 100)
        student = int(d["risk"].StudentKey.iloc[0])
        profile = m.student_profile(d, None, student)
        self.assertGreater(len(profile["grades"]), 0)
        self.assertNotIn("StudentKey", profile["grades"].columns)
        self.assertIsNotNone(m.data_quality(None)["score"])
        self.assertTrue(m.data_version(None))

    def test_a_loaded_table_can_be_changed_without_touching_the_copy(self):
        import offline
        first = offline.table("all_faculties")
        first["FacultyName"] = "x"
        self.assertNotIn("x", set(offline.table("all_faculties").FacultyName))

    def test_nothing_can_be_written_or_queried(self):
        import interventions as iv
        with self.assertRaises(PermissionError):
            iv.add(None, 1, 1, iv.TYPES[0], "", "tester")
        with self.assertRaises(PermissionError):
            iv.update(None, 1, iv.STATUSES[0], None, "tester")
        self.assertEqual(len(iv.for_student(None, 1)), 0)
        self.assertEqual(len(iv.latest_by_student(None)), 0)
        with self.assertRaises(PermissionError):
            _NoDatabase().sql_query("SELECT 1")


if __name__ == "__main__":
    unittest.main()
