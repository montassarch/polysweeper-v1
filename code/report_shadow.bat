@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PY=python
where py >nul 2>nul && set PY=py -3
%PY% -m polysweeper.shadow_report
pause
