from datetime import datetime
from src.utils.common import log_sys
from src.utils.sap_utils import conectar_sap
from src.utils.excel_utils import ler_excel_universal, valorFloatPy
from src.estoque.co01 import executar_co01_processo
from src.estoque.migo import executar_migo_zp1, executar_transferencia_migo
from src.estoque.prdi import executar_prdi
import src.utils.db as db

def processo_estoque(caminho, ponto_partida=1, op_global=None, inbound_global=None, lote_id=None):
    inicio = datetime.now()
    
    # 1. Obter os dados (lote novo ou retomando)
    if not lote_id:
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
        
        
        lote_id = db.criar_novo_lote(caminho)
        itens = []
        for _, row in df_agrupado.iterrows():
            semi = row['Material']
            peso = row['Peso Líquido']
            acabado = row['ACABADO']
            item_id = db.inserir_item(lote_id, semi, peso)
            itens.append({
                'id': item_id, 'material': semi, 'peso': peso, 'acabado': acabado,
                'op': op_global, 'inbound': inbound_global, 'status_etapa': 'PENDENTE'
            })
    else:
        log_sys.write(f"🔄 Retomando Lote {lote_id}...")
        df = ler_excel_universal(caminho, "Exportação SAPUI5", 0)
        if df is None: return
        df_agrupado = df.groupby('Material').agg({'ACABADO': 'first'}).reset_index()
        acabado_map = dict(zip(df_agrupado['Material'], df_agrupado['ACABADO']))
        
        db_itens = db.buscar_itens_por_lote(lote_id)
        itens = []
        for i in db_itens:
            itens.append({
                'id': i['id'], 'material': i['material'], 'peso': i['peso'],
                'acabado': acabado_map.get(i['material'], ''),
                'op': i['op'] if i['op'] else op_global,
                'inbound': i['inbound'] if i['inbound'] else inbound_global,
                'status_etapa': i['status_etapa']
            })

    relatorio = []

    # 2. Processar cada item
    for item in itens:
        item_id = item['id']
        semi = item['material']
        peso = item['peso']
        acabado = item['acabado']
        op = item['op']
        inbound = item['inbound']
        status = item['status_etapa']
        
        if status == 'CONCLUIDO':
            relatorio.append({'Semi': semi, 'OP': op, 'Inbound': inbound, 'Status': 'Já estava Concluído'})
            continue
            
        try:
            session = conectar_sap()
            if not session: raise Exception("Sem conexão SAP")
            log_sys.write(f"\n🔄 Processando: {acabado} | Semi: {semi} | Etapa Atual: {status}")

            # ETAPA 1: CO01
            if ponto_partida <= 1 and status in ['PENDENTE', 'ERRO_CO01']:
                log_sys.write(f"▶️ Executando CO01 para {semi}")
                op_gerada = executar_co01_processo(session, acabado, semi, peso)
                if not op_gerada:
                    raise Exception("Falha na criação da OP (CO01)")
                op = op_gerada
                db.atualizar_item(item_id, op=op, status_etapa='CO01_OK')
                status = 'CO01_OK'
                log_sys.write(f"✅ OP Criada/Salva: {op}")

            # ETAPA 2: MIGO ZP1
            if ponto_partida <= 2 and status in ['PENDENTE', 'CO01_OK', 'CONSUMO_OK', 'ERRO_MIGO_ZP1']:
                if not op: raise Exception("OP não informada para a etapa MIGO ZP1")
                log_sys.write(f"▶️ Executando MIGO ZP1 para {semi} com OP {op}")
                if not executar_migo_zp1(caminho, auto=True, op=op, filtro=acabado, item_id=item_id):
                    raise Exception("Falha no Apontamento (MIGO ZP1)")
                db.atualizar_item(item_id, status_etapa='MIGO_ZP1_OK')
                status = 'MIGO_ZP1_OK'

            # ETAPA 3: MIGO Transferência
            if ponto_partida <= 3 and status in ['PENDENTE', 'CO01_OK', 'MIGO_ZP1_OK', 'APONTAMENTO_OK', 'ERRO_MIGO_TRANSF']:
                log_sys.write(f"▶️ Executando MIGO Transferência para {semi}")
                if not executar_transferencia_migo(caminho, auto=True, filtro=acabado):
                    raise Exception("Falha na Transferência (MIGO 411/311)")
                
                # Pegar Inbound se aplicável
                try:
                    msg_inbound = session.findById("wnd[0]/sbar").text
                    inbound_temp = "".join(filter(str.isdigit, msg_inbound))
                    if inbound_temp: 
                        inbound = inbound_temp
                        log_sys.write(f"✅ Inbound Lida: {inbound}")
                except:
                    pass
                
                db.atualizar_item(item_id, inbound=inbound, status_etapa='MIGO_TRANSF_OK')
                status = 'MIGO_TRANSF_OK'

            # ETAPA 4: PRDI
            if ponto_partida <= 4 and status in ['PENDENTE', 'CO01_OK', 'MIGO_ZP1_OK', 'MIGO_TRANSF_OK', 'ERRO_PRDI']:
                if not inbound: raise Exception("Inbound não informada/gerada para PRDI")
                log_sys.write(f"▶️ Executando PRDI para {semi} com Inbound {inbound}")
                if not executar_prdi(caminho, auto=True, inbound=inbound, filtro=acabado):
                    raise Exception("Falha PRDI")
                
                db.atualizar_item(item_id, status_etapa='CONCLUIDO')
                status = 'CONCLUIDO'

            relatorio.append({'Semi': semi, 'OP': op, 'Inbound': inbound, 'Status': 'Concluído'})

        except Exception as e:
            msg_erro = str(e)
            log_sys.write(f"❌ FALHA NO ITEM {acabado}: {msg_erro}")
            log_sys.write("⚠️ O processo deste item foi abortado. Os outros continuarão.")
            
            # Definir erro exato
            if 'CO01' in msg_erro: novo_status = 'ERRO_CO01'
            elif 'ZP1' in msg_erro: novo_status = 'ERRO_MIGO_ZP1'
            elif 'Transferência' in msg_erro: novo_status = 'ERRO_MIGO_TRANSF'
            elif 'PRDI' in msg_erro: novo_status = 'ERRO_PRDI'
            else: novo_status = 'ERRO_GERAL'
            
            db.atualizar_item(item_id, status_etapa=novo_status)
            relatorio.append({'Semi': semi, 'OP': op, 'Inbound': inbound, 'Status': f"FALHA: {msg_erro}"})

    # Verificar se todos os itens foram concluidos
    db_itens = db.buscar_itens_por_lote(lote_id)
    todos_concluidos = all(i['status_etapa'] == 'CONCLUIDO' for i in db_itens)
    if todos_concluidos:
        db.concluir_lote(lote_id)
        log_sys.write("\n🎉 Lote Concluído com Sucesso e Finalizado no Banco de Dados.")
    else:
        log_sys.write("\n⚠️ Lote finalizado com algumas pendências. Poderá ser retomado depois.")

    # Relatório Final
    log_sys.write("=== RELATÓRIO FINAL ===")
    for r in relatorio:
        log_sys.write(f"Item: {r['Semi']} | OP: {r['OP']} | Inbound: {r['Inbound']} | Status: {r['Status']}")
    
    log_sys.write(f"🏁 Fim: {datetime.now() - inicio}")
