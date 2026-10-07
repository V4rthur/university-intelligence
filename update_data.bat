@echo off
rem Load new or changed files from 01_Data\raw and re-score students.
rem Works from any folder. Extra options are passed through, for example:
rem   update_data.bat --new-semester
rem   update_data.bat --retrain
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" run_pipeline.py %*
pause
