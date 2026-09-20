@echo off
title Stop J.A.R.V.I.S. Background Service
cd /d "%~dp0"
echo Stopping J.A.R.V.I.S. Background Service...
powershell -Command "Get-Process python*, pythonw* | Where-Object { $_.CommandLine -like '*jarvis*' } | Stop-Process -Force -ErrorAction SilentlyContinue"
echo [OK] J.A.R.V.I.S. Background Service Stopped.
pause
