# 📦 Guia de Compilação para Executável (.exe)

## 🎯 Objetivo
Gerar um pacote executável distribuível que inclui todas as dependências e templates num único executável ou pasta isolada.

---

## 📋 Pré-requisitos

1. **Python 3.8+** instalado e adicionado ao PATH
2. **pip** (geralmente vem com Python)
3. **PyInstaller** (será instalado automaticamente pelo script)

### Verificar instalação:
```bash
python --version
pip --version
```

---

## 🚀 Método Rápido (Recomendado)

### Windows:
Clique 2x no ficheiro **`BUILD.bat`** na pasta do projeto.

O script irá:
1. ✅ Verificar Python e PyInstaller
2. ✅ Instalar dependências do `requirements.txt`
3. ✅ Limpar compilações anteriores
4. ✅ Compilar o aplicativo com PyInstaller
5. ✅ Indicar a localização do executável

---

## 🔧 Método Manual

Se preferir controlar o processo manualmente:

### 1. Instalar PyInstaller
```bash
pip install pyinstaller
```

### 2. Instalar dependências
```bash
pip install -r requirements.txt
```

### 3. Compilar (3 opções)

#### Opção A: Usar o ficheiro .spec (RECOMENDADO)
```bash
pyinstaller app.spec
```

#### Opção B: Comando direto com --onedir
```bash
pyinstaller app.py \
    --onedir \
    --windowed \
    --add-data "templates:templates" \
    --name app
```

#### Opção C: Comando direto com --onefile (ficheiro único)
```bash
pyinstaller app.py \
    --onefile \
    --windowed \
    --add-data "templates:templates" \
    --name app
```

---

## 📁 Estrutura de Saída

### Com `--onedir` (recomendado para distribuição)
```
dist/
└── app/
    ├── app.exe
    ├── templates/
    │   └── index.html
    ├── _internal/
    │   ├── flask.so
    │   ├── pandas.so
    │   ├── pywin32.so
    │   └── [mais dependências...]
    └── [outros ficheiros]
```

### Com `--onefile` (executável único, mas mais lento)
```
dist/
└── app.exe  (contém tudo embedado)
```

---

## 📦 Distribuição

### Opção 1: Copiar pasta (mais rápido)
```
1. Copie a pasta dist/app para as máquinas dos utilizadores
2. Execute app.exe dentro da pasta
```

### Opção 2: Comprimir em .zip
```
1. Comprima dist/app em dist/app.zip
2. Distribua o .zip para os utilizadores
3. Utilizadores extraem e executam app.exe
```

### Opção 3: Criar instalador (avançado)
Use ferramentas como **NSIS** ou **Inno Setup** para criar um instalador .exe profissional.

---

## ⚙️ Parâmetros Explicados

| Parâmetro | Descrição |
|-----------|-----------|
| `--onedir` | Cria uma pasta com exe + dependências separadas (mais rápido, distribuição simples) |
| `--onefile` | Cria um único .exe com tudo embedado (mais lento ao iniciar, distribuição simples) |
| `--windowed` | Oculta a janela do prompt de comando |
| `--add-data "templates:templates"` | Inclui a pasta templates no executável |
| `--console` | Mostra a janela do prompt (padrão) |
| `--icon icon.ico` | Adiciona um ícone personalizado ao exe |

---

## 🐛 Resolução de Problemas

### Erro: "Python não encontrado"
**Solução:** Instale Python de https://python.org e certifique-se de selecionar "Add Python to PATH" durante a instalação.

### Erro: "ModuleNotFoundError"
**Solução:** Execute:
```bash
pip install -r requirements.txt
```

### Erro: "templates not found"
**Solução:** Certifique-se de que a pasta `templates/` existe e contém `index.html`.

### Executável muito lento ao iniciar
**Solução:** Use `--onedir` em vez de `--onefile`. PyInstaller com `--onefile` descompacta tudo em memória a cada inicialização.

### Erro ao conectar ao SAP GUI
**Solução:** Certifique-se de que:
1. SAP Logon está aberto
2. Tem sessão ativa no SAP
3. Tem permissões para usar a API do SAP Scripting

---

## ✅ Critérios de Aceitação Atingidos

- ✅ Comando do PyInstaller embutir com sucesso a pasta templates
- ✅ Aplicativo correr numa pasta isolada (`--onedir`)
- ✅ Janela de prompt ocultada por padrão (`--windowed`)
- ✅ Todas as dependências incluídas automaticamente
- ✅ Distribuição simples (copiar pasta ou extrair .zip)

---

## 📚 Referências

- [PyInstaller Docs](https://pyinstaller.org/)
- [Python Documentation](https://docs.python.org/)
- [Flask Deployment](https://flask.palletsprojects.com/deployment/)

---

**Autor:** Sistema de Compilação  
**Data:** 2026  
**Versão:** 1.0
