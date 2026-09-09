@echo off
REM Instalador do VOXEL FC para Windows usando so' cmd.exe puro,
REM sem chamar PowerShell em nenhum momento. Para maquinas antigas ou com
REM politica de execucao de scripts PowerShell restrita/bloqueada.
setlocal enabledelayedexpansion

set "REPO_DIR=%~dp0.."
cd /d "%REPO_DIR%"

echo == VOXEL FC: instalacao (Windows, cmd puro) ==

REM --- 1. Verificar Python ---
where python >nul 2>&1
if errorlevel 1 (
    echo Python nao encontrado no PATH.
    echo Instale com: winget install Python.Python.3.12
    echo Depois, em Configuracoes ^> Aplicativos ^> Configuracoes avancadas do
    echo aplicativo ^> Aliases de execucao do aplicativo, desligue python.exe
    echo e python3.exe caso o Windows abra a Microsoft Store em vez do Python.
    goto :fail
)

REM --- 2. Verificar FFmpeg ---
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo FFmpeg nao encontrado no PATH.
    echo Instale com: winget install Gyan.FFmpeg
    goto :fail
)

REM --- 3. Criar venv ---
if not exist ".venv\Scripts\activate.bat" (
    echo Criando ambiente virtual em .venv ...
    python -m venv .venv
    if errorlevel 1 goto :fail
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip -q

REM --- 4. Detectar GPU NVIDIA (CUDA) ---
set "EXTRAS=dropbox,transcribe,diarize"
where nvidia-smi >nul 2>&1
if errorlevel 1 (
    echo Nenhuma GPU NVIDIA detectada: instalando torch/torchaudio CPU-only.
    pip install -q --index-url https://download.pytorch.org/whl/cpu torch torchaudio
) else (
    nvidia-smi >nul 2>&1
    if errorlevel 1 (
        echo Nenhuma GPU NVIDIA detectada: instalando torch/torchaudio CPU-only.
        pip install -q --index-url https://download.pytorch.org/whl/cpu torch torchaudio
    ) else (
        echo GPU NVIDIA detectada: instalando com suporte a CUDA.
        set "EXTRAS=%EXTRAS%,cuda"
    )
)

echo Instalando o pacote (extras: %EXTRAS%) ...
pip install -q -e ".[%EXTRAS%]"
if errorlevel 1 goto :fail

REM --- 5. Criar .env a partir do exemplo, se necessario ---
if not exist ".env" (
    copy /y ".env.example" ".env" >nul
    echo Arquivo .env criado a partir de .env.example. Preencha DROPBOX_APP_KEY, DROPBOX_APP_SECRET, DROPBOX_REFRESH_TOKEN e HF_TOKEN.
)

echo.
echo Instalacao concluida nesta maquina.
echo Modelos e cache ficarao em: %USERPROFILE%\.voxelfc\models
echo Para usar:
echo   .venv\Scripts\activate.bat
echo   voxelfc --source C:\caminho\audio.mp3 --local
pause
exit /b 0

:fail
echo.
echo A instalacao falhou. Veja as mensagens acima.
pause
exit /b 1
