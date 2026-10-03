@echo off
cd /d "%~dp0"
if exist data\shadow\STOP del data\shadow\STOP
set PY=python
where py >nul 2>nul && set PY=py -3
echo Shadow mode is running. It places NO orders. Leave this window open.
echo To stop: double-click stop_shadow.bat (or close this window).
%PY% -u -m polysweeper.shadow --leagues cs2 lol dota2 val r6siege ow mlbb hok codmw atp wta epl lal bun sea fl1 ucl uel por ere --forever
echo.
echo Shadow mode stopped.
pause
