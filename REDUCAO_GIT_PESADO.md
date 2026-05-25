# 📦 Solução: Repositório Git muito pesado

## ❌ Problema
Seu repositório `.git` está com **~2 GB**, o que dificulta compartilhamento e sincronização com OneDrive.

## ✅ Soluções Aplicadas

### 1. `.gitignore` Criado
Um arquivo `.gitignore` foi criado com as principais regras para evitar:
- ✓ Arquivos `.exe`, `.dll`, `.spec` (compilados)
- ✓ Diretórios `dist/`, `build/`, `__pycache__/`
- ✓ Ambientes virtuais (`venv/`, `env/`)
- ✓ Arquivos de credenciais (`.env`, `secrets.*`)
- ✓ Logs, temporários e cache
- ✓ Arquivos de banco de dados

### 2. Causas Prováveis do Peso
O repositório está pesado provavelmente porque:
- Arquivos `.exe` / `.spec` foram commitados (não devem ser!)
- Arquivos de banco de dados ou logs no histórico
- `__pycache__` ou `dist/` foram versionados
- Muitos commits com arquivos bináros

### 3. Próximas Ações Recomendadas

#### Opção A: Solução Rápida (Se o histórico não é crítico)
```powershell
# 1. Mude o repositório para fora do OneDrive
# Exemplo: C:\Dev\rpa_Expedicao (não sincronize)

# 2. Depois faça:
cd "C:\Dev\rpa_Expedicao"
git reflog expire --expire=now --all
git gc --aggressive --prune=now
```

#### Opção B: Limpar Histórico de Arquivos Grandes
Se quer remover arquivos grandes do histórico:
```powershell
# Instale git-filter-repo (mais seguro que filter-branch)
pip install git-filter-repo

# Remova todos os .exe, .spec, etc do histórico
git filter-repo --path .exe --invert-paths
git filter-repo --path .spec --invert-paths
git filter-repo --path dist/ --invert-paths
```

#### Opção C: Começar do Zero (Recomendado)
```powershell
# 1. Crie um novo repositório limpo
mkdir "C:\Dev\rpa_Expedicao_clean"
cd "C:\Dev\rpa_Expedicao_clean"
git init

# 2. Copie APENAS os arquivos necessários do repositório antigo
# Ignore: .git, dist/, build/, __pycache__, *.exe, etc

# 3. Faça commit limpo
git add .
git commit -m "Initial clean commit"
```

## 🔧 Melhorias de Longo Prazo

### 1. Configure `.gitattributes` para LFS (se precisar versiontar binários)
```
*.exe filter=lfs diff=lfs merge=lfs -text
*.dll filter=lfs diff=lfs merge=lfs -text
*.db filter=lfs diff=lfs merge=lfs -text
```

### 2. Aliases Úteis
```powershell
git config --global alias.size "!git rev-list --all --objects | sed -n $(git rev-list --objects --all | cut -f1 -d' ' | git cat-file --batch-check | grep blob | sort -k3 -n | tail -10 | while read hash type size; do echo -n \"-e s/$hash/$size/p \"; done) | sort -k2 -n -r | head -20"
```

### 3. Rotina de Manutenção Mensal
```powershell
# Executar a cada mês
git reflog expire --expire=1.month.ago --all
git gc --aggressive --prune=1.month.ago
```

## 📋 Checklist

- [ ] `.gitignore` está configurado corretamente
- [ ] Remova o repositório do OneDrive (mude para C:\Dev)
- [ ] Execute `git gc --aggressive` em um local SEM sincronização
- [ ] Teste compartilhamento do repositório limpo
- [ ] Documente os passos no time

## 🎯 Recomendação Final

**Mude o repositório para fora do OneDrive** - Isso resolve:
1. Problemas de sincronização
2. Problemas de permissão no Git
3. Melhor performance
4. Melhor segurança (credenciais não sincronizadas)

Depois aplique o `git gc --aggressive` normalmente.
