@echo off
rem Share the running dashboard over the internet with a temporary public link.
rem 1. Start the dashboard first (start_dashboard.bat) and leave it running.
rem 2. Run this file. Copy the https://....trycloudflare.com address it prints and send it.
rem The link works while this window stays open and changes every time you run it.
rem Anyone with the link reaches the login page: share a login only with people you trust.
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://localhost:8610
pause
