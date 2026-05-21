from datetime import datetime
from src.utils.common import log_sys
from src.utils.sap_utils import conectar_sap
from src.utils.excel_utils import ler_excel_universal, valorFloatPy
from src.estoque.msc import executar_msc1n
from src.estoque.migo import executar_migo_zp1, executar_transferencia_migo
from src.estoque.prdi import executar_prdi

def brid(caminho):
    inicio = datetime.now()
    df = ler_excel_universal(caminho, "BRID", 0)
    if df is None: return

    df['Peso Líquido'] = df['Peso Líquido'].apply(valorFloatPy)
    
    df_agrupado = df.groupby('OP').agg({
        'Peso Líquido': 'sum',
        'ACABADO': 'first'
    }).reset_index()

    log_sys.write("\n--- Resumo por Item ---")
    log_sys.write(df_agrupado.to_string())
    
    executar_msc1n(df)

    relCo01 = []

    for _, row in df_agrupado.iterrows():
        peso = row['Peso Líquido']
        acabado = row['ACABADO']
        op = row["OP"]
        inbound = "Não gerado"
        try:
                        
            session = conectar_sap()
            if not session: raise Exception("Sem conexão SAP")


            if not executar_migo_zp1(df, auto=True, op=op, filtro=acabado):
                raise Exception("Falha no Apontamento (MIGO ZP1)") 
            
            input("Aguardando DU: ") # This might be printed normally to allow console input

            if not executar_transferencia_migo(df, auto=True, filtro=acabado):
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
                if not executar_prdi(df, auto=True, inbound=inbound, filtro=acabado):
                    inbound += " (Falha PRDI)"

            # Sucesso
            relCo01.append({
                'Material': acabado, 'Peso': peso, 'OP': op, 'Inbound': inbound, 'Status': 'Concluído'
            })
        except Exception as e:
            log_sys.write(f"❌ FALHA NO ITEM {acabado}: {e}")
            log_sys.write("⚠️ Pulando etapas restantes deste item...")
            
            relCo01.append({
                'Material': acabado,'Peso': peso, 'OP': op, 'Inbound': inbound, 'Status': f"FALHA: {str(e)}"
            })
            
    agora = datetime.now().strftime("%d-%m-%Y_%H-%M")
    nome_arquivo = f"Relatorio_SAP_{agora}.xlsx"

    df.to_excel(nome_arquivo, index=False)

    log_sys.write("\n=== RELATÓRIO FINAL ===")
    for item in relCo01:
        log_sys.write(f"Item: {item['Material']} | OP: {item['OP']} | Inbound: {item['Inbound']} | Status: {item['Status']}")
    
    log_sys.write(f"🏁 Fim: {datetime.now() - inicio}")
