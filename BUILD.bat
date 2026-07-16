@echo off
REM Script de compilação do aplicativo RPA para .exe
REM Requisitos: Python 3.8+ e PyInstaller instalados

REM Ativar ambiente virtual se existir
if not exist .venv\Scripts\activate.bat goto skip_venv
echo [INFO] Ativando ambiente virtual (.venv)...
call .venv\Scripts\activate.bat
:skip_venv

chcp 65001 > nul
cls

echo ========================================
echo   COMPILADOR RPA - PyInstaller
echo ========================================
echo.

REM Verifica se o Python está instalado
python --version > nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ❌ ERRO: Python não foi encontrado!
    echo Certifique-se de que o Python está instalado e adicionado ao PATH.
    pause
    exit /b 1
)

echo ✅ Python encontrado!
echo.

REM Verifica se o PyInstaller está instalado
pip show pyinstaller > nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ⚠️ PyInstaller não encontrado. Instalando...
    pip install pyinstaller --quiet
    if %ERRORLEVEL% neq 0 (
        echo ❌ ERRO: Falha ao instalar PyInstaller!
        pause
        exit /b 1
    )
    echo ✅ PyInstaller instalado com sucesso!
    echo.
)

REM Verifica e instala as dependências do requirements.txt
echo 🔧 Verificando e instalando dependências...
pip install -r requirements.txt --quiet
if %ERRORLEVEL% neq 0 (
    echo ❌ ERRO: Falha ao instalar dependências!
    pause
    exit /b 1
)
echo ✅ Dependências instaladas com sucesso!
echo.

REM Instala o greenlet (dependência do Playwright)
echo 🔧 Instalando greenlet (dependência do Playwright)...
pip install greenlet --quiet

REM Garante que o browser Chromium está instalado (necessário para Playwright)
echo 🌐 Verificando browser Chromium do Playwright...
python -m playwright install chromium
if %ERRORLEVEL% neq 0 (
    echo ⚠️ Aviso: Falha ao instalar Chromium - a função de Packlist instalará automaticamente no primeiro uso.
) else (
    echo ✅ Chromium verificado!
)
echo.


REM Limpa compilações anteriores
echo 🧹 Limpando compilações anteriores...
if exist build rmdir /s /q build > nul 2>&1
if exist dist rmdir /s /q dist > nul 2>&1
if exist app.spec del /f /q app.spec > nul 2>&1

REM Compila o aplicativo usando o arquivo .spec
echo.
echo 🚀 Compilando aplicativo...
echo ----------------------------------------
REM Criar o diretório temporário (sem espaços) para evitar erro de DLL
if not exist C:\Temp mkdir C:\Temp
python -m PyInstaller app.spec

if %ERRORLEVEL% neq 0 (
    echo.
    echo ❌ ERRO: Falha na compilação!
    pause
    exit /b 1
)

echo.
echo ========================================
echo ✅ COMPILAÇÃO CONCLUÍDA COM SUCESSO!
echo ========================================
echo.
echo 📦 O executável foi gerado em:
echo    dist\app\
echo.
echo 📋 Estrutura:
echo    dist\app\app.exe
echo    dist\app\templates\
echo    dist\app\[dependências]
echo.
echo 🎁 Para distribuir:
echo    1. Copie a pasta 'dist\app' para as máquinas dos utilizadores
echo    2. Execute o app.exe dentro da pasta
echo    3. Ou comprima 'dist\app' em .zip para distribuição
echo.
pause
