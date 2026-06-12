# debug.py
import sys
from src.utils.sap_utils import conectar_sap
from src.expedicao import EntrepostoProcessador

# Configurações de teste
ENTREPOSTO_TESTE = "ITAJAI"  # ou "ITAJAI"
CARGAS_TESTE = ["IT30/06-26"]  # Insira a(s) carga(s) de teste aqui

if __name__ == "__main__":
    print(f"🤖 Iniciando teste do processador de Entreposto para {ENTREPOSTO_TESTE}...")
    
    # 1. Carrega os dados estruturados do SharePoint
    try:
        dados = EntrepostoProcessador.obter_dados_etapas(ENTREPOSTO_TESTE, CARGAS_TESTE)
        print("✅ Dados carregados com sucesso:")
        for c_id, c_val in dados.items():
            print(f"   Carga {c_id} - Transportadora Código: {c_val['transportadora_codigo']}")
            for r in c_val["remessas"]:
                print(f"     Remessa: {r['remessa']} | Unidade: {r['unidade_medida']} | Lotes: {len(r['lotes'])}")
    except Exception as e:
        print(f"❌ Erro ao carregar dados do SharePoint: {e}")
        sys.exit(1)
        
    # 2. Conecta ao SAP GUI
    session = conectar_sap()
    if not session:
        print("❌ Não foi possível conectar ao SAP GUI.")
        sys.exit(1)
        
    # 3. Execução das etapas (Descomente a linha que deseja testar)
    
    # Inicializa o status das etapas para evitar erro de assinatura
    status_etapas = {}
    for c_id, c_val in dados.items():
        for r_val in c_val["remessas"]:
            status_etapas[r_val["remessa"]] = {
                "basico": "pending",
                "picking": "pending",
                "sm": "pending"
            }

    # Etapa 1: Atualização Básica
    print("\n🚀 Rodando Etapa 1: Atualização Básica...")
    #EntrepostoProcessador.rodar_atualizar_basico(session, dados, status_etapas)
    
    # Etapa 2: Picking
    # print("\n🚀 Rodando Etapa 2: Picking...")
    EntrepostoProcessador.rodar_picking(session, dados, {}, status_etapas)
    
    # Etapa 3: SM / Transportadora
    # print("\n🚀 Rodando Etapa 3: SM / Transportadora...")
    # EntrepostoProcessador.rodar_sm(session, dados, status_etapas)
    
    print("\n🏁 Fim da execução de depuração.")
