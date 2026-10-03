@echo off
cd /d "%~dp0"
echo Setting up the PolySweeper autopilot...
echo.
where git >nul 2>nul || (echo Git was not found. Install "Git for Windows" from git-scm.com, then run this again. & pause & exit /b 1)
set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
(
  echo @echo off
  echo start "PolySweeper autopilot" /min "%~dp0autopilot.bat"
) > "%STARTUP%\PolySweeper-autopilot.bat"
echo [1/3] Autopilot will start by itself every time you log in to Windows.
powercfg /change standby-timeout-ac 0 >nul 2>nul
powercfg /change hibernate-timeout-ac 0 >nul 2>nul
echo [2/3] Sleep and hibernate set to "Never" while plugged in.
echo [3/3] Starting the autopilot now (a minimised window called "PolySweeper autopilot").
call stop_shadow_quiet.bat
start "PolySweeper autopilot" /min "%~dp0autopilot.bat"
echo.
echo Done. Keep the PC plugged in. To turn it off later: remove_autopilot.bat
pause
