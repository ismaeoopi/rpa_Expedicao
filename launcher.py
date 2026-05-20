#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Launcher RPA - Auto-Update via Git + Execução da Aplicação
===========================================================

Este script é o ponto de entrada do aplicativo RPA.
Ele executa o git pull SILENCIOSAMENTE antes de iniciar o app.py

Autor: Tim TI
Data: 2026
"""

import os
import sys
import subprocess
import tempfile
import traceback
from pathlib import Path

def atualizar_repositorio():
    """
    Executa git pull silenciosamente sem mostrar terminal no Windows.
    Retorna True se sucesso ou já atualizado, False se erro.
    """
    try:
        if not os.path.exists(".git"):
            return True
        
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0x08000000
        else:
            creation_flags = 0
        
        resultado = subprocess.run(
            ["git", "pull"],
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=creation_flags,
            cwd=os.getcwd()
        )
        
        return resultado.returncode == 0
        
    except Exception as e:
        return True  # Continua mesmo se git falhar


def executar_app():
    """
    Executa o app.py de forma compatível com PyInstaller.
    """
    try:
        # Se estiver dentro do PyInstaller
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        app_path = os.path.join(base_path, "app.py")
        
        # Verifica se app.py existe
        if not os.path.exists(app_path):
            raise FileNotFoundError(f"app.py não encontrado em {app_path}")
        
        # Executa app.py com runpy (mais compatível)
        import runpy
        runpy.run_path(app_path, run_name="__main__")
        
    except Exception as e:
        # Se tudo falhar, tenta mostrar erro em uma janela
        try:
            import tkinter as tk
            from tkinter import showerror
            root = tk.Tk()
            root.withdraw()
            showerror("Erro no RPA", f"Erro ao iniciar aplicação:\n\n{str(e)}\n\n{traceback.format_exc()}")
            root.destroy()
        except:
            pass
        
        # Log de erro em arquivo
        try:
            log_file = os.path.join(tempfile.gettempdir(), "rpa_error.log")
            with open(log_file, "w") as f:
                f.write(f"Erro ao executar app.py:\n{traceback.format_exc()}")
        except:
            pass
        
        sys.exit(1)


def main():
    """
    Ponto de entrada principal.
    """
    try:
        # Muda para o diretório do script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        
        # Tenta atualizar via Git (silenciosamente)
        atualizar_repositorio()
        
        # Executa o app
        executar_app()
        
    except Exception as e:
        try:
            import tkinter as tk
            from tkinter import showerror
            root = tk.Tk()
            root.withdraw()
            showerror("Erro Crítico", f"Erro ao iniciar:\n\n{str(e)}")
            root.destroy()
        except:
            print(f"Erro crítico: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()