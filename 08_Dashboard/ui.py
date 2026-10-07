"""Shared dashboard helpers: cached data access, colours, chart styling, formats."""
import base64
import io
import json
import random
import sys
import threading
from functools import lru_cache
from pathlib import Path
from string import Template

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import metrics as m  # noqa: E402

ASSETS = Path(__file__).resolve().parent / "assets"

# ---------------------------------------------------------------------------
# Deep-space style in two themes. Dark: a navy night sky with drifting stars,
# glass panels with blue glow. Light: the same layout at daybreak - a pale sky,
# white glass, navy type. Serif capitals for titles and one teal accent in
# both. Colour still carries meaning: teal marks the selection, amber and red
# mark trouble.
#
# Upper-case keys become module constants (ui.INK, ui.BLUE, ...) that the
# pages and charts read; lower-case keys are used only inside the stylesheet.
# ---------------------------------------------------------------------------
THEMES = {
    "dark": dict(
        BG="#070b1a", PANEL="rgba(20, 30, 62, 0.58)", INK="#eef2ff", INK2="#c3cbe6", MUTED="#8b96b8",
        GRID="rgba(255,255,255,0.07)", AXIS="rgba(255,255,255,0.18)", LINE="rgba(126, 156, 255, 0.16)",
        BLUE="#5b9bff", CYAN="#37e0d0", VIOLET="#a78bfa", AMBER="#ffb454", RED="#ff5d73",
        DIM="rgba(150, 168, 220, 0.30)", HOVER_BG="#101a3a", RISK_LOW="#3d5a99", GRADE_MID="#6b7aa8",
        RISK_TAG={"Past": "background-color:rgba(61,90,153,0.35);color:#c3cbe6",
                  "O'rta": "background-color:rgba(91,155,255,0.28);color:#cfe1ff",
                  "Yuqori": "background-color:rgba(255,180,84,0.26);color:#ffd9a3",
                  "Kritik": "background-color:rgba(255,93,115,0.34);color:#ffd0d7"},
        SEAL="ttpu_seal.png", LOGO="logo.svg",
        app_bg="radial-gradient(1200px 720px at 82% -12%, rgba(64, 110, 255, 0.24), transparent 62%), "
               "radial-gradient(900px 620px at -6% 104%, rgba(55, 224, 208, 0.09), transparent 62%), "
               "radial-gradient(700px 500px at 40% 120%, rgba(120, 90, 255, 0.10), transparent 60%), #070b1a",
        stars="block", shadow="rgba(2, 6, 24, 0.45)", title_glow="0 0 34px rgba(110, 160, 255, 0.4)",
        sidebar="rgba(8, 13, 32, 0.72)", track="rgba(255, 255, 255, 0.09)",
        btn_bg="linear-gradient(180deg, #ffffff, #dfe9ff)", btn_ink="#0a1330",
        btn_ring="rgba(255, 255, 255, 0.4)",
        orb="radial-gradient(circle at 50% 0%, #3a86ff 0%, #143f9f 16%, #0a1f55 38%, #070d24 60%)",
        orb_glow="0 0 70px 6px rgba(70, 140, 255, 0.5), inset 0 10px 34px rgba(150, 205, 255, 0.5)"),
    "light": dict(
        BG="#eef2fb", PANEL="rgba(255, 255, 255, 0.74)", INK="#0d1736", INK2="#34406a", MUTED="#65709a",
        GRID="rgba(13,23,54,0.08)", AXIS="rgba(13,23,54,0.25)", LINE="rgba(60, 90, 180, 0.18)",
        BLUE="#2f6fed", CYAN="#0d9f93", VIOLET="#7c5ce0", AMBER="#d98a14", RED="#e23c56",
        DIM="rgba(60, 80, 140, 0.28)", HOVER_BG="#ffffff", RISK_LOW="#b9c6e6", GRADE_MID="#9aa6c8",
        RISK_TAG={"Past": "background-color:rgba(120,140,190,0.22);color:#34406a",
                  "O'rta": "background-color:rgba(47,111,237,0.18);color:#1c4bb3",
                  "Yuqori": "background-color:rgba(217,138,20,0.24);color:#8a5200",
                  "Kritik": "background-color:rgba(226,60,86,0.22);color:#a8182f"},
        SEAL="ttpu_seal_navy.png", LOGO="logo_light.svg",
        app_bg="radial-gradient(1200px 720px at 82% -12%, rgba(70, 120, 255, 0.22), transparent 62%), "
               "radial-gradient(900px 620px at -6% 104%, rgba(13, 159, 147, 0.12), transparent 62%), "
               "radial-gradient(700px 500px at 40% 120%, rgba(124, 92, 224, 0.10), transparent 60%), #eef2fb",
        stars="none", shadow="rgba(40, 60, 120, 0.14)", title_glow="none",
        sidebar="rgba(232, 238, 251, 0.78)", track="rgba(13, 23, 54, 0.10)",
        btn_bg="linear-gradient(180deg, #3d7bff, #1f4fd1)", btn_ink="#ffffff",
        btn_ring="rgba(47, 111, 237, 0.35)",
        orb="radial-gradient(circle at 50% 0%, #8fbcff 0%, #b9d4ff 16%, #dbe8ff 38%, rgba(255,255,255,0) 60%)",
        orb_glow="0 0 70px 6px rgba(70, 140, 255, 0.28), inset 0 10px 34px rgba(255, 255, 255, 0.8)"),
}
# The matching Streamlit theme (inputs, tables, menus) is in .streamlit/config.toml:
# [theme.dark] and [theme.light]. The browser decides which of the two it shows.
PAGES = ("overview", "faculty", "exams", "risk", "scenarios", "agent", "more")   # url paths
ALERT_ROW, ALERT_GAP = 76, 8      # px: one alert row with its gap (.ui-alert), for charts set beside a list
# Century Gothic everywhere (it ships with Windows/Office). Questrial is the closest
# web font and is loaded only as a fallback for machines without Century Gothic.
FONT = '"Century Gothic", CenturyGothic, "Questrial", AppleGothic, "Segoe UI", system-ui, sans-serif'
DISPLAY = FONT


