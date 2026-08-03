#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de Teste - Auto-Update do RPA
====================================

Use este script para testar a funcionalidade de auto-update
antes de compilar o executável com PyInstaller.

Como usar:
    python test_auto_update.py

"""

import os
import sys
import subprocess
from pathlib import Path


def print_header(title):
    """Imprime um cabeçalho formatado."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def test_git_installed():
    """Testa se Git está instalado."""
    print_header("TESTE 1: Verificar se Git está instalado")
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        print(f"✅ Git instalado: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("❌ Git NÃO está instalado!")
        print("   Para instalar: https://git-scm.com/download/win")
        return False
    except Exception as e:
        print(f"❌ Erro ao testar Git: {e}")
        return False


def test_git_repo():
    """Testa se o diretório atual é um repositório Git."""
    print_header("TESTE 2: Verificar se é um repositório Git")
    
    if os.path.exists(".git"):
        print("✅ Repositório .git encontrado!")
        
        # Mostra informações do repositório
        try:
            result = subprocess.run(
                ["git", "remote", "-v"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=os.getcwd()
            )
            if result.stdout:
                print(f"\n📍 Remotes:\n{result.stdout}")
            else:
                print("⚠️ Nenhum remote configurado (git pull falhará)")
                return False
                
            # Mostra branch atual
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=os.getcwd()
            )
            print(f"📌 Branch atual: {result.stdout.strip()}")
            return True
            
        except Exception as e:
            print(f"⚠️ Erro ao verificar repositório: {e}")
            return False
    else:
        print("❌ Nenhum repositório .git encontrado!")
        print("   Este diretório não é um repositório Git.")
        print("   Para criar: git init")
        return False


def test_git_pull_silent():
    """Testa o git pull com a configuração silenciosa."""
    print_header("TESTE 3: Simular git pull SILENCIOSO")
    
    try:
        print("Testando comando: git pull (silencioso no Windows)...\n")
        
        # Define flags para Windows
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0x08000000
        else:
            creation_flags = 0
        
        # Executa git pull
        resultado = subprocess.run(
            ["git", "pull"],
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=creation_flags,
            cwd=os.getcwd()
        )
        
        print(f"Return code: {resultado.returncode}")
        print(f"Output: {resultado.stdout}")
        if resultado.stderr:
            print(f"Stderr: {resultado.stderr}")
        
        if resultado.returncode == 0:
            print("\n✅ Git pull executado com SUCESSO!")
            return True
        else:
            print("\n⚠️ Git pull retornou código de erro (veja output acima)")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Timeout ao executar git pull (repositório muito grande?)")
        return False
    except Exception as e:
        print(f"❌ Erro ao executar git pull: {e}")
        return False


def test_launcher_exists():
    """Verifica se launcher.py existe."""
    print_header("TESTE 4: Verificar se launcher.py existe")
    
    if os.path.exists("launcher.py"):
        print("✅ launcher.py encontrado!")
        
        # Verifica se tem permissões de leitura
        try:
            with open("launcher.py", "r", encoding="utf-8") as f:
                lines = len(f.readlines())
            print(f"📄 Arquivo tem {lines} linhas")
            return True
        except Exception as e:
            print(f"❌ Erro ao ler launcher.py: {e}")
            return False
    else:
        print("❌ launcher.py NÃO encontrado!")
        print("   Este arquivo deve estar no mesmo diretório")
        return False


def test_app_py_exists():
    """Verifica se app.py existe."""
    print_header("TESTE 5: Verificar se app.py existe")
    
    if os.path.exists("app.py"):
        print("✅ app.py encontrado!")
        return True
    else:
        print("❌ app.py NÃO encontrado!")
        return False


def test_templates_exists():
    """Verifica se pasta templates existe."""
    print_header("TESTE 6: Verificar se pasta templates existe")
    
    if os.path.isdir("templates"):
        print("✅ Pasta templates encontrada!")
        files = os.listdir("templates")
        print(f"   Arquivos: {', '.join(files)}")
        return True
    else:
        print("❌ Pasta templates NÃO encontrada!")
        return False


def test_pyinstaller():
    """Verifica se PyInstaller está instalado."""
    print_header("TESTE 7: Verificar se PyInstaller está instalado")
    
    try:
        result = subprocess.run(
            ["pyinstaller", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        print(f"✅ PyInstaller instalado: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("⚠️ PyInstaller NÃO está instalado!")
        print("   Para instalar: pip install pyinstaller")
        return False
    except Exception as e:
        print(f"⚠️ Erro ao testar PyInstaller: {e}")
        return False


def main():
    """Executa todos os testes."""
    print("\n")
    print("+" + "="*68 + "+")
    print("|" + " "*68 + "|")
    print("|" + "  TESTES DE AUTO-UPDATE DO RPA  ".center(68) + "|")
    print("|" + " "*68 + "|")
    print("+" + "="*68 + "+")
    print(f"\nData: {__import__('datetime').datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"Diretório: {os.path.abspath('.')}")
    print(f"Plataforma: {sys.platform}")
    
    # Lista de testes
    tests = [
        ("Git Instalado", test_git_installed),
        ("Repositório Git", test_git_repo),
        ("Git Pull Silencioso", test_git_pull_silent),
        ("launcher.py", test_launcher_exists),
        ("app.py", test_app_py_exists),
        ("Pasta templates", test_templates_exists),
        ("PyInstaller", test_pyinstaller),
    ]
    
    # Executa testes
    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n❌ ERRO CRÍTICO: {e}")
            results[name] = False
    
    # Resumo
    print_header("📊 RESUMO DOS TESTES")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{status}  {name}")
    
    print(f"\n{passed}/{total} testes aprovados")
    
    # Recomendações
    print_header("💡 RECOMENDAÇÕES")
    
    if results["Git Instalado"] and results["Repositório Git"] and results["launcher.py"] and results["app.py"]:
        print("✅ Tudo está configurado!")
        print("\n🚀 Próximos passos:")
        print("   1. Execute: compile_launcher.bat")
        print("   2. O executável será criado em: dist\\RPA_Expedicao.exe")
        print("   3. Teste clicando no .exe")
    else:
        print("⚠️ Existem problemas a resolver:")
        if not results["Git Instalado"]:
            print("   - Instale Git: https://git-scm.com/download/win")
        if not results["Repositório Git"]:
            print("   - Configure um repositório Git: git init")
        if not results["launcher.py"]:
            print("   - Copie launcher.py para este diretório")
        if not results["app.py"]:
            print("   - app.py não encontrado (deve estar aqui)")
    
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()
