@echo off
REM VOXEL FC installer for Windows (e.g. ps20).
REM This is just a thin wrapper that calls install.ps1 via PowerShell,
REM bypassing the default execution policy (which usually blocks .ps1
REM scripts), for anyone who'd rather double-click than open PowerShell
REM manually.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Installation failed. See the messages above.
    pause
    exit /b %ERRORLEVEL%
)

pause
