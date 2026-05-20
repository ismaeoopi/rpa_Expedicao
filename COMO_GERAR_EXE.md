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

## Solução de Problemas

### Erro: "pyinstaller is not recognized"
Solução 1 (recomendada):
```batch
cd C:\caminho\para\rpa_Expedicao
python -m pip install pyinstaller
python -m PyInstaller app.spec
```

Solução 2 (usar caminho completo):
```batch
pip install pyinstaller
%LOCALAPPDATA%\Programs\Python\Python3x\Scripts\pyinstaller app.spec
```

Solução 3 (adicionar Scripts ao PATH):
1. Encontre onde Python está instalado (ex: `C:\Users\SeuNome\AppData\Local\Programs\Python\Python312`)
2. Adicione ao PATH: `C:\Users\SeuNome\AppData\Local\Programs\Python\Python312\Scripts`
3. Reinicie o terminal
4. Execute: `pyinstaller app.spec`

### Erro: "python is not recognized"
- Instale Python 3.8+ em https://python.org
- Durante a instalação, marque a opção "Add Python to PATH"

### Erro: "app not found"
Você precisa estar no diretório do projeto:
```batch
cd C:\caminho\onde\salvou\rpa_Expedicao
python -m PyInstaller app.spec
```
Ou simplesmente dê duplo clique no arquivo `BUILD.bat` ou `compilar_rpa.bat` dentro da pasta do projeto.

### Erro durante compilação
- Execute: `pip install -r requirements.txt`
- Verifique se todas as dependências foram instaladas corretamente
