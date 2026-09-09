@echo off
REM Updates the code (git pull) and runs voxelfc with the given
REM arguments, so it's never forgotten before each use.
REM
REM Usage: scripts\update.bat --source C:\path\or\folder --model-size large-v3 --language pt
setlocal

set "REPO_DIR=%~dp0.."
cd /d "%REPO_DIR%"

echo == Updating code (git pull) ==
git pull
if errorlevel 1 goto :fail

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)

REM The pull may change pyproject.toml, the package name, or the entry
REM points. Reinstalling the package updates voxelfc.exe and the legacy alias.
echo == Installing the updated code into the virtual environment ==
python -m pip install -q -e .
if errorlevel 1 goto :fail

where voxelfc >nul 2>&1
if errorlevel 1 (
    echo voxelfc executable not found after installation.
    goto :fail
)

echo == Running: voxelfc %* ==
voxelfc %*
exit /b %ERRORLEVEL%

:fail
echo.
echo Failed to update the code (git pull). See the messages above.
exit /b 1
