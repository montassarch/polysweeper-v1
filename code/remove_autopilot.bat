@echo off
cd /d "%~dp0"
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\PolySweeper-autopilot.bat" >nul 2>nul
if not exist data\shadow mkdir data\shadow
echo stop> data\shadow\STOP
echo Autopilot removed: it will no longer start at login, and the running one stops within about 15 seconds.
echo (Sleep settings were not changed back. Change them in Windows Settings - Power if you want.)
pause
