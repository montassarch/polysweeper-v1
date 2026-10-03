@echo off
title PolySweeper autopilot
cd /d "%~dp0"
set PY=python
where py >nul 2>nul && set PY=py -3
echo PolySweeper AUTOPILOT: keeps shadow mode running and up to date. NO real orders.
echo Leave this window open (you can minimise it). To stop: double-click stop_shadow.bat.
:loop
%PY% -u -m polysweeper.autopilot
if %errorlevel%==3 goto loop
if %errorlevel%==1 pause
