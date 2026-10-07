@echo off
rem University Intelligence dashboard - opens at http://localhost:8610
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" -m streamlit run 08_Dashboard\app.py
pause