def _stars(n: int, tile: int, seed: int, size=(0.6, 1.3)) -> str:
    """A repeatable tile of `n` stars as stacked CSS radial gradients."""
    rnd = random.Random(seed)
    dots = []
    for _ in range(n):
        r, a = rnd.uniform(*size), rnd.uniform(0.35, 0.95)
        dots.append(f"radial-gradient({r:.1f}px {r:.1f}px at {rnd.randrange(tile)}px "
                    f"{rnd.randrange(tile)}px, rgba(255,255,255,{a:.2f}), transparent)")
    return ",".join(dots)


_CSS = Template("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Questrial&display=swap');

html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"], p, li, label, input,
button, h1, h2, h3, h4, td, th { font-family: $font; }

/* ------------------------------------------------------------ night sky */
.stApp { background: $app_bg; background-attachment: fixed; }
/* Two star layers, each one tile larger than the window and moved by exactly one
   tile, so the drift loops seamlessly and runs on the compositor (no repaints). */
.stApp::before, .stApp::after { content: ""; display: $stars; position: fixed; pointer-events: none; z-index: 0;
  will-change: transform; }
.stApp::before { inset: -620px -620px 0 0; background-image: $stars_far; background-size: 620px 620px;
  animation: ui-drift 180s linear infinite; opacity: 0.75; }
.stApp::after { inset: -940px 0 0 -940px; background-image: $stars_near; background-size: 940px 940px;
  animation: ui-drift-near 120s linear infinite, ui-twinkle 5s ease-in-out infinite alternate; }
[data-testid="stAppViewContainer"] { z-index: 1; background: transparent; }
[data-testid="stMain"], [data-testid="stHeader"], [data-testid="stBottom"] > div,
[data-testid="stBottomBlockContainer"] { background: transparent; }
.block-container { max-width: 1240px; padding-top: 2.4rem; padding-bottom: 4rem; --kpi-h: 138px; }
/* Room for the scrollbar is kept from the start: otherwise the page narrows when it
   appears and tables measured just before are left sticking out past the right edge. */
[data-testid="stMain"] { scrollbar-gutter: stable; }
[data-testid="stDataFrame"] { max-width: 100%; }
/* segmented controls are as tall as the dropdowns and inputs they sit beside */
[data-testid="stButtonGroup"] button[data-variant="segmented_control"] { min-height: 40px; }
/* A block that only carries a stylesheet must not take a row (and its gap) in the layout. */
[data-testid="stElementContainer"]:has([data-testid="stMarkdownContainer"] > style:only-child),
[data-testid="stElementContainer"]:has([data-testid="stHtml"]) { display: none; }   /* run_js() */

@keyframes ui-drift { to { transform: translate3d(-620px, 620px, 0); } }
@keyframes ui-drift-near { to { transform: translate3d(940px, 940px, 0); } }
@keyframes ui-twinkle { from { opacity: 0.35; } to { opacity: 0.95; } }
@keyframes ui-rise { from { opacity: 0; transform: translateY(22px); } to { opacity: 1; transform: none; } }
@keyframes ui-fade { from { opacity: 0; } to { opacity: 1; } }
@keyframes ui-grow { from { transform: scaleX(0); } to { transform: scaleX(1); } }
@keyframes ui-fill { from { width: 0; } }
@keyframes ui-float { from { transform: translateY(-7px); } to { transform: translateY(7px); } }
@keyframes ui-spin { to { transform: rotate(360deg); } }
@keyframes ui-breathe { from { opacity: 0.55; } to { opacity: 1; } }
@keyframes ui-letters { from { opacity: 0; transform: translateY(16px); filter: blur(8px); }
  to { opacity: 1; transform: none; filter: none; } }

/* ------------------------------------------------------------ page title */
.ui-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px;
  margin: 0 0 30px; }
