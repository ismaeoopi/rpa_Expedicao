from datetime import datetime
from src.utils.common import log_sys
from src.utils.sap_utils import conectar_sap
from src.utils.excel_utils import ler_excel_universal, valorFloatPy
from src.estoque.co01 import executar_co01_processo
from src.estoque.migo import executar_migo_zp1, executar_transferencia_migo
from src.estoque.prdi import executar_prdi

def processo_completo(caminho):
    inicio = datetime.now()
    df = ler_excel_universal(caminho, "Exportação SAPUI5", 0)
    if df is None: return

    log_sys.write("🔄 Processando e convertendo pesos...")
    df['Peso Líquido'] = df['Peso Líquido'].apply(valorFloatPy)
    
    df_agrupado = df.groupby('Material').agg({
        'Peso Líquido': 'sum',
        'ACABADO': 'first'
    }).reset_index()

    log_sys.write("\n--- Resumo por Item ---")
    log_sys.write(df_agrupado.to_string())

    relCo01 = []

    for _, row in df_agrupado.iterrows():
        semi = row['Material']
        peso = row['Peso Líquido']
        acabado = row['ACABADO']
        op = "Não gerada"
        inbound = "Não gerado"

        try:
            session = conectar_sap()
            if not session: raise Exception("Sem conexão SAP")

            log_sys.write(f"🔄 Processando: {acabado} | Semi: {semi}")
            
            # 1. CO01
            op = executar_co01_processo(session, acabado, semi, peso)
            if not op:
                raise Exception("Falha na criação da OP (CO01)") # Força parada
            
            log_sys.write(f"✅ OP Criada: {op}")
            
            # 2. MIGO ZP1 (Apontamento)
            if not executar_migo_zp1(caminho, auto=True, op=op, filtro=acabado):
                raise Exception("Falha no Apontamento (MIGO ZP1)") 
            
            # 3. MIGO Transferência
            if not executar_transferencia_migo(caminho, auto=True, filtro=acabado):
                raise Exception("Falha na Transferência (MIGO 411)")

            # Pega Inbound
            msg_inbound = session.findById("wnd[0]/sbar").text
            inbound_temp = "".join(filter(str.isdigit, msg_inbound))
            
            if not inbound_temp:
                 inbound = "Erro Inbound"
            else:
                 inbound = inbound_temp

            # 4. PRDI
            if inbound != "Erro Inbound":
                if not executar_prdi(caminho, auto=True, inbound=inbound, filtro=acabado):
                     inbound += " (Falha PRDI)"

            # Sucesso
            relCo01.append({
                'Semi': semi, 'Peso': peso, 'OP': op, 'Inbound': inbound, 'Status': 'Concluído'
            })

        except Exception as e:
            log_sys.write(f"❌ FALHA NO ITEM {acabado}: {e}")
            log_sys.write("⚠️ Pulando etapas restantes deste item...")
            
            relCo01.append({
                'Semi': semi, 'Peso': peso, 'OP': op, 'Inbound': inbound, 'Status': f"FALHA: {str(e)}"
            })

    # Relatório Final
    log_sys.write("\n=== RELATÓRIO FINAL ===")
    for item in relCo01:
        log_sys.write(f"Item: {item['Semi']} | OP: {item['OP']} | Inbound: {item['Inbound']} | Status: {item['Status']}")
    
    log_sys.write(f"🏁 Fim: {datetime.now() - inicio}")
