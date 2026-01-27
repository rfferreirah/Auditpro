@echo off
title Audit PRO - Agente de Qualidade de Dados REDCap
echo.
echo ============================================================
echo   Audit PRO - Agente de Qualidade de Dados do REDCap
echo ============================================================
echo.
echo Iniciando servidor web...
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5003/register"
echo Acesse: http://localhost:5003

python web_app.py

pause
