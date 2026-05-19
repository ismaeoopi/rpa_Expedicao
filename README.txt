╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║                      RPA AUTO-UPDATE - INSTRUÇÕES                         ║
║                                                                            ║
║  Seu aplicativo RPA agora tem atualização automática via GitHub!          ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝


⚡ COMEÇAR RAPIDAMENTE:
════════════════════════════════════════════════════════════════════════════

1️⃣  Abra PowerShell ou CMD neste diretório
    
2️⃣  Instale as dependências (primeira vez):
    pip install pyinstaller
    
3️⃣  Execute o script de compilação:
    compile_launcher.bat
    
4️⃣  Pronto! Seu executável está em: dist\RPA_Expedicao.exe
    
5️⃣  Clique no .exe para usar o app com auto-update


🎯 O QUE FOI IMPLEMENTADO:
════════════════════════════════════════════════════════════════════════════

✅ Auto-atualização via Git Pull silenciosa
   - Terminal preto não fica visível

✅ Tratamento de erros inteligente
   - Sem internet? App abre com versão local
   - Git não instalado? App abre normalmente
   
✅ Compilação em executável .exe
   - Clique uma vez e pronto
   - Sem precisar de Python instalado no PC do utilizador


📁 ARQUIVOS CRIADOS:
════════════════════════════════════════════════════════════════════════════

launcher.py                 - Novo ponto de entrada (auto-update)
compile_launcher.bat        - Script para compilar em .exe
GUIA_AUTO_UPDATE.md         - Documentação completa (ler primeiro!)
test_auto_update.py         - Script para testar antes de compilar
README.txt                  - Este arquivo


🧪 TESTAR ANTES DE COMPILAR:
════════════════════════════════════════════════════════════════════════════

Execute este comando para validar tudo:

    python test_auto_update.py

Ele irá verificar:
  - Se Git está instalado
  - Se este é um repositório Git
  - Se launcher.py existe
  - Se app.py existe
  - Se templates/ existe
  - Se PyInstaller está instalado


⚠️  PRÉ-REQUISITOS:
════════════════════════════════════════════════════════════════════════════

Você precisa de:
  1. Python 3.7+ instalado (use: python --version)
  2. Git instalado (use: git --version)
  3. PyInstaller (instale com: pip install pyinstaller)


🚀 MODO PASSO-A-PASSO:
════════════════════════════════════════════════════════════════════════════

Passo 1: Preparação
  [CMD]$ pip install pyinstaller

Passo 2: Teste (opcional mas recomendado)
  [CMD]$ python test_auto_update.py

Passo 3: Compilação
  [CMD]$ compile_launcher.bat
  
Passo 4: Resultado
  Seu .exe está em: dist\RPA_Expedicao.exe
  
Passo 5: Distribuição (opcional)
  Copie dist\RPA_Expedicao.exe + pasta .git para qualquer computador


🔍 VERIFICAÇÃO RÁPIDA:
════════════════════════════════════════════════════════════════════════════

Para verificar rapidamente se tudo está funcionando:

  1. Clique no dist\RPA_Expedicao.exe
  2. Não deve aparecer nenhuma janela preta/terminal
  3. A interface RPA deve abrir normalmente
  4. O código será atualizado silenciosamente


📝 ONDE LER MAIS:
════════════════════════════════════════════════════════════════════════════

Para documentação completa, abra: GUIA_AUTO_UPDATE.md

Nele você encontrará:
  - Como funciona o auto-update
  - Troubleshooting de problemas
  - Configurações avançadas
  - Como distribuir o .exe


❓ DÚVIDAS COMUNS:
════════════════════════════════════════════════════════════════════════════

P: Como distribuo o .exe para os meus colegas?
R: Copie dist\RPA_Expedicao.exe + pasta .git para eles
   Ou coloque em uma pasta partilhada de rede

P: E se o Git não estiver instalado no PC do utilizador?
R: O app abre normalmente, sem erros
   (simplesmente não faz auto-update)

P: O terminal fica visível?
R: Não! O terminal está oculto por padrão

P: Posso alterar o ícone do .exe?
R: Sim, leia o GUIA_AUTO_UPDATE.md na secção "Ícone Personalizado"

P: O que fazer se o auto-update falhar?
R: O app abre mesmo assim com a versão local
   Verifique sua conexão de internet


🔗 LINKS ÚTEIS:
════════════════════════════════════════════════════════════════════════════

Git: https://git-scm.com/download/win
Python: https://www.python.org/downloads/
PyInstaller: https://pyinstaller.org/


✉️  SUPORTE:
════════════════════════════════════════════════════════════════════════════

Se tiver problemas:
  1. Leia o GUIA_AUTO_UPDATE.md
  2. Execute: python test_auto_update.py
  3. Verifique se Git está instalado


════════════════════════════════════════════════════════════════════════════
Versão: 1.0 | Data: Maio 2026 | Autor: GitHub Copilot RPA
════════════════════════════════════════════════════════════════════════════
