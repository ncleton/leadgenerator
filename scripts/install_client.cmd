@echo off
setlocal
title Installation de Lead Generator

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_client.ps1"
set "INSTALL_EXIT_CODE=%ERRORLEVEL%"

if not "%INSTALL_EXIT_CODE%"=="0" (
  echo.
  echo L'installation a echoue. Le message ci-dessus indique l'etape concernee.
  echo Vous pouvez fermer Codex et relancer ce fichier sans perdre vos profils.
  pause
)

exit /b %INSTALL_EXIT_CODE%
