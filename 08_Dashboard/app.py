"""University Intelligence & AI Decision System - dashboard (replaces Power BI).

A Streamlit web app; the look (deep-space theme, motion) is in ui.py and the
lock screen in auth.py.

    streamlit run 08_Dashboard/app.py        (or double-click start_dashboard.bat)

Every page reads the SQL Server warehouse through 05_Analytics/metrics.py, so
the figures are identical to what the AI agent quotes. When the ETL pipeline
loads new data, the app notices and refreshes on its own.
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402,F401
import metrics as m  # noqa: E402
import auth  # noqa: E402
import ui  # noqa: E402
import views  # noqa: E402
import views_ai  # noqa: E402
from agent_tools import ROLES  # noqa: E402

ASSETS = ui.ASSETS
ui.apply_theme(ui.current_theme())      # light or dark: colours, stylesheet, logo
st.set_page_config(page_title="University Intelligence", page_icon=str(ASSETS / ui.SEAL),
                   layout="wide")
ui.inject_css()
auth.require_login()         # lock screen: nothing below runs until the user signs in
st.logo(str(ASSETS / ui.LOGO), size="large", icon_image=str(ASSETS / ui.SEAL))

try:
    data, version = ui.get_data()
except Exception as exc:  # database missing or SQL Server not reachable
    st.error("Ma'lumotlar omboriga ulanib bo'lmadi. Avval konveyerni ishga tushiring: "
             "`python run_pipeline.py --rebuild`")
    st.exception(exc)
    st.stop()


def page(fn):
    def run():
        fn(data)
    run.__name__ = fn.__name__
    return run


def more_page():
    views.more(data, views_ai.data_quality)


# Six everyday pages, one question each, plus a compact page for the rest.
nav = st.navigation([
    st.Page(page(views.overview), title="Umumiy ko'rinish", icon=":material/dashboard:",
            url_path="overview", default=True),
    st.Page(page(views.faculty), title="Fakultetlar", icon=":material/account_balance:",
            url_path="faculty"),
    st.Page(page(views.exams), title="Imtihon natijalari", icon=":material/fact_check:",
            url_path="exams"),
    st.Page(page(views.risk), title="Xavf ostidagi talabalar", icon=":material/warning:",
            url_path="risk"),
    st.Page(page(views_ai.scenarios), title="«Agar...» ssenariylari", icon=":material/tune:",
            url_path="scenarios"),
    st.Page(page(views_ai.agent), title="AI yordamchi", icon=":material/smart_toy:", url_path="agent"),
    st.Page(more_page, title="Boshqa", icon=":material/more_horiz:", url_path="more"),
])

st.session_state.semester_label = m.semester_label(data, data["latest"])

# The role comes from the account that signed in (auth.py); nobody can pick another one.
role = st.session_state.role
if role == "dekan":
    own = data["faculties"].loc[
        data["faculties"].FacultyName == st.session_state.own_faculty_name, "FacultyKey"]
    if own.empty:        # the account names a faculty the warehouse does not have: open nothing
        st.error(f"Bu hisobga biriktirilgan fakultet topilmadi: «{st.session_state.own_faculty_name}». "
                 "Hisobni `python 08_Dashboard/set_password.py` orqali tuzating.")
        with st.sidebar:
            auth.sidebar_user(ROLES[role]["label"])
        st.stop()
    st.session_state.own_faculty = int(own.iloc[0])

with st.sidebar:
    st.divider()
    st.caption(f"Manba: SQL Server · {config.SQL_DATABASE}  \nYangilangan: {version.split('-', 1)[-1]}")
    auth.sidebar_user(ROLES[role]["label"])
    ui.watch_for_new_data()

nav.run()
