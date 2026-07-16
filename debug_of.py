import os
import sys
from dotenv import load_dotenv

# Adiciona o diretório atual ao sys.path para importações locais
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.utils.common import log_sys
from src.expedicao.sap_ordem_frete import rodar_criacao_of_playwright

def main():
    # Carrega variáveis do arquivo .env
    dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(dotenv_path)
    
    usuario = os.getenv("SAP_WEB_USER", "SP3IBNASCIME")
    senha = os.getenv("SAP_WEB_PASSWORD", "Leamsi!233219779")
    
    # Insira aqui os números das remessas reais para testar a criação da OF
    remessas = ["80714414"]
    
    print("=" * 60)
    print("🚀 Script de Depuração da Criação de Ordem de Frete (OF) SAP 🚀")
    print("=" * 60)
    print(f"👤 Usuário: {usuario}")
    print(f"📦 Remessas para Teste: {remessas}")
    print("-" * 60)
    print("Aguarde, iniciando o navegador Chromium (Visível)...")
    print("-" * 60)
    
    try:
        of_criada = rodar_criacao_of_playwright(remessas, usuario, senha)
        print("\n" + "=" * 60)
        print(f"✅ SUCESSO! Ordem de Frete criada com sucesso no SAP Fiori!")
        print(f"🚛 Número da OF: {of_criada}")
        print("=" * 60)
    except Exception as e:
        print("\n" + "x" * 60)
        print(f"❌ ERRO na Execução da Automação:")
        print(f"⚠️ Detalhe: {e}")
        print("x" * 60)

if __name__ == "__main__":
    main()
