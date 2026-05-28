import os
import tempfile
import pandas as pd
from datetime import datetime
from src.utils.common import log_sys
from src.utils.sap_utils import conectar_sap
from src.estoque.vl32 import gerar_relatorios
from src.estoque.co01 import executar_co01_processo
from src.estoque.migo import executar_migo_zp1, executar_transferencia_migo
from src.estoque.prdi import executar_prdi

def consultar_cs15(session, semi_acabado):
    """Executa a pesquisa reversa na CS15 para obter o item ACABADO."""
    try:
        session.findById("wnd[0]/tbar[0]/okcd").text = "/ncs15"
        session.findById("wnd[0]").sendVKey(0)
        session.findById("wnd[0]/usr/chkRC29L-DIRKT").selected = True
        session.findById("wnd[0]/usr/ctxtRC29L-MATNR").text = semi_acabado
        session.findById("wnd[0]/tbar[1]/btn[5]").press()
        session.findById("wnd[0]/usr/ctxtRC29L-WERKS").text = "P716"
        session.findById("wnd[0]/tbar[1]/btn[8]").press()
        
        texto_status = session.findById("wnd[0]/sbar").text
        if "Nenhuma" in texto_status or "Nenhum" in texto_status:
            log_sys.write(f"⚠️ Material {semi_acabado} sem roteiro/onde-usado na CS15")
            return None
            
        acabado = session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell").getCellValue(0, "MATNR")
        return acabado.strip()
    except Exception as e:
        log_sys.write(f"❌ Erro na consulta CS15 para {semi_acabado}: {e}")
        return None

