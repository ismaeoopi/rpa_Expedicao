@echo off
REM ============================================================================
REM Script para Criar Atalho do RPA no Desktop
REM ============================================================================
REM Este script cria um atalho do RPA_Expedicao.exe no seu Desktop
REM
REM Como usar:
REM   1. Abra CMD neste diretório
REM   2. Execute: create_shortcut.bat
REM   3. Um atalho aparecerá no Desktop
REM ============================================================================

setlocal enabledelayedexpansion

echo.
echo ============================================================================
echo    CRIADOR DE ATALHO - RPA Expedicao
echo ============================================================================
echo.

REM Verifica se o .exe foi compilado
if not exist "dist\RPA_Expedicao.exe" (
    echo [ERRO] dist\RPA_Expedicao.exe não encontrado!
    echo.
    echo Você precisa compilar primeiro:
    echo   compile_launcher.bat
    echo.
    pause
    exit /b 1
)

echo [INFO] Criando atalho no Desktop...
echo.

REM Localiza o Desktop
for /f "tokens=3" %%A in ('reg query "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders" /v "Desktop" ^| findstr Desktop') do set DESKTOP=%%A

if not defined DESKTOP (
    echo [ERRO] Não foi possível localizar o Desktop!
    pause
    exit /b 1
)

REM Caminho absoluto do .exe
set EXE_PATH=%cd%\dist\RPA_Expedicao.exe

REM Cria o arquivo .lnk usando PowerShell
powershell -Command ^
    "$shell = New-Object -ComObject WScript.Shell; " ^
    "$shortcut = $shell.CreateShortcut('%DESKTOP%\RPA Expedicao.lnk'); " ^
    "$shortcut.TargetPath = '%EXE_PATH%'; " ^
    "$shortcut.WorkingDirectory = '%cd%'; " ^
    "$shortcut.IconLocation = '%EXE_PATH%'; " ^
    "$shortcut.Save()" >nul 2>&1

if errorlevel 1 (
    echo [ERRO] Falha ao criar o atalho!
    pause
    exit /b 1
)

echo [SUCESSO] Atalho criado no Desktop!
echo.
echo Atalho: RPA Expedicao.lnk
echo Local: %DESKTOP%
echo.
echo Você agora pode clicar no atalho para abrir o RPA com auto-update!
echo.
pause
