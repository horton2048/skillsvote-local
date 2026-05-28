@echo off
rem One-click launcher for personalized skill scoring.
rem Usage examples:
rem   score.bat                         scores your installed skills, top 20
rem   score.bat --top-k 10              top 10
rem   score.bat --skills-dir "%USERPROFILE%\.claude\plugins"
rem   score.bat --rank browse wechat-mp-article ai-proofreading
rem   score.bat --json
setlocal
set "PYTHONUTF8=1"
set "PROJDIR=%~dp0"
set "PYTHONPATH=%PROJDIR%packaging"
"%PROJDIR%.venv-score\Scripts\python.exe" -m skillsvote --skills-dir "%USERPROFILE%\.claude\skills" --exclude pers-* seed-* %*
endlocal
