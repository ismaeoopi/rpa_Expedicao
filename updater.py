import os
import sys
import urllib.request
import urllib.error
import tempfile
import subprocess
import time
import shutil

# Configurações do Repositório GitHub
GITHUB_USER = "ismaeoopi"
GITHUB_REPO = "rpa_Expedicao"
GITHUB_BRANCH = "main"

# URLs para verificar versão e baixar o novo executável
URL_VERSION = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}/version.txt"
URL_EXE = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/raw/{GITHUB_BRANCH}/RPA_Expedicao.exe"

def get_current_version():
    """Lê a versão atual do arquivo version.txt embutido no .exe"""
    try:
        # Se rodando do PyInstaller, usa a pasta temporária
        base_path = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        version_file = os.path.join(base_path, "version.txt")
        
        with open(version_file, "r") as f:
            return f.read().strip()
    except Exception as e:
        print(f"Erro ao ler versão local: {e}")
        return "0.0.0"

def get_remote_version():
    """Puxa a versão mais recente do GitHub"""
    try:
        # Timeout de 5 segundos para não travar o app se estiver sem internet
        req = urllib.request.Request(URL_VERSION, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.read().decode('utf-8').strip()
    except Exception as e:
        print(f"Erro ao verificar versão remota: {e}")
        return None

def download_new_exe(remote_version):
    """Baixa o novo executável para uma pasta temporária"""
    try:
        temp_dir = tempfile.gettempdir()
        new_exe_path = os.path.join(temp_dir, f"RPA_Expedicao_v{remote_version}.exe")
        
        print(f"Baixando nova versão ({remote_version}) para {new_exe_path}...")
        
        req = urllib.request.Request(URL_EXE, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=60) as response, open(new_exe_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
            
        return new_exe_path
    except Exception as e:
        print(f"Erro ao baixar novo executável: {e}")
        return None

def apply_update_and_restart(new_exe_path):
    """Cria um .bat para substituir o executável atual pelo novo e reinicia"""
    try:
        current_exe_path = sys.executable
        if not getattr(sys, 'frozen', False):
            print("Não está rodando como executável. Atualização cancelada.")
            return

        bat_path = os.path.join(tempfile.gettempdir(), "rpa_update.bat")
        
        # O script .bat fará o seguinte:
        # 1. Espera 2 segundos para dar tempo deste executável fechar
        # 2. Tenta deletar o executável antigo (se falhar, tenta novamente)
        # 3. Move o novo executável para o lugar do antigo
        # 4. Inicia o novo executável
        # 5. Deleta o próprio arquivo .bat
        bat_content = f"""@echo off
timeout /t 2 /nobreak > NUL
:loop
del "{current_exe_path}" /q
if exist "{current_exe_path}" (
    timeout /t 1 /nobreak > NUL
    goto loop
)
move /Y "{new_exe_path}" "{current_exe_path}"
start "" "{current_exe_path}"
del "%~f0"
"""
        with open(bat_path, "w") as f:
            f.write(bat_content)

        print("Atualização baixada! O aplicativo será reiniciado.")
        
        # Define flags para executar o .bat silenciosamente (sem janela do cmd)
        creation_flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0x08000000
        
        subprocess.Popen([bat_path], creationflags=creation_flags)
        
        # Fecha o aplicativo atual para o .bat poder substituí-lo
        sys.exit(0)
        
    except Exception as e:
        print(f"Erro ao aplicar atualização: {e}")

def check_for_updates():
    """Função principal chamada pelo app.py ao iniciar"""
    # Só tenta atualizar se estiver compilado (evita baixar .exe enquanto desenvolve em .py)
    if not getattr(sys, 'frozen', False):
        print("Rodando em modo desenvolvimento. Auto-update desativado.")
        return

    print("Verificando atualizações...")
    local_version = get_current_version()
    remote_version = get_remote_version()
    
    if remote_version and remote_version != local_version:
        # Uma lógica simples: se for diferente, tenta baixar. 
        # (Para ser mais robusto, poderíamos quebrar por pontos e comparar maior/menor, 
        # mas checar se é diferente resolve a maioria dos casos práticos)
        print(f"Nova versão encontrada: {remote_version} (Atual: {local_version})")
        new_exe_path = download_new_exe(remote_version)
        
        if new_exe_path and os.path.exists(new_exe_path):
            apply_update_and_restart(new_exe_path)
    else:
        print(f"Aplicativo atualizado (Versão: {local_version}).")

