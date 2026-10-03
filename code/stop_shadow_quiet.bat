@echo off
rem Used by setup: stops a shadow window started the old way, then gives it time to exit.
cd /d "%~dp0"
if not exist data\shadow mkdir data\shadow
echo stop> data\shadow\STOP
timeout /t 20 /nobreak >nul
if exist data\shadow\STOP del data\shadow\STOP
