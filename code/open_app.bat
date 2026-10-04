@echo off
title PolySweeper app
cd /d "%~dp0.."
echo Getting the PolySweeper app from GitHub...
git fetch origin +refs/heads/app-build:refs/remotes/origin/app-build
if not exist app\bin mkdir app\bin
git show origin/app-build:PolySweeper.exe > app\bin\PolySweeper.download
if errorlevel 1 (
  echo Could not download the app. Send Claude a screenshot of this window.
  pause
  exit /b 1
)
move /y app\bin\PolySweeper.download app\bin\PolySweeper.exe >nul
powershell -NoProfile -Command "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'PolySweeper.lnk')); $s.TargetPath='%CD%\app\bin\PolySweeper.exe'; $s.WorkingDirectory='%CD%\app\bin'; $s.Save()"
echo Opening PolySweeper...
start "" "app\bin\PolySweeper.exe"