def executar_processo_sap_direto(inbound):
    inicio = datetime.now()
    log_sys.write(f"🚀 Iniciando processo integrado direto do SAP para Inbound {inbound}...")
    
    try:
        session = conectar_sap()
        if not session:
            raise Exception("Não foi possível conectar ao SAP GUI ativo.")
        
        # PASSO 1: Extração VL32N e CS15
        log_sys.write("▶️ Extraindo dados da VL32N...")
        df1, df2 = gerar_relatorios(inbound)
        if df1 is None or df2 is None or df1.empty or df2.empty:
            raise Exception("Falha ao extrair dados da transação VL32N.")
        
        semi_acabado = df2['Semi Acabado'].iloc[0]
        log_sys.write(f"🔍 Item Semi-Acabado identificado: {semi_acabado}")
        
        log_sys.write("▶️ Executando consulta reversa na CS15...")
        acabado = consultar_cs15(session, semi_acabado)
        if not acabado:
            raise Exception(f"Não foi possível obter o item ACABADO correspondente para o semi {semi_acabado} via CS15.")
        log_sys.write(f"✅ Item ACABADO retornado pela CS15: {acabado}")
        
        # Populando a coluna ACABADO no df1 e df2
        df1['ACABADO'] = acabado
        df2['ACABADO'] = acabado
        
        # Cálculos requeridos
        peso_total = df1['Peso LIQ'].sum()
        qtd_ucs_unicas = df1['UC'].nunique()
        log_sys.write(f"📊 Peso Líquido Total: {peso_total} | UCs Únicas: {qtd_ucs_unicas}")
        
        # PASSO 2: Criação na CO01
        log_sys.write("▶️ Iniciando criação da ordem na CO01...")
        op_gerada = executar_co01_processo(session, acabado, semi_acabado, peso_total)
        if not op_gerada:
            raise Exception("Falha na criação da OP (CO01).")
        log_sys.write(f"✅ OP Gerada com Sucesso: {op_gerada}")
        
        # Preparação do DataFrame integrado para os passos de MIGO e PRDI
        df_merged = pd.merge(df1, df2, on="UC")
        df_migo_prdi = pd.DataFrame()
        df_migo_prdi['ACABADO'] = df_merged['ACABADO_x']
        df_migo_prdi['LOTE'] = df_merged['lote']
        df_migo_prdi['Peso Líquido'] = df_merged['peso_bob']
        df_migo_prdi['Peso Bruto'] = df_merged['Peso Bruto']
        df_migo_prdi['Nº Bobinas'] = df_merged['nº de bob']
        df_migo_prdi['UC'] = df_merged['UC']
        df_migo_prdi['Peso LIQ'] = df_merged['Peso LIQ']
        
        # Criando planilha Excel temporária para uso das funções existentes
        temp_dir = tempfile.gettempdir()
        caminho_temp_excel = os.path.join(temp_dir, f"temp_processo_sap_{inbound}.xlsx")
        with pd.ExcelWriter(caminho_temp_excel) as writer:
            df_migo_prdi.to_excel(writer, sheet_name="Exportação SAPUI5", index=False)
        log_sys.write(f"📂 Planilha temporária criada em: {caminho_temp_excel}")
        
        # PASSO 3: MIGO ZP1 e 261
        log_sys.write("▶️ Executando movimentos MIGO ZP1 e 261...")
        try:
            if not executar_migo_zp1(caminho_temp_excel, auto=True, op=op_gerada, filtro=acabado):
                raise Exception("Falha nos movimentos MIGO ZP1 / 261.")
            log_sys.write("✅ Movimentos MIGO ZP1 e 261 concluídos com sucesso.")
        except Exception as e:
            raise Exception(f"Erro na etapa MIGO ZP1/261: {e}")
            
        # PASSO 4: MIGO 411 (Transferência)
        log_sys.write("▶️ Executando movimento de transferência MIGO 411...")
        try:
            if not executar_transferencia_migo(caminho_temp_excel, auto=True, filtro=acabado):
                raise Exception("Falha no movimento de transferência MIGO 411.")
            
            # Capturar a Inbound gerada no rodapé se aplicável
            inbound_gerada = ""
            try:
                import time
                for _ in range(5):
                    msg_inbound = session.findById("wnd[0]/sbar").text
                    if msg_inbound and any(c.isdigit() for c in msg_inbound):
                        inbound_temp = "".join(filter(str.isdigit, msg_inbound))
                        inbound_gerada = inbound_temp
                        log_sys.write(f"✅ Inbound Gerada/Lida na transferência: {inbound_gerada} (Msg: {msg_inbound})")
                        break
                    time.sleep(1)
            except Exception as e:
                log_sys.write(f"⚠️ Erro ao tentar ler sbar da MIGO 411: {e}")
        except Exception as e:
            raise Exception(f"Erro na etapa MIGO 411: {e}")
            
        # PASSO 5: Processamento do PRDI
        log_sys.write("▶️ Iniciando processamento do PRDI...")
        try:
            # A quantidade de lotes é a contagem de lotes únicos
            quantidade_lotes = df_migo_prdi['LOTE'].nunique()
            log_sys.write(f"📊 Quantidade de lotes (lotes únicos): {quantidade_lotes}")
            
            # nUcs_unicas é a quantidade de UCs únicas
            log_sys.write(f"📊 Quantidade de UCs únicas para str(nUcs): {qtd_ucs_unicas}")
            
            if not executar_prdi(caminho_temp_excel, auto=True, inbound=inbound_gerada, filtro=acabado, tamanho=quantidade_lotes, nUcs_unicas=qtd_ucs_unicas):
                raise Exception("Falha no processamento do PRDI.")
            log_sys.write("✅ Processamento do PRDI concluído com sucesso.")
        except Exception as e:
            raise Exception(f"Erro na etapa PRDI: {e}")
            
        # Limpar arquivo temporário
        try:
            os.remove(caminho_temp_excel)
        except:
            pass
            
        log_sys.write(f"🎉 Processo concluído com sucesso em {datetime.now() - inicio}!")
        return True
        
    except Exception as e:
        log_sys.write(f"❌ Ocorreu uma falha no processo: {e}")
        return False

