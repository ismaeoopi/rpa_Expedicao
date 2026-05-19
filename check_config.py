#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Verificador de Configuração RPA
================================

Use este script para diagnosticar problemas com o auto-update do RPA.

Como usar:
    python check_config.py

Isto irá gerar um relatório de diagnóstico que pode ser enviado para suporte.
"""

import os
import sys
import subprocess
import platform
from pathlib import Path
from datetime import datetime


def get_system_info():
    """Coleta informações do sistema."""
    return {
        "OS": platform.system(),
        "Python Version": platform.python_version(),
        "Architecture": platform.architecture()[0],
        "Current Directory": os.getcwd(),
    }


def get_git_info():
    """Coleta informações do Git."""
    info = {}
    
    # Versão do Git
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        info["Git Version"] = result.stdout.strip()
    except:
        info["Git Version"] = "❌ Não encontrado"
    
    # Repositório
    info["Is Git Repo"] = "✅ Sim" if os.path.exists(".git") else "❌ Não"
    
    # Remote
    if os.path.exists(".git"):
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=os.getcwd()
            )
            info["Remote Origin"] = result.stdout.strip() or "⚠️ Nenhum configurado"
        except:
            info["Remote Origin"] = "⚠️ Erro ao verificar"
        
        # Branch
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=os.getcwd()
            )
            info["Current Branch"] = result.stdout.strip()
        except:
            info["Current Branch"] = "⚠️ Erro ao verificar"
    
    return info


def get_files_info():
    """Verifica se os arquivos necessários existem."""
    return {
        "launcher.py": "✅ Existe" if os.path.exists("launcher.py") else "❌ Falta",
        "app.py": "✅ Existe" if os.path.exists("app.py") else "❌ Falta",
        "templates/": "✅ Existe" if os.path.isdir("templates") else "❌ Falta",
        ".git/": "✅ Existe" if os.path.isdir(".git") else "❌ Falta",
    }


def get_python_packages():
    """Verifica pacotes Python instalados."""
    packages = [
        "flask",
        "pandas",
        "openpyxl",
        "pywin32",
        "pyinstaller",
    ]
    
    result = {}
    for package in packages:
        try:
            __import__(package)
            result[package] = "✅ Instalado"
        except ImportError:
            result[package] = "❌ Não instalado"
    
    return result


def test_git_connectivity():
    """Testa conectividade com o repositório remoto."""
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", "origin"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=os.getcwd()
        )
        if result.returncode == 0:
            return "✅ Conectado ao repositório remoto"
        else:
            return f"❌ Erro de conectividade: {result.stderr}"
    except subprocess.TimeoutExpired:
        return "⏱️ Timeout (conexão lenta ou sem internet)"
    except Exception as e:
        return f"⚠️ Erro: {e}"


def generate_report():
    """Gera relatório de diagnóstico."""
    report = []
    
    report.append("╔" + "="*70 + "╗")
    report.append("║" + " "*70 + "║")
    report.append("║" + "RELATÓRIO DE DIAGNÓSTICO - RPA AUTO-UPDATE".center(70) + "║")
    report.append("║" + " "*70 + "║")
    report.append("╚" + "="*70 + "╝")
    
    report.append("")
    report.append(f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    report.append("")
    
    # Sistema
    report.append("═" * 70)
    report.append("📊 INFORMAÇÕES DO SISTEMA")
    report.append("═" * 70)
    for key, value in get_system_info().items():
        report.append(f"  {key}: {value}")
    
    # Git
    report.append("")
    report.append("═" * 70)
    report.append("🔧 CONFIGURAÇÃO GIT")
    report.append("═" * 70)
    for key, value in get_git_info().items():
        report.append(f"  {key}: {value}")
    
    # Teste de conectividade
    report.append("")
    report.append("🔗 Teste de Conectividade:")
    report.append(f"  {test_git_connectivity()}")
    
    # Arquivos
    report.append("")
    report.append("═" * 70)
    report.append("📁 ARQUIVOS NECESSÁRIOS")
    report.append("═" * 70)
    for file, status in get_files_info().items():
        report.append(f"  {file}: {status}")
    
    # Pacotes Python
    report.append("")
    report.append("═" * 70)
    report.append("📦 PACOTES PYTHON")
    report.append("═" * 70)
    for package, status in get_python_packages().items():
        report.append(f"  {package}: {status}")
    
    # Recomendações
    report.append("")
    report.append("═" * 70)
    report.append("💡 RECOMENDAÇÕES")
    report.append("═" * 70)
    
    files = get_files_info()
    if all("✅" in v for v in files.values()):
        report.append("  ✅ Todos os arquivos estão presentes!")
    else:
        report.append("  ⚠️ Arquivos faltando - verifique acima")
    
    packages = get_python_packages()
    missing = [k for k, v in packages.items() if "❌" in v]
    if missing:
        report.append(f"  ⚠️ Pacotes faltando: {', '.join(missing)}")
        report.append(f"     Execute: pip install {' '.join(missing)}")
    else:
        report.append("  ✅ Todos os pacotes estão instalados!")
    
    if "❌" in test_git_connectivity():
        report.append("  ⚠️ Problemas de conectividade com repositório remoto")
        report.append("     Verifique sua conexão de internet")
        report.append("     Ou verifique as credenciais do Git")
    
    # Próximos passos
    report.append("")
    report.append("═" * 70)
    report.append("🚀 PRÓXIMOS PASSOS")
    report.append("═" * 70)
    
    if all("✅" in v for v in files.values()) and not missing:
        report.append("  1. Execute: python test_auto_update.py")
        report.append("  2. Execute: compile_launcher.bat")
        report.append("  3. Teste clicando em: dist\\RPA_Expedicao.exe")
    else:
        report.append("  1. Resolva os problemas acima")
        report.append("  2. Execute este script novamente")
        report.append("  3. Quando tudo estiver ✅, execute: compile_launcher.bat")
    
    report.append("")
    report.append("═" * 70)
    
    return "\n".join(report)


def save_report(report):
    """Salva o relatório em um arquivo."""
    filename = f"rpa_diagnostico_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(report)
        return filename
    except:
        return None


def main():
    """Função principal."""
    report = generate_report()
    print(report)
    
    # Tenta salvar
    filename = save_report(report)
    if filename:
        print(f"\n📄 Relatório salvo em: {filename}")
        print("   Você pode enviar este arquivo para suporte")
    else:
        print("\n⚠️ Não foi possível salvar o relatório")


if __name__ == "__main__":
    main()
