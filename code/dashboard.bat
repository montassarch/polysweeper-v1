@echo off
cd /d "%~dp0"
set PY=python
where py >nul 2>nul && set PY=py -3
%PY% -m polysweeper.dashboard
if errorlevel 1 (echo Something went wrong. Send me this window. & pause & exit /b 1)
start "" "%~dp0dashboard.html"
