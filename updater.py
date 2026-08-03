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

def _versao_tuple(v_str: str) -> tuple:
    """Converte '1.2.3' em (1, 2, 3) para comparação numérica."""
    try:
        return tuple(int(p) for p in str(v_str).strip().split("."))
    except Exception:
        return (0, 0, 0)


def get_current_version():
    """Lê a versão atual do arquivo version.txt embutido no .exe ou no diretório local"""
    try:
        cwd_version_file = os.path.join(os.getcwd(), "version.txt")
        if os.path.exists(cwd_version_file):
            with open(cwd_version_file, "r", encoding="utf-8") as f:
                ver = f.read().strip()
                if ver:
                    return ver

        base_path = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        version_file = os.path.join(base_path, "version.txt")
        
        with open(version_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        print(f"Erro ao ler versão local: {e}")
        return "0.0.0"

def get_remote_version():
    """Puxa a versão mais recente do GitHub"""
    try:
        req = urllib.request.Request(URL_VERSION, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as response:
            return response.read().decode('utf-8').strip()
    except Exception as e:
        print(f"Erro ao verificar versão remota: {e}")
        return None

def download_new_exe(remote_version):
    """Baixa o novo executável para uma pasta temporária exibindo mensagem amigável ao usuário"""
    popup_root = None
    try:
        # Exibe janela avisando o usuário sobre o download
        try:
            import tkinter as tk
            popup_root = tk.Tk()
            popup_root.title("Atualizando RPA Expedição")
            popup_root.geometry("420x130")
            popup_root.resizable(False, False)
            popup_root.attributes("-topmost", True)
            
            # Centralizar na tela
            popup_root.update_idletasks()
            width = popup_root.winfo_width()
            height = popup_root.winfo_height()
            x = (popup_root.winfo_screenwidth() // 2) - (width // 2)
            y = (popup_root.winfo_screenheight() // 2) - (height // 2)
            popup_root.geometry(f'{width}x{height}+{x}+{y}')
            
            lbl = tk.Label(
                popup_root,
                text=f"🚀 Nova versão ({remote_version}) encontrada!\nBaixando atualização, por favor aguarde...",
                font=("Segoe UI", 11),
                pady=20
            )
            lbl.pack()
            popup_root.update()
        except Exception:
            popup_root = None

        temp_dir = tempfile.gettempdir()
        new_exe_path = os.path.join(temp_dir, f"RPA_Expedicao_v{remote_version}.exe")
        
        print(f"Baixando nova versão ({remote_version}) para {new_exe_path}...")
        
        req = urllib.request.Request(URL_EXE, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=180) as response, open(new_exe_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
            
        return new_exe_path
    except Exception as e:
        print(f"Erro ao baixar novo executável: {e}")
        return None
    finally:
        if popup_root:
            try:
                popup_root.destroy()
            except Exception:
                pass

def apply_update_and_restart(new_exe_path):
    """Cria um .bat para substituir o executável atual pelo novo e reinicia"""
    try:
        current_exe_path = sys.executable
        if not getattr(sys, 'frozen', False):
            print("Não está rodando como executável. Atualização cancelada.")
            return

        bat_path = os.path.join(tempfile.gettempdir(), "rpa_update.bat")
        
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
        
        creation_flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0x08000000
        subprocess.Popen([bat_path], creationflags=creation_flags)
        
        sys.exit(0)
        
    except Exception as e:
        print(f"Erro ao aplicar atualização: {e}")

def check_for_updates():
    """Função principal chamada pelo launcher ao iniciar"""
    if not getattr(sys, 'frozen', False):
        print("Rodando em modo desenvolvimento. Auto-update desativado.")
        return

    print("Verificando atualizações...")
    local_version = get_current_version()
    remote_version = get_remote_version()
    
    if remote_version and _versao_tuple(remote_version) > _versao_tuple(local_version):
        print(f"Nova versão encontrada: {remote_version} (Atual: {local_version})")
        new_exe_path = download_new_exe(remote_version)
        
        if new_exe_path and os.path.exists(new_exe_path):
            apply_update_and_restart(new_exe_path)
    else:
        print(f"Aplicativo atualizado (Versão: {local_version}).")