.ui-header .eyebrow { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.42em;
  text-transform: uppercase; color: $ink2; animation: ui-fade 0.9s ease both; }
.ui-header h1 { font-family: $display; font-size: clamp(1.6rem, 2.8vw, 2.5rem); font-weight: 400;
  color: $ink; margin: 4px 0 0; padding: 0; letter-spacing: 0.05em; line-height: 1.05;
  text-transform: uppercase; text-shadow: $title_glow;
  animation: ui-letters 1.1s cubic-bezier(0.2, 0.7, 0.2, 1) both; }
h1 [data-testid="stHeaderActionElements"] { display: none; }
.ui-header .rule { width: 64px; height: 2px; margin: 16px 0 0; background: $cyan;
  box-shadow: 0 0 14px $cyan; transform-origin: left; animation: ui-grow 0.8s 0.35s ease both; }
.ui-header p { margin: 14px 0 0; color: $muted; font-size: 0.95rem;
  animation: ui-rise 0.8s 0.3s ease both; }
.ui-chip { white-space: nowrap; font-size: 0.7rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.14em; color: $muted; padding: 8px 16px; border: 1px solid $line;
  border-radius: 999px; background: $panel; backdrop-filter: blur(10px);
  animation: ui-fade 1s 0.4s ease both; }
.ui-chip b { color: $ink; font-weight: 600; }

/* section headings: small spaced capitals with a short glowing tick */
h3 { font-size: 0.74rem !important; font-weight: 600 !important; text-transform: uppercase;
  letter-spacing: 0.22em; color: $ink2 !important; padding: 0 0 10px !important;
  margin-top: 2rem !important; display: flex; align-items: center; gap: 12px; }
h3::before { content: ""; width: 22px; height: 2px; background: $cyan; box-shadow: 0 0 10px $cyan;
  flex: 0 0 22px; }

/* ---------------------------------------------------------- glass panels */
.ui-kpi, .ui-score, .ui-alert, [data-testid="stPlotlyChart"], [data-testid="stMetric"],
[data-testid="stExpander"] details, [data-testid="stForm"] {
  background: $panel; border: 1px solid $line; border-radius: 18px;
  backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
  box-shadow: 0 18px 44px $shadow, inset 0 1px 0 rgba(255, 255, 255, 0.05); }

.ui-kpi { position: relative; overflow: hidden; box-sizing: border-box; padding: 16px 18px;
  min-height: var(--kpi-h);
  margin-bottom: 14px; animation: ui-rise 0.7s cubic-bezier(0.2, 0.7, 0.2, 1) both;
  transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease; }
.ui-kpi::after { content: ""; position: absolute; left: 18px; right: 18px; top: 0; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(120, 170, 255, 0.7), transparent); }
.ui-kpi:hover { transform: translateY(-4px); border-color: rgba(120, 170, 255, 0.45);
  box-shadow: 0 22px 50px $shadow, 0 0 28px rgba(79, 140, 255, 0.22); }
[data-testid="stColumn"]:nth-child(2) .ui-kpi { animation-delay: 0.08s; }
[data-testid="stColumn"]:nth-child(3) .ui-kpi { animation-delay: 0.16s; }
[data-testid="stColumn"]:nth-child(4) .ui-kpi { animation-delay: 0.24s; }
.ui-kpi .lab { min-height: 2.8em; font-size: 0.68rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.14em;
  color: $muted; line-height: 1.4; }
.ui-kpi .q { display: inline-block; width: 14px; height: 14px; line-height: 13px; text-align: center;
  border: 1px solid $muted; border-radius: 50%; font-size: 0.58rem; text-transform: none;
  letter-spacing: 0; margin-left: 4px; cursor: help; }
.ui-kpi .val { font-size: clamp(1.3rem, 2.1vw, 2.05rem); font-weight: 500; color: $ink;
  letter-spacing: -0.02em; line-height: 1.15; margin-top: 6px; font-variant-numeric: tabular-nums;
  white-space: nowrap; }
.ui-kpi .chg { font-size: 0.78rem; font-weight: 600; margin-top: 4px; }

[data-testid="stMetric"] { padding: 16px 18px !important; min-height: 116px; }
[data-testid="stMetricLabel"] { overflow: visible; min-height: 1.1rem; }
[data-testid="stMetricLabel"] p { font-size: 0.68rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.14em; color: $muted; line-height: 1.5; }
[data-testid="stMetricValue"] { font-size: 2.05rem; font-weight: 500; color: $ink;
  letter-spacing: -0.02em; line-height: 1.1; font-variant-numeric: tabular-nums; }

/* the headline score: a planet rising behind a very large figure */
.ui-score { position: relative; overflow: hidden; box-sizing: border-box; padding: 22px 24px 26px;
  min-height: calc(2 * var(--kpi-h) + 14px);
  margin-bottom: 14px; animation: ui-rise 0.8s cubic-bezier(0.2, 0.7, 0.2, 1) both; }
