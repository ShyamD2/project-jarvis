@echo off
title J.A.R.V.I.S. Auto-Start Installer
cd /d "%~dp0"
echo ======================================================================
echo       CONFIGURING J.A.R.V.I.S. WAKE-WORD TO START BY DEFAULT
echo ======================================================================
echo.
python services/gateway/setup_autostart.py
echo.
pause
