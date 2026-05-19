# 🚀 RPA Auto-Update - Guia de Implementação

## 📋 Resumo da Solução

O aplicativo RPA foi aprimorado com um sistema de **auto-atualização silenciosa via Git**. Quando você clica no executável, o sistema:

1. ✅ Executa `git pull` **silenciosamente** (sem mostrar o terminal preto)
2. ✅ Carrega as atualizações mais recentes do GitHub
3. ✅ Trata erros internamente (se não houver internet ou Git não estiver instalado)
4. ✅ Abre a interface RPA normalmente

---

## 🎯 Critérios de Aceitação - Status

| Requisito | Status | Implementação |
|-----------|--------|---------------|
| Auto-update ao clicar no .exe | ✅ | `launcher.py` + compilação PyInstaller |
| Git pull silencioso | ✅ | Flag `CREATE_NO_WINDOW` no subprocess |
| Terminal não fica visível | ✅ | Usando `--windowed` no PyInstaller |
| Tratamento de erros (sem Git/internet) | ✅ | Try-except com fallback seguro |
| Versão local abre normalmente em caso de erro | ✅ | Continua mesmo com falha de atualização |

---

## 📦 Arquivos Criados/Modificados

### 1. **app.py** (Modificado)
- Função `verificar_e_atualizar_via_git()` aprimorada
- Suporta modo silencioso
- Melhor tratamento de erros
- Timeout de 20 segundos para evitar travamentos

### 2. **launcher.py** (Novo)
- Ponto de entrada principal
- Executa git pull silenciosamente
- Trata erros internamente
- Pronto para compilação em .exe

### 3. **compile_launcher.bat** (Novo)
- Script para compilar o launcher em executável
- Uso: basta executar no CMD/PowerShell

---

## 🛠️ Como Compilar o Executável

### Pré-requisitos:
```bash
pip install pyinstaller
pip install -r requirements.txt  # seu requirements.txt
```

### Passo 1: Abra o PowerShell ou CMD
```
Windows+R -> digitar "cmd" -> Enter
```

### Passo 2: Navegue até a pasta do projeto
```bash
cd "c:\Users\ismael.nascimento\OneDrive - VALGROUP\Scripts\app"
```

### Passo 3: Execute o script de compilação
```bash
compile_launcher.bat
```

**Pronto!** O executável será criado em: `dist\RPA_Expedicao.exe`

---

### ✋ Compilação Manual (Alternativa)

Se o script .bat não funcionar, execute este comando manualmente:

```bash
pyinstaller --onefile --windowed --name "RPA_Expedicao" --add-data "templates;templates" launcher.py
```

---

## 📍 Onde Usar o Executável

### ✅ Recomendado:
Executar o .exe **no mesmo diretório do repositório Git**:
```
C:\Users\ismael.nascimento\OneDrive - VALGROUP\Scripts\app\
├── .git/                          ← Repositório Git
├── templates/
├── app.py
├── launcher.py
├── RPA_Expedicao.exe              ← Executável
```

### ⚠️ Se Copiar o .exe para Outro Local:
Você **DEVE** copiar também a pasta `.git`:
```
C:\Users\MeuPC\Desktop\
├── .git/                          ← Copie isto também!
├── templates/
├── app.py
├── RPA_Expedicao.exe
```

---

## 🔄 Como Funciona o Auto-Update

```
Clique no RPA_Expedicao.exe
         ↓
launcher.py inicia (sem janela visível)
         ↓
Tenta executar: git pull
         ↓
    ├─ ✅ Sucesso
    │   ├─ Código atualizado
    │   └─ App inicia
    │
    ├─ ⚠️ Sem Internet
    │   └─ App inicia mesmo assim (versão local)
    │
    └─ ⚠️ Git não instalado
        └─ App inicia mesmo assim (versão local)
```

---

## 🧪 Teste a Solução

