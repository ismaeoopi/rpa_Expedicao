# debug_migo_sem_planilha.py
import os
import sys
from dotenv import load_dotenv

# Adiciona o diretório atual ao sys.path para importações locais
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.utils.common import log_sys
from src.utils.sap_utils import conectar_sap
from src.estoque.processo_sap import processo_estoque_sem_planilha

# ==============================================================================
# CONFIGURAÇÕES DE DEPURAÇÃO DO PROCESSO SEM PLANILHA (A PARTIR DA MIGO)
# ==============================================================================

# 1. Lista de Inbounds / VL32N para processamento
# Pode ser uma lista de strings ex: ["18001234"] ou dicionários [{"val": "18001234"}]
VL32_LIST = ["181230301"]

# 2. Ponto de Partida do Processo:
# 1 -> Início Completo (VL32N -> CS15 -> CO01 -> MIGO ZP1/261 -> MIGO 411 -> PRDI)
# 2 -> A partir da MIGO ZP1 / 261 (Requer OP_GLOBAL informada abaixo) -> MIGO 411 -> PRDI
# 3 -> A partir da MIGO 411 (Transferência) -> PRDI
# 4 -> A partir do PRDI
PONTO_PARTIDA = 3

# 3. Ordem de Produção (OP)
# Necessária se PONTO_PARTIDA = 2 (Apontamento/Consumo MIGO ZP1)
OP_GLOBAL = "10001234"

# 4. Inbound / MIGO de Transferência Gerada (Opcional)
# Usada principalmente se for direto para a etapa 4 (PRDI)
MIGO_GLOBAL = None

# 5. ID do Lote no Banco de Dados SQLite (Opcional)
# Caso queira retomar um lote existente, informe o ID numérico ex: 5. Caso contrário, deixe None.
LOTE_ID = None


def main():
    # Carrega variáveis do arquivo .env
    dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(dotenv_path)

    print("=" * 70)
    print("🚀 SCRIPT DE DEPURAÇÃO: PROCESSO DE ESTOQUE SEM PLANILHA (MIGO/PRDI) 🚀")
    print("=" * 70)
    print(f"📦 Inbounds/VL32: {VL32_LIST}")
    print(f"📍 Ponto de Partida: {PONTO_PARTIDA} (2=MIGO ZP1, 3=MIGO 411, 4=PRDI)")
    print(f"📄 OP Global: {OP_GLOBAL}")
    if MIGO_GLOBAL:
        print(f"🔄 MIGO Global (PRDI): {MIGO_GLOBAL}")
    if LOTE_ID:
        print(f"💾 Lote DB ID: {LOTE_ID}")
    print("-" * 70)

    # 1. Verifica Conexão com o SAP GUI
    print("🔍 Verificando conexão com o SAP GUI...")
    session = conectar_sap()
    if not session:
        print("❌ ERRO: Não foi possível conectar ao SAP GUI ativo. Abra o SAP antes de rodar.")
        sys.exit(1)
    print("✅ Conexão com SAP GUI estabelecida com sucesso!")
    print("-" * 70)

    # 2. Executa a automação a partir da etapa selecionada
    print("▶️ Iniciando execução do processo sem planilha...")
    print("-" * 70)

    try:
        resultado = processo_estoque_sem_planilha(
            vl32_list=VL32_LIST,
            ponto_partida=PONTO_PARTIDA,
            op_global=OP_GLOBAL,
            migo_global=MIGO_GLOBAL,
            lote_id=LOTE_ID
        )

        print("\n" + "=" * 70)
        if resultado:
            print("🎉 PROCESSO CONCLUÍDO COM SUCESSO!")
        else:
            print("⚠️ PROCESSO FINALIZADO COM AVISOS OU PENDÊNCIAS.")
        print("=" * 70)

    except Exception as e:
        print("\n" + "x" * 70)
        print(f"❌ ERRO NA EXECUÇÃO DO DEBUG:")
        print(f"⚠️ Detalhe: {e}")
        print("x" * 70)

    finally:
        print("\n📋 LOGS DE EXECUÇÃO DETALHADOS:")
        print("-" * 70)
        for log in log_sys.logs:
            print(log)
        print("-" * 70)


if __name__ == "__main__":
    main()
