@echo off
rem Launch the local "should I install this skill?" web app.
rem Double-click this file, or run:  web.bat
rem It scans your local Claude Code usage + environment, starts a local
rem server, and opens the page in your browser. Press Ctrl+C to stop.
setlocal
set "PYTHONUTF8=1"
set "PROJDIR=%~dp0"
set "PYTHONPATH=%PROJDIR%src"
"%PROJDIR%.venv-score\Scripts\python.exe" -m skills_vote.score --web %*
endlocal