.ui-score .lab { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.3em;
  color: $ink2; }
.ui-score .fig { font-family: $display; font-size: clamp(3.6rem, 6.4vw, 5.6rem); font-weight: 400;
  line-height: 1; color: $ink; margin: 8px 0 14px; white-space: nowrap; font-variant-numeric: lining-nums tabular-nums;
  text-shadow: $title_glow; position: relative; z-index: 1; }
.ui-score .fig span { font-family: $font; font-size: 1.2rem; color: $muted; font-weight: 400;
  text-shadow: none; }
.ui-score .bar { height: 6px; border-radius: 6px; background: $track;
  position: relative; z-index: 1; }
.ui-score .bar i { display: block; height: 6px; border-radius: 6px;
  background: linear-gradient(90deg, $blue, $cyan); box-shadow: 0 0 16px rgba(55, 224, 208, 0.7);
  animation: ui-fill 1.4s 0.3s cubic-bezier(0.2, 0.7, 0.2, 1) both; }
.ui-score .note { margin-top: 12px; color: $muted; font-size: 0.8rem; position: relative; z-index: 1; }
.ui-score .orb { position: absolute; left: 50%; bottom: -330px; width: 520px; height: 520px;
  margin-left: -100px; border-radius: 50%;
  background: $orb; box-shadow: $orb_glow;
  animation: ui-breathe 4.5s ease-in-out infinite alternate; }

/* alerts: glass rows, the level as a small glowing tag */
.ui-alert { display: grid; grid-template-columns: 140px 1fr; gap: 16px; align-items: center;
  box-sizing: border-box; min-height: 68px; padding: 10px 16px; margin-bottom: 8px; border-radius: 14px;
  animation: ui-rise 0.6s ease both; transition: transform 0.2s ease, border-color 0.2s ease; }
.ui-alert:hover { transform: translateX(4px); border-color: rgba(120, 170, 255, 0.4); }
.ui-alert .tag { display: inline-flex; align-items: center; gap: 9px; font-size: 0.68rem;
  font-weight: 600; text-transform: uppercase; letter-spacing: 0.14em; color: $ink2; }
.ui-alert .dot { width: 9px; height: 9px; flex: 0 0 9px; border-radius: 50%;
  box-shadow: 0 0 10px currentColor; animation: ui-breathe 1.8s ease-in-out infinite alternate; }
.ui-alert .msg { color: $ink; font-size: 0.94rem; line-height: 1.45; }

[data-testid="stPlotlyChart"] { overflow: hidden;
  animation: ui-rise 0.8s 0.12s cubic-bezier(0.2, 0.7, 0.2, 1) both;
  transition: border-color 0.25s ease, box-shadow 0.25s ease; }
[data-testid="stPlotlyChart"]:hover { border-color: rgba(120, 170, 255, 0.4); }
[data-testid="stDataFrame"] { border-radius: 14px; overflow: hidden; border: 1px solid $line;
  box-shadow: 0 18px 44px $shadow; animation: ui-rise 0.8s 0.12s ease both; }
[data-testid="stExpander"] details { overflow: hidden; }
[data-testid="stExpander"] summary p { font-weight: 600; color: $ink; font-size: 0.86rem; }
[data-testid="stMain"] [data-testid="stCaptionContainer"],
[data-testid="stMain"] [data-testid="stCaptionContainer"] p { color: $muted !important; opacity: 1;
  font-size: 0.8rem; }

/* buttons: the light pill with a blue halo is the one primary action */
button[kind="primary"], button[kind="primaryFormSubmit"] {
  background: $btn_bg !important; color: $btn_ink !important;
  border: 0 !important; font-weight: 600 !important; letter-spacing: 0.12em; text-transform: uppercase;
  box-shadow: 0 0 0 1px $btn_ring, 0 10px 34px rgba(79, 140, 255, 0.55);
  transition: transform 0.2s ease, box-shadow 0.2s ease; }
button[kind="primary"] p, button[kind="primaryFormSubmit"] p { font-size: 0.78rem; font-weight: 600; }
button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover { transform: translateY(-2px);
  box-shadow: 0 0 0 1px $btn_ring, 0 14px 44px rgba(79, 140, 255, 0.8); }
button[kind="secondary"], [data-testid="stDownloadButton"] button {
  background: $panel; border: 1px solid $line; backdrop-filter: blur(10px);
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease; }
button[kind="secondary"]:hover, [data-testid="stDownloadButton"] button:hover {
  transform: translateY(-2px); border-color: rgba(120, 170, 255, 0.6);
  box-shadow: 0 0 24px rgba(79, 140, 255, 0.3); }

.ui-profile { display: flex; align-items: baseline; gap: 16px; flex-wrap: wrap; margin: 4px 0 14px;
  animation: ui-fade 0.7s ease both; }