def processo_estoque_sem_planilha(vl32_list, ponto_partida, op_global, migo_global, lote_id=None):
    import src.utils.db as db
    inicio = datetime.now()
    log_sys.write(f"🚀 Iniciando processo integrado 'Sem Planilha'...")
    
    if not lote_id:
        lote_id = db.criar_novo_lote("SEM_PLANILHA")
        itens = []
        for v in vl32_list:
            vl32_val = v['val'] if isinstance(v, dict) else v
            item_id = db.inserir_item(lote_id, material=vl32_val, peso=0.0)
            db.atualizar_item(item_id, inbound=vl32_val, op=op_global)
            itens.append({
                'id': item_id, 'material': vl32_val, 'peso': 0.0, 'acabado': '',
                'op': op_global, 'inbound': vl32_val, 'status_etapa': 'PENDENTE'
            })
    else:
        log_sys.write(f"🔄 Retomando Lote {lote_id}...")
        db_itens = db.buscar_itens_por_lote(lote_id)
        itens = []
        for i in db_itens:
            itens.append({
                'id': i['id'], 'material': i['material'], 'peso': i['peso'],
                'acabado': '',
                'op': i['op'] if i['op'] else op_global,
                'inbound': i['inbound'],
                'inbound_gerada': i.get('inbound_gerada'),
                'status_etapa': i['status_etapa']
            })

    relatorio = []

    for item in itens:
        item_id = item['id']
        vl32_inbound = item['inbound']
        op = item['op']
        status = item['status_etapa']
        
        if status == 'CONCLUIDO':
            relatorio.append({'VL32': vl32_inbound, 'OP': op, 'Status': 'Já estava Concluído'})
            continue
            
        inicio_item = datetime.now()
        try:
            session = conectar_sap()
            if not session: raise Exception("Sem conexão SAP")
            log_sys.write(f"\n🔄 Processando VL32: {vl32_inbound} | Etapa Atual: {status}")

            df1, df2 = None, None
            caminho_temp_excel = None
            
            log_sys.write("▶️ Extraindo dados da VL32N...")
            df1, df2 = gerar_relatorios(vl32_inbound)
            if df1 is None or df2 is None or df1.empty or df2.empty:
                raise Exception("Falha ao extrair dados da transação VL32N.")
            
            semi_acabado = df2['Semi Acabado'].iloc[0]
            log_sys.write(f"🔍 Item Semi-Acabado identificado: {semi_acabado}")
            db.atualizar_item(item_id, material=semi_acabado)
            
            log_sys.write("▶️ Executando consulta reversa na CS15...")
            acabado = consultar_cs15(session, semi_acabado)
            if not acabado:
                raise Exception(f"Não foi possível obter o item ACABADO correspondente para o semi {semi_acabado} via CS15.")
            log_sys.write(f"✅ Item ACABADO retornado pela CS15: {acabado}")
            
            df1['ACABADO'] = acabado
            df2['ACABADO'] = acabado
            peso_total = df1['Peso LIQ'].sum()
            qtd_ucs_unicas = df1['UC'].nunique()
            
            db.atualizar_item(item_id, peso=float(peso_total))
            
            df_merged = pd.merge(df1, df2, on="UC")
            df_migo_prdi = pd.DataFrame()
            df_migo_prdi['ACABADO'] = df_merged['ACABADO_x']
            df_migo_prdi['LOTE'] = df_merged['lote']
            df_migo_prdi['Peso Líquido'] = df_merged['peso_bob']
            df_migo_prdi['Peso Bruto'] = df_merged['Peso Bruto']
            df_migo_prdi['Nº Bobinas'] = df_merged['nº de bob']
            df_migo_prdi['UC'] = df_merged['UC']
            df_migo_prdi['Peso LIQ'] = df_merged['Peso LIQ']
            
            temp_dir = tempfile.gettempdir()
            caminho_temp_excel = os.path.join(temp_dir, f"temp_processo_sap_{vl32_inbound}.xlsx")
            with pd.ExcelWriter(caminho_temp_excel) as writer:
                df_migo_prdi.to_excel(writer, sheet_name="Exportação SAPUI5", index=False)
            
            if ponto_partida <= 1 and status in ['PENDENTE', 'ERRO_CO01', 'ERRO_GERAL']:
                log_sys.write(f"▶️ Executando CO01 para {semi_acabado}")
                op_gerada = executar_co01_processo(session, acabado, semi_acabado, peso_total)
                if not op_gerada:
                    raise Exception("Falha na criação da OP (CO01)")
                op = op_gerada
                db.atualizar_item(item_id, op=op, status_etapa='CO01_OK')
                status = 'CO01_OK'
                log_sys.write(f"✅ OP Criada/Salva: {op}")

            if ponto_partida <= 2 and status in ['PENDENTE', 'CO01_OK', 'ERRO_MIGO_ZP1', 'ERRO_GERAL']:
                if not op: raise Exception("OP não informada para a etapa MIGO ZP1")
                log_sys.write(f"▶️ Executando MIGO ZP1 para {semi_acabado} com OP {op}")
                if not executar_migo_zp1(caminho_temp_excel, auto=True, op=op, filtro=acabado):
                    raise Exception("Falha no Apontamento (MIGO ZP1 / 261)")
                db.atualizar_item(item_id, status_etapa='MIGO_ZP1_OK')
                status = 'MIGO_ZP1_OK'

            if ponto_partida <= 3 and status in ['PENDENTE', 'CO01_OK', 'MIGO_ZP1_OK', 'ERRO_MIGO_TRANSF', 'ERRO_GERAL']:
                log_sys.write(f"▶️ Executando MIGO Transferência (411) para {semi_acabado}")
                if not executar_transferencia_migo(caminho_temp_excel, auto=True, filtro=acabado):
                    raise Exception("Falha na Transferência (MIGO 411)")
                
                inbound_gerada = ""
                try:
                    import time
                    for _ in range(5):
                        msg_inbound = session.findById("wnd[0]/sbar").text
                        if msg_inbound and any(c.isdigit() for c in msg_inbound):
                            inbound_temp = "".join(filter(str.isdigit, msg_inbound))
                            inbound_gerada = inbound_temp
                            log_sys.write(f"✅ Inbound Gerada/Lida na transferência: {inbound_gerada} (Msg: {msg_inbound})")
                            break
                        time.sleep(1)
                except Exception as e:
                    log_sys.write(f"⚠️ Erro ao tentar ler sbar da MIGO 411: {e}")
                
                if inbound_gerada:
                    item['inbound_gerada'] = inbound_gerada
                
                db.atualizar_item(item_id, inbound_gerada=inbound_gerada if inbound_gerada else None, status_etapa='MIGO_TRANSF_OK')
                status = 'MIGO_TRANSF_OK'

            if ponto_partida <= 4 and status in ['PENDENTE', 'CO01_OK', 'MIGO_ZP1_OK', 'MIGO_TRANSF_OK', 'ERRO_PRDI', 'ERRO_GERAL']:
                prdi_inbound = migo_global if migo_global else item.get('inbound_gerada') or item.get('inbound', vl32_inbound)
                log_sys.write(f"▶️ Executando PRDI para {semi_acabado} com Inbound {prdi_inbound}")
                quantidade_lotes = df_migo_prdi['LOTE'].nunique()
                if not executar_prdi(caminho_temp_excel, auto=True, inbound=prdi_inbound, filtro=acabado, tamanho=quantidade_lotes, nUcs_unicas=qtd_ucs_unicas):
                    raise Exception("Falha PRDI")
                
                db.atualizar_item(item_id, status_etapa='CONCLUIDO')
                status = 'CONCLUIDO'

            relatorio.append({'VL32': vl32_inbound, 'OP': op, 'Status': 'Concluído'})

        except Exception as e:
            msg_erro = str(e)
            log_sys.write(f"❌ FALHA NO ITEM {vl32_inbound}: {msg_erro}")
            log_sys.write("⚠️ O processo deste item foi abortado. Os outros continuarão.")
            
            if 'CO01' in msg_erro: novo_status = 'ERRO_CO01'
            elif 'ZP1' in msg_erro or '261' in msg_erro: novo_status = 'ERRO_MIGO_ZP1'
            elif 'Transferência' in msg_erro or '411' in msg_erro: novo_status = 'ERRO_MIGO_TRANSF'
            elif 'PRDI' in msg_erro: novo_status = 'ERRO_PRDI'
            else: novo_status = 'ERRO_GERAL'
            
            db.atualizar_item(item_id, status_etapa=novo_status)
            relatorio.append({'VL32': vl32_inbound, 'OP': op, 'Status': f"FALHA: {msg_erro}"})
            
        finally:
            if caminho_temp_excel and os.path.exists(caminho_temp_excel):
                try:
                    os.remove(caminho_temp_excel)
                except:
                    pass
            
            duracao = datetime.now() - inicio_item
            minutos = int(duracao.total_seconds() // 60)
            segundos = int(duracao.total_seconds() % 60)
            tempo_str = f"{minutos}m {segundos}s"
            db.atualizar_item(item_id, tempo=tempo_str)

    db_itens = db.buscar_itens_por_lote(lote_id)
    todos_concluidos = all(i['status_etapa'] == 'CONCLUIDO' for i in db_itens)
    if todos_concluidos:
        db.concluir_lote(lote_id)
        log_sys.write("\n🎉 Lote Concluído com Sucesso e Finalizado no Banco de Dados.")
    else:
        log_sys.write("\n⚠️ Lote finalizado com algumas pendências. Poderá ser retomado depois.")

    log_sys.write("=== RELATÓRIO FINAL ===")
    for r in relatorio:
        log_sys.write(f"VL32/Inbound: {r['VL32']} | OP: {r['OP']} | Status: {r['Status']}")
    
    log_sys.write(f"🏁 Fim: {datetime.now() - inicio}")
