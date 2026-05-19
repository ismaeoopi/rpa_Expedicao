#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Launcher RPA - Auto-Update via Git + Execução da Aplicação
===========================================================

Este script é o ponto de entrada do aplicativo RPA.
Ele executa o git pull SILENCIOSAMENTE antes de iniciar o app.py

Como compilar para .exe com PyInstaller:
    pyinstaller --onefile --windowed --icon=icon.ico --add-data "templates:templates" launcher.py

Autor: Tim TI
Data: 2026
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def atualizar_repositorio():
    """
    Executa git pull silenciosamente sem mostrar terminal no Windows.
    Retorna True se sucesso ou já atualizado, False se erro.
    """
    try:
        if not os.path.exists(".git"):
            # Não é um repositório Git, continua normalmente
            return True
        
        # Define flags para executar sem mostrar janela no Windows
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0x08000000
        else:
            creation_flags = 0
        
        # Executa git pull com timeout de 20 segundos
        resultado = subprocess.run(
            ["git", "pull"],
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=creation_flags,
            cwd=os.getcwd()
        )
        
        # Retorna sucesso se o returncode for 0
        return resultado.returncode == 0
        
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        # Git não instalado, timeout, ou outro erro - continua normalmente
        return True


def executar_app():
    """
    Executa o app.py usando o interpretador Python atual.
    """
    try:
        # Determina o caminho do app.py
        script_dir = os.path.dirname(os.path.abspath(__file__))
        app_path = os.path.join(script_dir, "app.py")
        
        if not os.path.exists(app_path):
            print(f"Erro: app.py não encontrado em {app_path}")
            sys.exit(1)
        
        # Executa o app.py
        exec(open(app_path).read())
        
    except Exception as e:
        print(f"Erro ao executar app.py: {e}")
        sys.exit(1)


def main():
    """
    Ponto de entrada principal.
    1. Tenta atualizar via Git (silenciosamente)
    2. Executa o app.py
    """
    try:
        # Muda para o diretório do script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        
        # Tenta atualizar (silenciosamente)
        atualizar_repositorio()
        
        # Executa o app
        executar_app()
        
    except Exception as e:
        # Em caso de erro crítico, tenta abrir o app mesmo assim
        try:
            executar_app()
        except:
            sys.exit(1)


if __name__ == "__main__":
    main()
