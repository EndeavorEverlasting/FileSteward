@echo off
setlocal
set "FS_SHORTCUT_INSTALLER=%~dp0scripts\windows\Install-FileSteward-Shortcut.ps1"
if not exist "%FS_SHORTCUT_INSTALLER%" (
  echo FileSteward shortcut installer is missing from this checkout.
  pause
  exit /b 1
)
powershell.exe -NoLogo -NoProfile -File "%FS_SHORTCUT_INSTALLER%"
if errorlevel 1 (
  echo FileSteward shortcut installation was not completed. Read the error above.
  echo Your existing files and shortcuts were preserved.
  pause
  exit /b 1
)
exit /b 0