.ui-profile .name { font-family: $display; font-size: 1.45rem; font-weight: 700; color: $ink;
  letter-spacing: 0.02em; }
.ui-profile .meta { color: $muted; font-size: 0.85rem; }
.ui-pill { padding: 4px 12px; font-size: 0.68rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.12em; border-radius: 999px; }

.ui-note { margin-top: 40px; padding-top: 14px; border-top: 1px solid $line; color: $muted;
  font-size: 0.74rem; letter-spacing: 0.02em; }

/* --------------------------------------------------------------- sidebar */
[data-testid="stSidebar"] { background: $sidebar; border-right: 1px solid $line;
  backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px); }
[data-testid="stSidebar"] [data-testid="stSidebarNav"] a { border-radius: 12px; margin: 2px 0;
  transition: background 0.2s ease, transform 0.2s ease; }
[data-testid="stSidebar"] [data-testid="stSidebarNav"] a span { font-size: 0.74rem; font-weight: 500;
  text-transform: uppercase; letter-spacing: 0.12em; }
[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover { transform: translateX(3px); }
[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] {
  background: linear-gradient(90deg, rgba(79, 140, 255, 0.28), rgba(79, 140, 255, 0.04));
  box-shadow: inset 2px 0 0 $cyan, 0 0 22px rgba(79, 140, 255, 0.18); }
[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] span {
  font-weight: 600; color: $ink; }
[data-testid="stSidebarUserContent"] { padding-top: 0.5rem; }
[data-testid="stSidebarHeader"] img { height: 46px; }
.ui-user { display: flex; align-items: center; gap: 10px; margin: 2px 0 10px; font-size: 0.8rem;
  color: $ink2; }
.ui-user i { width: 8px; height: 8px; border-radius: 50%; background: $cyan; box-shadow: 0 0 10px $cyan;
  animation: ui-breathe 1.8s ease-in-out infinite alternate; }
.ui-user b { color: $ink; font-weight: 600; }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
}
</style>
""")
_STARS = dict(stars_far=_stars(46, 620, 7), stars_near=_stars(18, 940, 21, size=(1.0, 1.9)))


def _palette(name: str) -> dict:
    """Every colour constant of one theme, the derived ones and its stylesheet."""
    t = THEMES[name]
    p = {k: v for k, v in t.items() if k.isupper()}
    p["THEME"] = name
    p["SERIES"] = [p["BLUE"], p["CYAN"], p["VIOLET"], p["AMBER"]]
    # Risk levels are ordered: a calm blue ramp that turns amber, then red.
    p["RISK_COLORS"] = dict(zip(config.RISK_ORDER, [p["RISK_LOW"], p["BLUE"], p["AMBER"], p["RED"]]))
    p["STATUS"] = {"good": p["CYAN"], "warning": p["AMBER"], "serious": "#ff8a5c", "critical": p["RED"]}
    p["GRADE_COLORS"] = [p["CYAN"], p["BLUE"], p["GRADE_MID"], p["RED"]]      # 5, 4, 3, 2
    p["ALERT_STYLE"] = {  # level -> (label, marker colour)
        "critical": ("Kritik", p["RED"]), "warning": ("Ogohlantirish", p["AMBER"]),
        "attention": ("E'tibor", p["BLUE"]), "positive": ("Ijobiy", p["CYAN"])}
    p["CSS"] = _CSS.substitute(
        font=FONT, display=DISPLAY, bg=p["BG"], panel=p["PANEL"], ink=p["INK"], ink2=p["INK2"],
        muted=p["MUTED"], line=p["LINE"], blue=p["BLUE"], cyan=p["CYAN"], **_STARS,
        **{k: v for k, v in t.items() if k.islower()})
    return p


# Two people can have the dashboard open in different themes at the same time, so the
# active theme belongs to the script run (one thread each), not to the module.
_PALETTES = {name: _palette(name) for name in THEMES}
_run = threading.local()


class _Active:
    """P.INK, P.BLUE, ... - the constants of the theme of the current run."""
    def __getattr__(self, name):
        try:
            return _PALETTES[getattr(_run, "theme", "dark")][name]
        except KeyError:
            raise AttributeError(name) from None


P = _Active()


def __getattr__(name):           # ui.INK, ui.SERIES, ... from the pages resolve the same way
    return getattr(P, name)


def apply_theme(name: str):
    """Make `name` the theme of this script run."""
    _run.theme = name


def current_theme() -> str:
    """The theme this browser is showing (Streamlit reports it with every run)."""
    shown = st.context.theme.type
    return shown if shown in THEMES else "dark"


def run_js(code: str):
    """Run a snippet in the page (cookies, theme choice): things only the browser can do."""
    st.html(f"<script>{code}</script>", unsafe_allow_javascript=True)


def theme_button(key: str = "theme_toggle"):
    """The light/dark switch, for this browser only.

    Streamlit keeps the choice in the browser's localStorage (one entry per page
    address) and reads it when the page loads, so the switch writes it there and
    reloads; the signed session cookie (auth.py) keeps the user logged in."""
    dark = P.THEME == "dark"
    if st.button("Yorug' rejim" if dark else "Tungi rejim", key=key, width="stretch",
                 icon=":material/light_mode:" if dark else ":material/dark_mode:"):
        paths = json.dumps(["/"] + [f"/{p}" for p in PAGES])
        run_js(f"""
            const choice = JSON.stringify("{'Light' if dark else 'Dark'}");
            const paths = new Set({paths}.concat([window.location.pathname]));
            for (const p of paths) window.localStorage.setItem(`stActiveTheme-${{p}}-v2`, choice);
            window.location.reload();""")


def inject_css():
    st.markdown(P.CSS, unsafe_allow_html=True)


@lru_cache(maxsize=None)
def asset_uri(name: str) -> str:
    """An image from the assets folder as a data URI, for use inside custom HTML."""
    kind = {"png": "image/png", "svg": "image/svg+xml", "jpg": "image/jpeg"}[name.rsplit(".", 1)[-1]]
    return f"data:{kind};base64,{base64.b64encode((ASSETS / name).read_bytes()).decode()}"


def header(title: str, subtitle: str | None = None, chip: bool = True):
    """Page title with the current semester shown as a chip on the right."""
    sem = st.session_state.get("semester_label") if chip else None
    chip = f'<span class="ui-chip">Semestr: <b>{sem}</b></span>' if sem else ""
    sub = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(f'<div class="ui-header"><div><div class="eyebrow">University Intelligence</div>'
                f'<h1>{title}</h1><div class="rule"></div>{sub}</div>{chip}</div>',
                unsafe_allow_html=True)


# --------------------------------------------------------------------- data
@st.cache_resource
def engine():
    return config.get_engine()


@st.cache_data(show_spinner="Ma'lumotlar ombordan yuklanmoqda...", max_entries=2)
def _load(version: str) -> dict:
    return m.load_all(engine())


def get_data() -> tuple[dict, str]:
    """Warehouse snapshot, reloaded automatically when the ETL or ML has run."""
    version = m.data_version(engine())
    st.session_state["data_version"] = version
    return _load(version), version


@st.fragment(run_every="30s")
def watch_for_new_data():
    """Re-run the app as soon as a new ETL run or scoring lands in the database."""
    if m.data_version(engine()) != st.session_state.get("data_version"):
        st.rerun()


def faculty_color(d: dict) -> dict:
    """Bars are labelled on the axis, so every faculty is drawn in the same colour."""
    return {int(k): P.BLUE for k in d["faculties"].FacultyKey}


# ------------------------------------------------------------------ formats
def pct(v, digits=1):
    return "-" if v is None or pd.isna(v) else f"{v * 100:.{digits}f}%"


def num(v):
    return "-" if v is None or pd.isna(v) else f"{v:,.0f}".replace(",", " ")


def money(v):
    """so'm amounts in milliard (10^9)."""
    return "-" if v is None or pd.isna(v) else f"{v / 1e9:,.1f} mlrd".replace(",", " ")


