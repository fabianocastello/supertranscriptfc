@echo off
REM Atualiza o codigo (git pull) e ja roda o voxelfc com os
REM argumentos passados, para nao esquecer de atualizar antes de cada uso.
REM
REM Uso: scripts\update.bat --source C:\caminho\ou\pasta --model-size large-v3 --language pt
setlocal

set "REPO_DIR=%~dp0.."
cd /d "%REPO_DIR%"

echo == Atualizando codigo (git pull) ==
git pull
if errorlevel 1 goto :fail

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)

echo == Rodando: voxelfc %* ==
voxelfc %*
exit /b %ERRORLEVEL%

:fail
echo.
echo Falha ao atualizar o codigo (git pull). Veja as mensagens acima.
exit /b 1
