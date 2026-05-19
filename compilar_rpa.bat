@echo off
echo =======================================================
echo     Compilador do RPA Expedicao (Auto-Update Version)
echo =======================================================
echo.

echo [1] Verificando dependencias...
pip install pyinstaller > NUL
if errorlevel 1 (
    echo Erro ao instalar pyinstaller. Verifique sua instalacao do Python.
    pause
    exit /b
)

echo [2] Removendo builds antigos (limpando cache)...
if exist build rmdir /s /q build
if exist dist\RPA_Expedicao.exe del /q dist\RPA_Expedicao.exe

echo [3] Iniciando compilacao (isso pode demorar 1-2 minutos)...
:: Comando PyInstaller
:: --onefile: Cria um unico .exe
:: --windowed: Oculta o terminal preto
:: --name: Nome do arquivo final
:: --add-data: Inclui arquivos e pastas no executavel (formato Origem;Destino)
pyinstaller --onefile --windowed --name "RPA_Expedicao" --add-data "templates;templates" --add-data "version.txt;." app.py

if errorlevel 1 (
    echo.
    echo ❌ ERRO DURANTE A COMPILACAO! Verifique as mensagens acima.
    pause
    exit /b
)

echo.
echo =======================================================
echo ✅ SUCESSO! O executavel foi criado.
echo Onde encontrar: dist\RPA_Expedicao.exe
echo =======================================================
echo.
echo PROXIMOS PASSOS:
echo 1. Teste o executavel gerado na pasta 'dist'
echo 2. Suba o 'dist\RPA_Expedicao.exe' para o repositorio GitHub (branch main)
echo 3. Suba tambem o 'version.txt' para o GitHub
echo.
pause