def kpi(col, label, value, delta=None, inverse=False, help=None):
    """A number on a glass card: small spaced label, large figure, and the
    change below it. Teal marks a change for the better, red for the worse."""
    change = ""
    if delta:
        zero = delta.lstrip("+-").split()[0].strip("0.") == ""
        down = delta.startswith("-") and not zero
        bad = (not zero) and (down != inverse)
        arrow = "" if zero else ("&#9660; " if down else "&#9650; ")
        change = (f'<div class="chg" style="color:{P.MUTED if zero else P.RED if bad else P.CYAN}">'
                  f'{arrow}{delta.lstrip("+-")}</div>')
    tip = f' title="{help}"' if help else ""
    mark = ' <span class="q">i</span>' if help else ""
    col.markdown(f'<div class="ui-kpi"{tip}><div class="lab">{label}{mark}</div>'
                 f'<div class="val">{value}</div>{change}</div>', unsafe_allow_html=True)


def pp(cur, prev):
    """Change in percentage points."""
    return None if prev is None or pd.isna(prev) else f"{(cur - prev) * 100:+.1f} f.p."


# ------------------------------------------------------------------- charts
def style(fig: go.Figure, height=300, pct_axis=None, legend=True, title=None) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=18, r=18, t=(52 if title else 18) + (28 if legend else 0), b=14),
        title=dict(text=title, font=dict(size=13, color=P.INK), x=0, xanchor="left", pad=dict(l=18, t=16),
                   y=1, yanchor="top") if title else None,
        font=dict(family=FONT, size=13, color=P.INK2), paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", showlegend=legend,
        legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, font=dict(size=11, color=P.INK2)),
        hoverlabel=dict(font=dict(family=FONT, size=12, color=P.INK), bgcolor=P.HOVER_BG,
                        bordercolor="rgba(120,170,255,0.5)"), bargap=0.42)
    fig.update_xaxes(showgrid=False, linecolor=P.AXIS, linewidth=1, ticks="",
                     tickfont=dict(color=P.MUTED), title=None)
    fig.update_yaxes(gridcolor=P.GRID, zeroline=False, linecolor="rgba(0,0,0,0)",
                     tickfont=dict(color=P.MUTED), title=None)
    if pct_axis == "y":
        fig.update_yaxes(tickformat=".0%")
    elif pct_axis == "x":
        fig.update_xaxes(tickformat=".0%")
    return fig


