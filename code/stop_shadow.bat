@echo off
cd /d "%~dp0"
if not exist data\shadow mkdir data\shadow
echo stop> data\shadow\STOP
echo Stop file created. Shadow mode will stop within about 15 seconds.
pause
