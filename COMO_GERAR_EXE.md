# Como Gerar o .exe (Windows)

## Instruções Rápidas

### Pré-requisitos
- Windows com Python 3.8+ instalado
- Python adicionado ao PATH

### Método 1: BUILD.bat (Recomendado)
```batch
# No Windows, duplo clique em:
BUILD.bat
```
- Gera: `dist/app/app.exe` (pasta com exe + dependências)
- Mais rápido ao iniciar
- Fácil de distribuir (copiar pasta)

### Método 2: compilar_rpa.bat (Arquivo Único)
```batch
# No Windows, duplo clique em:
compilar_rpa.bat
```
- Gera: `dist/RPA_Expedicao.exe` (arquivo único)
- Mais lento ao iniciar
- Fácil de distribuir (apenas um arquivo)

### Método 3: Manual
```batch
pip install pyinstaller
pip install -r requirements.txt
pyinstaller app.spec
```

## Onde Encontrar o .exe
- **BUILD.bat**: `dist/app/app.exe`
- **compilar_rpa.bat**: `dist/RPA_Expedicao.exe`

## Distribuir
1. Copie a pasta `dist/app` ou o arquivo `dist/RPA_Expedicao.exe`
2. Ou comprima em .zip para enviar aos usuários
