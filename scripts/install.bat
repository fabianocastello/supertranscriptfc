@echo off
REM Instalador do VOXEL FC para Windows (ex: ps20).
REM So' um wrapper fino que chama install.ps1 via PowerShell contornando a
REM politica de execucao padrao (que costuma bloquear scripts .ps1), para
REM quem preferir dar duplo-clique em vez de abrir o PowerShell manualmente.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo A instalacao falhou. Veja as mensagens acima.
    pause
    exit /b %ERRORLEVEL%
)

pause