### Teste 1: Verificar Auto-Update
```bash
# No seu repositório Git
git log --oneline -n 5     # Veja os commits atuais

# Faça uma mudança e faça commit (ou use outro branch)
git commit --allow-empty -m "Teste de auto-update"

# Agora execute o .exe - deve fazer git pull automaticamente
```

### Teste 2: Verificar Modo Silencioso
```bash
# Ao clicar no .exe, não deve aparecer nenhuma janela preta/terminal
# Deve abrir direto a interface RPA
```

### Teste 3: Desligar Internet e Testar
```bash
# Desconecte a internet
# Execute o .exe novamente
# Deve abrir normalmente com a versão local
```

---

## ⚙️ Configuração Avançada

### Alterar Timeout de Git Pull
Se o seu repositório é muito grande e demora para fazer pull, altere em `app.py`:

```python
resultado = subprocess.run(
    ["git", "pull"],
    capture_output=True,
    text=True,
    timeout=30,  # ← Altere para 30, 60, etc segundos
    ...
)
```

### Adicionar Mais Arquivos ao Executável
Se tiver assets (imagens, ícones, etc), adicione em `compile_launcher.bat`:

```batch
--add-data "templates;templates" ^
--add-data "assets;assets" ^     ← Adicione isto
--add-data "icons;icons" ^       ← E isto
```

---

## 📊 Fluxo de Atualização Detalhado

1. **Usuário clica no RPA_Expedicao.exe**
   - Não vê nenhuma janela (--windowed)

2. **launcher.py verifica .git**
   - Se não existir → Continua normalmente

3. **launcher.py executa: git pull**
   - Subprocess com CREATE_NO_WINDOW (Windows)
   - Timeout de 20 segundos
   - Captura output (não mostra no terminal)

4. **Resultado do git pull**
   - Sucesso: "Already up to date" ou código atualizado
   - Erro: Continua de qualquer forma

5. **launcher.py executa app.py**
   - Interface RPA abre normalmente
   - app.py mostra os logs internos

---

## 🐛 Troubleshooting

### ❌ "Git não é reconhecido como comando interno"
- Git não está instalado ou não está no PATH
- Instale Git from git-scm.com
- Reinicie o PC após instalar

### ❌ "ModuleNotFoundError: No module named 'X'"
- Faltam dependências ao compilar
- Solução:
  ```bash
  pip install -r requirements.txt
  # Depois recompile o .exe
  ```

### ❌ "launcher.py não encontrado"
- Certifique-se que launcher.py está no mesmo diretório que app.py
- Verifique se digitou o nome correto

### ❌ "O app trava ao abrir"
- Pode ser timeout do git pull muito curto
- Aumente para 30-60 segundos em app.py

### ❌ "Erro de permissão ao fazer git pull"
- Verifique se a pasta .git tem permissões de leitura/escrita
- Ou execute como Administrador

---

## 📝 Próximas Atualizações (Recomendadas)

Depois de compilar, você pode:

1. **Distribuir o .exe** para a equipa
2. **Criar um atalho no Desktop** com ícone personalizado
3. **Usar Task Scheduler** para rodar diariamente (opcional)

---

## ✅ Checklist Final

- [ ] PyInstaller instalado (`pip install pyinstaller`)
- [ ] Executou `compile_launcher.bat` ou comando manual
- [ ] Arquivo `dist/RPA_Expedicao.exe` foi criado
- [ ] Testou clicar no .exe
- [ ] Verificou que não aparece terminal preto
- [ ] Interface RPA abriu normalmente
- [ ] Testou com internet desligada

---

## 📞 Suporte

Se encontrar problemas:
1. Verifique o arquivo de log em: `c:\logs\rpa_debug.log` (se existir)
2. Execute manualmente: `python launcher.py` para ver erros no console
3. Verifique se Git está instalado: `git --version`

---

**Versão:** 1.0  
**Data:** Maio 2026  
**Autor:** GitHub Copilot RPA  
