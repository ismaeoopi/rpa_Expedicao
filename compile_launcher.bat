@echo off
REM ============================================================================
REM Script de Compilação - RPA Auto-Update Launcher
REM ============================================================================
REM Este script compila o launcher.py em um executável (.exe) usando PyInstaller
REM Requisitos: PyInstaller instalado (pip install pyinstaller)
REM
REM Como usar:
REM   1. Abra o PowerShell ou CMD neste diretório
REM   2. Execute: compile_launcher.bat
REM   3. O .exe será criado em: dist\launcher.exe
REM ============================================================================

setlocal enabledelayedexpansion

echo.
echo ============================================================================
echo    COMPILADOR RPA - Auto-Update Launcher para Executável
echo ============================================================================
echo.

REM Verifica se PyInstaller está instalado
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [ERRO] PyInstaller não está instalado!
    echo.
    echo Para instalar, execute:
    echo   pip install pyinstaller
    echo.
    pause
    exit /b 1
)

echo [INFO] PyInstaller encontrado. Iniciando compilação...
echo.

REM Remove diretórios de build anteriores
if exist build rmdir /s /q build >nul 2>&1
if exist dist rmdir /s /q dist >nul 2>&1
if exist launcher.spec del /q launcher.spec >nul 2>&1

echo [ETAPA 1/3] Compilando launcher.py com PyInstaller...
echo.

REM Comando principal de compilação
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "RPA_Expedicao" ^
    --distpath ".\dist" ^
    --buildpath ".\build" ^
    --specpath "." ^
    --add-data "templates;templates" ^
    launcher.py

if errorlevel 1 (
    echo.
    echo [ERRO] Falha na compilação!
    echo Verifique se todos os arquivos estão presentes.
    echo.
    pause
    exit /b 1
)

echo.
echo [ETAPA 2/3] Limpando arquivos temporários...
if exist build rmdir /s /q build >nul 2>&1
if exist launcher.spec del /q launcher.spec >nul 2>&1
del /q __pycache__ >nul 2>&1

echo.
echo [ETAPA 3/3] Compilação finalizada com sucesso!
echo.
echo ============================================================================
echo    RESULTADO:
echo ============================================================================
echo.
echo Executável criado em: dist\RPA_Expedicao.exe
echo.
echo PRÓXIMOS PASSOS:
echo   1. Você pode copiar o arquivo .exe para qualquer lugar no seu PC
echo   2. Ao clicar no .exe, o sistema vai:
echo      - Executar "git pull" SILENCIOSAMENTE
echo      - Abrir a interface RPA normalmente
echo   3. Se não houver Git instalado, o app abre normalmente
echo.
echo NOTAS IMPORTANTES:
echo   - O repositório .git deve estar no mesmo diretório que o .exe
echo   - Se copiar o .exe, copie também o repositório Git
echo   - Ou execute o .exe sempre a partir do diretório do projeto
echo.
echo ============================================================================
echo.
pause