def show(fig):
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def glow_line(fig: go.Figure, x, y, name, color, fmt, width=3, marker=7, unified=False):
    """A smooth line with a soft halo under it, as in a lit instrument panel."""
    curve = dict(shape="spline", smoothing=0.6)      # gentle: the curve stays close to the points
    fig.add_scatter(x=x, y=y, mode="lines", line=dict(color=color, width=width + 9, **curve),
                    opacity=0.16, hoverinfo="skip", showlegend=False)
    lead = "" if unified else "%{x}<br>"
    fig.add_scatter(x=x, y=y, name=name, mode="lines+markers",
                    line=dict(color=color, width=width, **curve),
                    marker=dict(size=marker, color=P.BG, line=dict(color=color, width=2)),
                    hovertemplate=f"{lead}{name + ': ' if unified else ''}%{{y:{fmt}}}<extra></extra>")


def line(df, x, y, title=None, percent=False, height=280, name=None):
    """Single-series trend line (the title names the series, so no legend)."""
    fig = go.Figure()
    glow_line(fig, df[x], df[y], name or title or y, P.BLUE, ".1%" if percent else ".2f")
    return style(fig, height, "y" if percent else None, legend=False, title=title)


def faculty_lines(df, d, y, title=None, percent=False, height=340, highlight=None):
    """One line per faculty. The highlighted faculty glows in the accent and is
    labelled at its last point; the others stay dim as context (their names
    appear on hover), so the eye goes to one line instead of six."""
    fig, fmt = go.Figure(), ".1%" if percent else ".2f"
    order = sorted(zip(d["faculties"].FacultyKey, d["faculties"].FacultyName),
                   key=lambda kv: int(kv[0]) == highlight)          # highlighted line drawn last
    for fk, name in order:
        sub = df[df.FacultyKey == fk].sort_values("SemesterKey")
        if int(fk) != highlight:
            fig.add_scatter(x=sub.SemesterLabel, y=sub[y], name=name, mode="lines+markers",
                            line=dict(color=P.DIM, width=1.5, shape="spline", smoothing=0.6),
                            marker=dict(size=4),
                            hovertemplate=f"{name}: %{{y:{fmt}}}<extra></extra>")
            continue
        glow_line(fig, sub.SemesterLabel, sub[y], name, P.CYAN, fmt, unified=True)
        if len(sub):
            fig.add_annotation(x=sub.SemesterLabel.iloc[-1], y=sub[y].iloc[-1], text=f"<b>{name}</b>",
                               showarrow=False, xanchor="right", yshift=16,
                               font=dict(color=P.CYAN, size=12, family=FONT))
    fig.update_layout(hovermode="x unified")
    return style(fig, height, "y" if percent else None, legend=False, title=title)


def bar_h_height(*frames) -> int:
    """Height that fits the longest of `frames`, so charts placed side by side end level."""
    return max(180, 34 * max(len(f) for f in frames) + 72)


def bar_h(df, value, label, title=None, percent=False, colors=None, height=None, text=True):
    """Horizontal bars, largest on top; one colour unless `colors` maps identity."""
    df = df.iloc[::-1]
    fmt = ".1%" if percent else ",.2f"
    fig = go.Figure(go.Bar(
        x=df[value], y=df[label], orientation="h",
        marker=dict(color=colors[::-1] if colors is not None else P.BLUE, cornerradius=6),
        text=[f"{v:{fmt}}" for v in df[value]] if text else None, textposition="outside",
        textfont=dict(color=P.INK2, size=11), cliponaxis=False,
        hovertemplate=f"%{{y}}<br>%{{x:{fmt}}}<extra></extra>"))
    fig = style(fig, height or bar_h_height(df), "x" if percent else None,
                legend=False, title=title)
    fig.update_yaxes(showgrid=False, tickfont=dict(color=P.INK2))
    fig.update_xaxes(showgrid=True, gridcolor=P.GRID, showticklabels=False)
    fig.update_layout(margin=dict(r=64))
    return fig


