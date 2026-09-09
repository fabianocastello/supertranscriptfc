@echo off
REM Atualiza o codigo sem precisar do git instalado: baixa o ZIP do branch
REM main direto do GitHub usando curl.exe e tar.exe (ambos ja vem embutidos
REM no Windows 10 1803+ / Windows 11), extrai e substitui os arquivos do
REM projeto, preservando .venv e .env. Depois roda o voxelfc com
REM os argumentos passados.
REM
REM Uso: scripts\update-nogit.bat --source C:\caminho\audio.mp3 --local --model-size large-v3
setlocal

set "REPO_DIR=%~dp0.."
cd /d "%REPO_DIR%"

where curl >nul 2>&1
if errorlevel 1 (
    echo curl.exe nao encontrado. Ele vem embutido no Windows 10 1803+/11;
    echo em versoes mais antigas, instale o Git for Windows e use update.bat.
    goto :fail
)
where tar >nul 2>&1
if errorlevel 1 (
    echo tar.exe nao encontrado. Ele vem embutido no Windows 10 1803+/11;
    echo em versoes mais antigas, instale o Git for Windows e use update.bat.
    goto :fail
)

set "ZIP_URL=https://github.com/fabianocastello/voxelfc/archive/refs/heads/main.zip"
set "TMP_ZIP=%TEMP%\voxelfc_update.zip"
set "TMP_EXTRACT=%TEMP%\voxelfc_update_extract"

echo == Baixando codigo mais recente ==
curl -L -o "%TMP_ZIP%" "%ZIP_URL%"
if errorlevel 1 goto :fail

if exist "%TMP_EXTRACT%" rmdir /s /q "%TMP_EXTRACT%"
mkdir "%TMP_EXTRACT%"
tar -xf "%TMP_ZIP%" -C "%TMP_EXTRACT%"
if errorlevel 1 goto :fail

REM O zip do GitHub extrai para uma subpasta tipo voxelfc-main
set "EXTRACTED_DIR="
for /d %%D in ("%TMP_EXTRACT%\*") do set "EXTRACTED_DIR=%%D"
if not defined EXTRACTED_DIR goto :fail

echo == Atualizando arquivos (preservando .venv e .env) ==
xcopy "%EXTRACTED_DIR%\src" "%REPO_DIR%\src" /e /y /i >nul
xcopy "%EXTRACTED_DIR%\scripts" "%REPO_DIR%\scripts" /e /y /i >nul
xcopy "%EXTRACTED_DIR%\tests" "%REPO_DIR%\tests" /e /y /i >nul
copy /y "%EXTRACTED_DIR%\pyproject.toml" "%REPO_DIR%\" >nul
copy /y "%EXTRACTED_DIR%\README.md" "%REPO_DIR%\" >nul
copy /y "%EXTRACTED_DIR%\quickInstall.md" "%REPO_DIR%\" >nul
copy /y "%EXTRACTED_DIR%\.env.example" "%REPO_DIR%\" >nul
copy /y "%EXTRACTED_DIR%\.gitignore" "%REPO_DIR%\" >nul

del /q "%TMP_ZIP%"
rmdir /s /q "%TMP_EXTRACT%"

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
    echo == Reinstalando dependencias (caso tenham mudado) ==
    pip install -q -e ".[dropbox,transcribe,diarize]" >nul 2>&1
)

echo == Rodando: voxelfc %* ==
voxelfc %*
exit /b %ERRORLEVEL%

:fail
echo.
echo Falha ao atualizar o codigo. Veja as mensagens acima.
exit /b 1
