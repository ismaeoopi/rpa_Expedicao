#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Kill-Switch e Controle de Versão Mínima Obrigatória
=====================================================

Verifica remotamente (via GitHub) se o RPA está autorizado a iniciar.
Dois critérios de bloqueio:
  1. enabled == false  →  manutenção/emergência (admin desativou o app)
  2. versão local < min_required_version  →  versão obsoleta bloqueada

Caso qualquer critério seja atendido, exibe um alerta em tkinter e
encerra com sys.exit(1) ANTES de iniciar o app.py.

Uso (em launcher.py):
    import kill_switch
    kill_switch.verificar()
"""

import os
import sys
import json
import urllib.request
import urllib.error

# ─────────────────────────────────────────────────────────
#  Configurações — altere conforme o repositório
# ─────────────────────────────────────────────────────────
GITHUB_USER   = "ismaeoopi"
GITHUB_REPO   = "rpa_Expedicao"
GITHUB_BRANCH = "main"

URL_VERSION_CONTROL = (
    f"https://raw.githubusercontent.com/"
    f"{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}/version_control.json"
)

TIMEOUT_SEGUNDOS = 8   # Tempo máximo de espera pela resposta do GitHub


# ─────────────────────────────────────────────────────────
#  Helpers internos
# ─────────────────────────────────────────────────────────

def _versao_tuple(versao_str: str) -> tuple:
    """Converte '1.2.3' em (1, 2, 3) para comparação numérica."""
    try:
        return tuple(int(p) for p in str(versao_str).strip().split("."))
    except Exception:
        return (0, 0, 0)


def _ler_versao_local() -> str:
    """Lê a versão atual do version.txt embutido no .exe ou na pasta do script."""
    try:
        # Prioriza o version.txt na pasta atual (caso tenha sido atualizado por git pull)
        cwd_version_file = os.path.join(os.getcwd(), "version.txt")
        if os.path.exists(cwd_version_file):
            with open(cwd_version_file, "r", encoding="utf-8") as f:
                ver = f.read().strip()
                if ver:
                    return ver

        base_path = (
            sys._MEIPASS
            if getattr(sys, "frozen", False)
            else os.path.dirname(os.path.abspath(__file__))
        )
        version_file = os.path.join(base_path, "version.txt")
        with open(version_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "0.0.0"


def _buscar_version_control() -> dict | None:
    """
    Faz o download do version_control.json do GitHub.
    Retorna o dict parseado ou None se falhar (sem internet, timeout etc.).
    """
    try:
        req = urllib.request.Request(
            URL_VERSION_CONTROL,
            headers={"User-Agent": "RPA-KillSwitch/1.0"},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEGUNDOS) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except Exception:
        return None


def _mostrar_alerta_e_sair(titulo: str, mensagem: str) -> None:
    """
    Exibe uma janela de erro com tkinter e encerra o processo com código 1.
    Funciona mesmo sem a janela principal do app aberta.
    """
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()          # Oculta a janela raiz vazia
        root.attributes("-topmost", True)   # Garante que fique na frente
        messagebox.showerror(titulo, mensagem, parent=root)
        root.destroy()
    except Exception:
        # Fallback para ambientes sem tkinter (ex.: servidores headless)
        print(f"\n[BLOQUEADO] {titulo}\n{mensagem}\n")
    finally:
        sys.exit(1)


# ─────────────────────────────────────────────────────────
#  Funções públicas
# ─────────────────────────────────────────────────────────

def verificar_kill_switch(controle: dict | None = None) -> dict | None:
    """
    Verifica APENAS se o app está desativado emergencialmente (enabled == false).
    Deve ser executado ANTES das tentativas de update.
    """
    if controle is None:
        controle = _buscar_version_control()

    if controle is None:
        return None

    enabled = controle.get("enabled", True)
    if not enabled:
        mensagem = controle.get(
            "blocked_message",
            "⚠️ O RPA está temporariamente desativado. Tente novamente mais tarde.",
        )
        _mostrar_alerta_e_sair("RPA Bloqueado", mensagem)
    
    return controle


def verificar_versao_minima(controle: dict | None = None) -> None:
    """
    Verifica APENAS se a versão local atende à versão mínima obrigatória.
    Deve ser executado APÓS as tentativas de update (git pull / updater).
    """
    if controle is None:
        controle = _buscar_version_control()

    if controle is None:
        return

    min_version_str = controle.get("min_required_version", "0.0.0")
    local_version_str = _ler_versao_local()

    min_tuple   = _versao_tuple(min_version_str)
    local_tuple = _versao_tuple(local_version_str)

    if local_tuple < min_tuple:
        mensagem = controle.get(
            "outdated_message",
            "⚠️ Sua versão do RPA está desatualizada e foi bloqueada. "
            "Por favor, aguarde o download da versão mais recente ou contate o suporte.",
        )
        _mostrar_alerta_e_sair(
            f"Versão Desatualizada (local: {local_version_str} | mínima: {min_version_str})",
            mensagem,
        )


def verificar() -> None:
    """
    Verifica kill-switch e versão mínima em sequência.
    Mantido para compatibilidade.
    """
    controle = verificar_kill_switch()
    verificar_versao_minima(controle)