def bar_v(df, x, y, title=None, percent=False, colors=None, height=280):
    fmt = ".1%" if percent else ",.0f"
    fig = go.Figure(go.Bar(
        x=df[x], y=df[y], marker=dict(color=colors if colors is not None else P.BLUE, cornerradius=8),
        text=[f"{v:{fmt}}" for v in df[y]], textposition="outside",
        textfont=dict(color=P.INK2, size=11), cliponaxis=False,
        hovertemplate=f"%{{x}}<br>%{{y:{fmt}}}<extra></extra>"))
    return style(fig, height, "y" if percent else None, legend=False, title=title)


def score(value: float, label: str, note: str = ""):
    """The headline score: a very large figure over a 0-100 bar, lit from below
    by a planet on the horizon."""
    st.markdown(
        f'<div class="ui-score"><div class="orb"></div><div class="lab">{label}</div>'
        f'<div class="fig">{value:.0f}<span> / 100</span></div>'
        f'<div class="bar"><i style="width:{value:.0f}%"></i></div>'
        f'<div class="note">{note}</div></div>', unsafe_allow_html=True)


def gauge(value: float, title: str, height=262):
    """One headline score on a 0-100 dial."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value,
        number=dict(font=dict(size=46, color=P.INK, family=FONT), valueformat=".0f"),
        gauge=dict(axis=dict(range=[0, 100], tickvals=[0, 25, 50, 75, 100],
                             tickfont=dict(color=P.MUTED, size=11), tickcolor=P.AXIS),
                   bar=dict(color=P.BLUE, thickness=0.78), bgcolor="rgba(255,255,255,0.08)",
                   borderwidth=0)))
    fig.update_layout(
        height=height, margin=dict(l=28, r=28, t=52, b=10), paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, color=P.INK2),
        title=dict(text=title, font=dict(size=14, color=P.INK), x=0, xanchor="left",
                   y=0.97, yanchor="top"))
    return fig


def season_lines(df, y, title=None, percent=False, height=300):
    """Autumn and spring semesters as two separate lines over academic years.

    The two semesters teach different courses, so one joined line would only
    show a seasonal zigzag; split by season, the year-to-year trend is visible.
    """
    fig, fmt = go.Figure(), ".1%" if percent else ".2f"
    for season, color in zip(("Kuz", "Bahor"), P.SERIES):
        sub = df[df.SemesterName == season].sort_values("SemesterKey")
        glow_line(fig, sub.AcademicYear, sub[y], f"{season} semestri", color, fmt, unified=True)
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(type="category")
    return style(fig, height, "y" if percent else None, title=title)


def shade(df, heat: list[str], formats: dict, tag: str | None = None, rgb=(255, 93, 115)):
    """Table with the columns in `heat` tinted faint-to-bright by value, so the
    worst rows stand out without reading every number. `tag` colours a
    risk-level column. `formats` gives the display format of numeric columns."""
    def heat_col(s):
        lo, hi = s.min(), s.max()
        span = (hi - lo) or 1
        return [f"background-color: rgba({rgb[0]},{rgb[1]},{rgb[2]},{0.03 + 0.42 * (v - lo) / span:.2f})"
                if pd.notna(v) else "" for v in s]

    styler = df.style.format(formats, na_rep="-")
    if heat:
        styler = styler.apply(heat_col, subset=heat)
    if tag:
        styler = styler.map(lambda v: f"{P.RISK_TAG.get(v, '')};font-weight:600", subset=[tag])
    return styler


def alert_box(level: str, text: str):
    label, color = P.ALERT_STYLE[level]
    st.markdown(
        f'<div class="ui-alert"><span class="tag"><span class="dot" style="background:{color};'
        f'color:{color}"></span>{label}</span><span class="msg">{text}</span></div>',
        unsafe_allow_html=True)


def callout(label: str, text: str, color: str | None = None):
    """A note in the alert style with its own label, e.g. how far to trust a list."""
    color = color or P.BLUE
    st.markdown(
        f'<div class="ui-alert"><span class="tag"><span class="dot" style="background:{color};'
        f'color:{color}"></span>{label}</span><span class="msg">{text}</span></div>',
        unsafe_allow_html=True)


def export_buttons(df: pd.DataFrame, name: str, key: str):
    """Download the table on screen as CSV (opens in Excel with the right letters) or .xlsx."""
    book = io.BytesIO()
    df.to_excel(book, index=False, sheet_name="Ma'lumot")
    left, right, _ = st.columns([1, 1, 3])
    left.download_button("CSV yuklab olish", df.to_csv(index=False).encode("utf-8-sig"), f"{name}.csv",
                         "text/csv", icon=":material/download:", key=f"{key}_csv", width="stretch")
    right.download_button("Excel yuklab olish", book.getvalue(), f"{name}.xlsx",
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                          icon=":material/table_view:", key=f"{key}_xlsx", width="stretch")


def synthetic_note():
    st.markdown('<div class="ui-note">Ma\'lumotlar sintetik (sun\'iy yaratilgan) - haqiqiy universitet '
                'ma\'lumoti emas. Bashoratlar ehtimollik bo\'lib, kafolat emas.</div>',
                unsafe_allow_html=True)
