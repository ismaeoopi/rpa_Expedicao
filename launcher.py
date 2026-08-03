#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Launcher RPA - Auto-Update via Git + Execução da Aplicação
===========================================================

Este script é o ponto de entrada do aplicativo RPA.
Ele executa atualizações ANTES de iniciar o app.py

Autor: Tim TI
Data: 2026
"""

import os
import sys
import subprocess
import tempfile
import traceback
from pathlib import Path

# Imports falsos apenas para o PyInstaller detectar as dependências do app.py
if False:
    import requests
    import dotenv
    import pandas
    import openpyxl
    import flask
    import flask_cors
    import reportlab
    import jinja2
    import werkzeug
    import win32com
    import win32com.client
    import win32con
    import win32gui
    import PIL
    import plyer
    import geopy
    import customtkinter
    import git
    import sqlite3
    import Entreposto
    import kill_switch



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


def verificar_atualizacoes_github():
    """
    Verifica se há nova versão no GitHub e atualiza o .exe se necessário
    (Funciona mesmo SEM repositório .git)
    """
    try:
        import updater
        updater.check_for_updates()
    except Exception as e:
        pass  # Continua mesmo se falhar


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
    1. [KILL-SWITCH] Verifica remotamente se o app está habilitado e a versão é válida
    2. Atualiza via Git (se disponível)
    3. Verifica atualizações no GitHub (funciona SEM Git)
    4. Executa o app.py
    """
    try:
        # Muda para o diretório do script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)

        # ── PASSO 1: Kill-Switch e Versão Mínima ──────────────────────────
        # Esta verificação é SEMPRE a primeira a ser executada.
        # Se o app estiver desabilitado remotamente OU a versão local for
        # inferior à versão mínima exigida, exibe alerta e encerra (sys.exit).
        # Se não houver internet ou o GitHub estiver offline, continua normalmente.
        import kill_switch
        kill_switch.verificar()
        # ─────────────────────────────────────────────────────────────────

        # Tenta atualizar via Git (silenciosamente)
        atualizar_repositorio()
        
        # Verifica e aplica atualizações do GitHub
        # IMPORTANTE: Isso tem que ser ANTES de executar o app.py
        # Assim um .exe antigo baixa a versão nova e reinicia
        verificar_atualizacoes_github()
        
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