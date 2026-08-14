import os
import sys
from dotenv import load_dotenv

# Adiciona o diretório atual ao sys.path para importações locais
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.utils.common import log_sys
from src.expedicao.sap_cabotagem_playwright import rodar_criacao_of_cabotagem_playwright

def main():
    # Carrega variáveis do arquivo .env
    dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(dotenv_path)
    
    usuario = os.getenv("SAP_WEB_USER")
    senha = os.getenv("SAP_WEB_PASSWORD")
    
    # Insira aqui os números das remessas reais para testar a criação da OF
    remessas = ["80748899", "80748890"]
    transportadora = "9190617"
    valor_frete = 4816.53
    
    print("=" * 60)
    print("🚀 Script de Depuração da Criação de Ordem de Frete (OF) CABOTAGEM SAP 🚀")
    print("=" * 60)
    print(f"👤 Usuário: {usuario}")
    print(f"📦 Remessas para Teste: {remessas}")
    print(f"🚚 Transportadora: {transportadora}")
    print(f"💰 Valor Frete: {valor_frete}")
    print("-" * 60)
    print("Aguarde, iniciando o navegador Chromium (Modo Oculto / Headless)...")
    print("-" * 60)
    
    try:
        resultado = rodar_criacao_of_cabotagem_playwright(
            remessas=remessas,
            transportadora=transportadora,
            valor_frete=valor_frete,
            usuario=usuario,
            senha=senha,
            headless=True
        )
        of_criada = resultado["of_numero"]
        confirmadas = resultado["remessas_confirmadas"]
        ausentes    = resultado["remessas_ausentes"]

        print("\n" + "=" * 60)
        print(f"✅ SUCESSO! Ordem de Frete de Cabotagem criada no SAP Fiori!")
        print(f"🚛 Número da OF: {of_criada}")
        print("-" * 60)
        print(f"📦 Remessas verificadas na aba Items:")
        for r in confirmadas:
            print(f"   ✅ {r} — CONFIRMADA na OF")
        for r in ausentes:
            print(f"   ⚠️  {r} — NÃO encontrada na aba Items")
        if not ausentes:
            print("🎉 Todas as remessas foram confirmadas com sucesso!")
        else:
            print(f"⚠️  {len(ausentes)} remessa(s) não encontrada(s) — verifique manualmente no SAP.")
        print("=" * 60)
    except Exception as e:
        print("\n" + "x" * 60)
        print(f"❌ ERRO na Execução da Automação:")
        print(f"⚠️ Detalhe: {e}")
        print("x" * 60)
"""        print("\n📋 LOGS DE EXECUÇÃO DETALHADOS:")
        for log in log_sys.logs:
            print(log)"""


if __name__ == "__main__":
    main()
