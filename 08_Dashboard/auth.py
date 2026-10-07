"""Lock screen and accounts: the dashboard opens only after a login and password.

Every account has a role, and the role decides what its owner may see:

    rahbariyat  university management: everything, including named students
    dekan       one faculty only (the account names it); named students of it
    oqituvchi   aggregated indicators only: no named students

Accounts live in `.streamlit/secrets.toml` ([users.<login>] sections). Passwords
are never stored: only a salted PBKDF2-SHA256 hash. Create, change or list
accounts with

    python 08_Dashboard/set_password.py
"""
import hashlib
import hmac
import json
import secrets
import time
import tomllib
from string import Template

import streamlit as st

import config
import ui

SECRETS = config.ROOT / ".streamlit" / "secrets.toml"
ITERATIONS = 240_000
MAX_ATTEMPTS, LOCK_SECONDS = 5, 30
ROLES = ("rahbariyat", "dekan", "oqituvchi")     # the keys of agent_tools.ROLES
_DUMMY_SALT = "00" * 16                           # hashed against when the login does not exist


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), ITERATIONS).hex()


# ----------------------------------------------------------------- storage
def _read() -> dict:
    try:
        return tomllib.loads(SECRETS.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _write(doc: dict):
    """Write the secrets file: flat [section] tables and [users."login"] tables of strings."""
    out = ["# Dashboard accounts. Manage them with: python 08_Dashboard/set_password.py", ""]
    for section, table in doc.items():
        if section == "users":
            continue
        out += [f"[{section}]", *(f"{k} = {json.dumps(v, ensure_ascii=False)}" for k, v in table.items()), ""]
    for login, acc in doc.get("users", {}).items():
        out += [f"[users.{json.dumps(login, ensure_ascii=False)}]",
                *(f"{k} = {json.dumps(v, ensure_ascii=False)}" for k, v in acc.items()), ""]
    SECRETS.parent.mkdir(exist_ok=True)
    SECRETS.write_text("\n".join(out), encoding="utf-8")


def accounts() -> dict:
    """{login in lower case: account}. An account is a dict with username, role,
    faculty (dekan only), salt and password_hash."""
    doc, found = _read(), {}
    legacy = doc.get("auth")                 # the first version had one account without a role
    if legacy and {"username", "salt", "password_hash"} <= legacy.keys():
        found[legacy["username"].lower()] = {**legacy, "role": "rahbariyat"}
    for login, acc in doc.get("users", {}).items():
        if {"role", "salt", "password_hash"} <= acc.keys() and acc["role"] in ROLES:
            found[login.lower()] = {**acc, "username": login}
    return found


def write_account(username: str, password: str, role: str = "rahbariyat", faculty: str | None = None):
    """Create an account or replace the one with the same login."""
    if role not in ROLES:
        raise ValueError(f"Noma'lum rol: {role}")
    if role == "dekan" and not faculty:
        raise ValueError("Dekan hisobi uchun fakultet ko'rsatilishi kerak.")
    doc = _read()
    users = {a["username"]: {k: v for k, v in a.items() if k != "username"}
             for a in accounts().values()}                    # also migrates the legacy account
    doc.pop("auth", None)
    users = {u: a for u, a in users.items() if u.lower() != username.lower()}
    salt = secrets.token_hex(16)
    users[username] = {"role": role, **({"faculty": faculty} if role == "dekan" else {}),
                       "salt": salt, "password_hash": hash_password(password, salt)}
    doc["users"] = users
    _write(doc)


def delete_account(username: str) -> bool:
    doc = _read()
    users = {a["username"]: {k: v for k, v in a.items() if k != "username"} for a in accounts().values()}
    kept = {u: a for u, a in users.items() if u.lower() != username.lower()}
    doc.pop("auth", None)
    doc["users"] = kept
    _write(doc)
    return len(kept) < len(users)


def check(username: str, password: str) -> dict | None:
    """The account if the login and password match, otherwise None."""
    acc = accounts().get(username.strip().lower())
    # the hash is always computed, so timing does not reveal whether the login exists
    digest = hash_password(password, acc["salt"] if acc else _DUMMY_SALT)
    return acc if acc and hmac.compare_digest(digest, acc["password_hash"]) else None


def _sign_in(acc: dict):
    st.session_state.auth_user = acc["username"]
    st.session_state.role = acc["role"]
    st.session_state.own_faculty_name = acc.get("faculty") if acc["role"] == "dekan" else None


# What differs between the two themes on the lock screen.
LOCK_THEME = {
    "dark": dict(
        ring="rgba(120, 170, 255, 0.30)", ring2="rgba(120, 170, 255, 0.16)",
        halo="radial-gradient(circle, rgba(79, 140, 255, 0.30), transparent 68%)",
        seal_glow="drop-shadow(0 0 22px rgba(120, 170, 255, 0.8))",
        planet="radial-gradient(circle at 50% 0%, #4a94ff 0%, #1a4fbd 4%, #0c2a73 11%, #081640 22%, #060b1e 40%)",
        planet_glow="0 0 120px 12px rgba(70, 140, 255, 0.5), inset 0 16px 60px rgba(160, 210, 255, 0.55)"),
    "light": dict(
        ring="rgba(47, 111, 237, 0.38)", ring2="rgba(47, 111, 237, 0.20)",
        halo="radial-gradient(circle, rgba(255, 255, 255, 0.95), rgba(255, 255, 255, 0) 68%)",
        seal_glow="drop-shadow(0 8px 22px rgba(47, 111, 237, 0.30))",
        planet="radial-gradient(circle at 50% 0%, #3f86ff 0%, #6aa6ff 4%, #a5c6ff 11%, #cfdffb 22%, #eef2fb 40%)",
        planet_glow="0 0 120px 12px rgba(70, 140, 255, 0.30), inset 0 16px 60px rgba(255, 255, 255, 0.85)"),
}

# The intro: the seal fades in at the centre of the page, holds for two
# seconds, then shrinks a little and glides to the right half while the title
# and the login form rise on the left. It plays once per visit; later reruns
# (a wrong password, a theme change) show the settled layout straight away.
INTRO_SECONDS = 3.6
LOCK_CSS = Template("""
<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
[data-testid="stExpandSidebarButton"], [data-testid="stHeader"] { display: none !important; }
/* the login column is centred on the same horizontal line as the seal and its caption */
.block-container { max-width: 420px !important; margin-left: max(5vw, calc(27vw - 210px)) !important;
  margin-right: auto !important; padding: 5vh 0 !important; min-height: 100vh; box-sizing: border-box;
  display: flex; flex-direction: column; justify-content: center; position: relative; z-index: 2; }
.block-container > div { flex: 0 0 auto; }

.lk-stage { --s: min(44vh, 340px); position: fixed; top: 46vh; left: 50%; width: var(--s);
  height: var(--s); z-index: 1; pointer-events: none;
  transform: translate(calc(-50% + 23vw), -50%) scale(0.8); animation: $stage_anim; }
@keyframes lk-intro {
  0%   { opacity: 0; transform: translate(-50%, -50%) scale(0.82); filter: blur(12px); }
  17%  { opacity: 1; transform: translate(-50%, -50%) scale(1); filter: none; }
  72%  { opacity: 1; transform: translate(-50%, -50%) scale(1); filter: none;
         animation-timing-function: cubic-bezier(0.65, 0, 0.2, 1); }
  100% { opacity: 1; transform: translate(calc(-50% + 23vw), -50%) scale(0.8); filter: none; }
}
.lk-stage .halo { position: absolute; inset: -34%; border-radius: 50%; background: $halo;
  animation: ui-breathe 4s ease-in-out infinite alternate; }
.lk-stage img { position: absolute; inset: 9%; width: 82%; height: 82%; filter: $seal_glow;
  animation: ui-float 5s ease-in-out infinite alternate; }
.lk-stage .ring { position: absolute; inset: 0; border-radius: 50%; border: 1px solid $ring;
  animation: ui-spin 26s linear infinite; }
.lk-stage .ring::after { content: ""; position: absolute; top: -5px; left: 50%; width: 9px; height: 9px;
  margin-left: -5px; border-radius: 50%; background: $cyan; box-shadow: 0 0 16px $cyan; }
.lk-stage .ring.two { inset: -9%; border-style: dashed; border-color: $ring2;
  animation-duration: 44s; animation-direction: reverse; }
.lk-stage .ring.two::after { background: $amber; box-shadow: 0 0 14px $amber; width: 6px; height: 6px; }
.lk-stage .cap { position: absolute; top: 116%; left: -40%; width: 180%; text-align: center;
  animation: ui-rise 0.9s $delay_cap ease both; }
/* tracked capitals carry a trailing gap; the matching left padding re-centres them */
.lk-stage .cap b { display: block; font-family: $display; font-size: 1.2rem; font-weight: 400;
  letter-spacing: 0.14em; padding-left: 0.14em; text-transform: uppercase; color: $ink; text-shadow: $title_glow; }
.lk-stage .cap span { display: block; margin-top: 8px; font-size: 0.68rem; font-weight: 600;
  letter-spacing: 0.42em; padding-left: 0.42em; text-transform: uppercase; color: $muted; }

.lk-hero, [data-testid="stForm"], [data-testid="stAlert"], .lk-foot { position: relative; z-index: 2; }
.lk-hero { margin-bottom: 24px; }
.lk-hero .eyebrow { font-size: 0.7rem; font-weight: 600; letter-spacing: 0.44em; text-transform: uppercase;
  color: $ink2; animation: ui-fade 1s $delay_hero ease both; }
.lk-hero h1 { font-family: $display; font-size: 2.3rem; font-weight: 400; letter-spacing: 0.1em;
  line-height: 1.05; text-transform: uppercase; white-space: nowrap; color: $ink; margin: 6px 0 0;
  padding: 0; text-shadow: $title_glow;
  animation: ui-letters 1.1s $delay_hero cubic-bezier(0.2, 0.7, 0.2, 1) both; }
.lk-hero .rule { width: 64px; height: 2px; margin: 18px 0 0; background: $cyan; box-shadow: 0 0 14px $cyan;
  transform-origin: left; animation: ui-grow 0.9s $delay_form ease both; }
.lk-hero p { margin: 16px 0 0; color: $muted; font-size: 0.9rem; line-height: 1.55;
  animation: ui-rise 0.9s $delay_form ease both; }
[data-testid="stForm"] { padding: 22px 22px 18px !important;
  animation: ui-rise 0.9s $delay_form cubic-bezier(0.2, 0.7, 0.2, 1) both; }
.lk-foot { margin-top: 18px; color: $muted; font-size: 0.68rem; letter-spacing: 0.22em;
  text-transform: uppercase; animation: ui-fade 1s $delay_foot ease both; }
.st-key-lock_theme { position: fixed; top: 18px; right: 22px; width: 170px !important; z-index: 5;
  animation: ui-fade 1s $delay_foot ease both; }

/* the planet on the horizon and its two neighbours */
.lk-planet { position: fixed; left: 50%; bottom: calc(-1 * max(1500px, 150vw) + 13vh);
  width: max(1500px, 150vw); height: max(1500px, 150vw); margin-left: calc(-0.5 * max(1500px, 150vw));
  border-radius: 50%; pointer-events: none; z-index: 0; background: $planet; box-shadow: $planet_glow;
  animation: lk-planet-in 1.8s cubic-bezier(0.2, 0.7, 0.2, 1) both, ui-breathe 5s 1.8s ease-in-out infinite alternate; }
@keyframes lk-planet-in { from { transform: translateY(160px); opacity: 0; } to { transform: none; opacity: 1; } }
.lk-moon { position: fixed; border-radius: 50%; pointer-events: none; z-index: 0; }
.lk-moon.left { left: -30px; top: 70vh; width: 84px; height: 84px;
  background: radial-gradient(circle at 68% 30%, #e9e3cf, #9aa58f 45%, #2a3340 80%);
  box-shadow: 0 0 30px rgba(220, 220, 190, 0.25);
  animation: lk-moon-left 1.6s 0.3s cubic-bezier(0.2, 0.7, 0.2, 1) both, ui-float 7s 1.9s ease-in-out infinite alternate; }
.lk-moon.right { right: -28px; top: 13vh; width: 74px; height: 74px;
  background: radial-gradient(circle at 32% 30%, #ffb07a, #c2522c 48%, #3a1410 82%);
  box-shadow: 0 0 30px rgba(255, 130, 80, 0.3);
  animation: lk-moon-right 1.6s 0.45s cubic-bezier(0.2, 0.7, 0.2, 1) both, ui-float 8s 2.1s ease-in-out infinite alternate-reverse; }
@keyframes lk-moon-left { from { transform: translateX(-120px); opacity: 0; } to { transform: none; opacity: 1; } }
@keyframes lk-moon-right { from { transform: translateX(120px); opacity: 0; } to { transform: none; opacity: 1; } }

/* narrow screens: no room for two halves, so the seal settles above the form */
@media (max-width: 900px) {
  .block-container { margin-left: auto !important; padding: 30vh 16px 2rem !important;
    justify-content: flex-start; }
  .lk-stage { transform: translate(-50%, calc(-50% - 30vh)) scale(0.42); animation-name: $stage_name_sm; }
  .lk-stage .cap { display: none; }
  .lk-hero h1 { font-size: 2.4rem; }
}
@keyframes lk-intro-sm {
  0%   { opacity: 0; transform: translate(-50%, -50%) scale(0.82); filter: blur(12px); }
  17%  { opacity: 1; transform: translate(-50%, -50%) scale(1); filter: none; }
  72%  { opacity: 1; transform: translate(-50%, -50%) scale(1); filter: none;
         animation-timing-function: cubic-bezier(0.65, 0, 0.2, 1); }
  100% { opacity: 1; transform: translate(-50%, calc(-50% - 30vh)) scale(0.42); filter: none; }
}
</style>
""")


def _lock_css(intro: bool) -> str:
    t = INTRO_SECONDS
    wait = (lambda s: f"{s:.1f}s") if intro else (lambda s: "0s")
    return LOCK_CSS.substitute(
        LOCK_THEME[ui.THEME], ink=ui.INK, ink2=ui.INK2, muted=ui.MUTED, cyan=ui.CYAN, amber=ui.AMBER,
        display=ui.DISPLAY, title_glow=ui.THEMES[ui.THEME]["title_glow"],
        stage_anim=f"lk-intro {t}s both" if intro else "none",
        stage_name_sm="lk-intro-sm" if intro else "none",
        delay_cap=wait(0.5), delay_hero=wait(t - 0.9), delay_form=wait(t - 0.7), delay_foot=wait(t - 0.2))


def _lock_screen():
    intro = not st.session_state.get("lock_seen")
    st.session_state.lock_seen = True
    st.markdown(_lock_css(intro), unsafe_allow_html=True)
    st.markdown(
        '<div class="lk-planet"></div><div class="lk-moon left"></div><div class="lk-moon right"></div>'
        '<div class="lk-stage"><div class="halo"></div><div class="ring"></div><div class="ring two"></div>'
        f'<img src="{ui.asset_uri(ui.SEAL)}" alt="Turin Polytechnic University in Tashkent">'
        '<div class="cap"><b>Turin Polytechnic</b><span>University in Tashkent</span></div></div>'
        '<div class="lk-hero"><div class="eyebrow">University</div><h1>Intelligence</h1>'
        "<div class=\"rule\"></div><p>Qarorlarni qo'llab-quvvatlash tizimi.<br>"
        "Davom etish uchun tizimga kiring.</p></div>",
        unsafe_allow_html=True)
    ui.theme_button(key="lock_theme")

    if not accounts():
        st.error("Kirish hisobi sozlanmagan. Uni yaratish uchun: `python 08_Dashboard/set_password.py`")
        return

    wait = int(st.session_state.get("auth_locked_until", 0) - time.time())
    with st.form("login", border=False):
        username = st.text_input("Login", autocomplete="username")
        password = st.text_input("Parol", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Kirish", type="primary", width="stretch", disabled=wait > 0)
    if wait > 0:
        st.warning(f"Juda ko'p noto'g'ri urinish. {wait} soniyadan keyin qayta urinib ko'ring.")
    elif submitted:
        acc = check(username, password)
        if acc:
            _sign_in(acc)
            st.session_state.pop("auth_fails", None)
            st.rerun()
        time.sleep(0.6)                      # slow down guessing
        fails = st.session_state.get("auth_fails", 0) + 1
        st.session_state.auth_fails = fails
        if fails >= MAX_ATTEMPTS:
            st.session_state.auth_fails = 0
            st.session_state.auth_locked_until = time.time() + LOCK_SECONDS
            st.rerun()
        st.error("Login yoki parol noto'g'ri.")
    st.markdown('<div class="lk-foot">Education · Science · Production</div>', unsafe_allow_html=True)


def require_login():
    """Show the lock screen and stop the script until the user has signed in."""
    if not st.session_state.get("auth_user"):
        _lock_screen()
        st.stop()


def sidebar_user(role_label: str):
    """Who is signed in and in which role, the theme switch, and a button that locks
    the dashboard again."""
    faculty = st.session_state.get("own_faculty_name")
    st.markdown(f'<div class="ui-user"><i></i><span>Kirgan: <b>{st.session_state.auth_user}</b><br>'
                f'{role_label}{" · " + faculty if faculty else ""}</span></div>', unsafe_allow_html=True)
    ui.theme_button()
    if st.button("Chiqish", icon=":material/lock:", width="stretch"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
