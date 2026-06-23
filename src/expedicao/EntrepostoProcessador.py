import re
import time
import pandas as pd
from src.utils.common import log_sys
from src.utils.sap_utils import conectar_sap, fechar_popups
from src.utils.excel_utils import valorFloatexcel
from Entreposto import carregar_planilhas_em_memoria, encontrar_coluna, converter_para_float
import src.utils.db as db

def esperar_id(session, elementos_id, timeout=10):
    """Espera até encontrar um dos IDs informados."""
    end = time.time() + timeout
    while time.time() < end:
        for eid in elementos_id:
            try:
                if session.findById(eid, False):
                    return True
            except:
                pass
        time.sleep(0.2)
    return False

def fechar_popups_VL02N(session):
    try:
        while True:
            active_window = session.ActiveWindow
            title = active_window.Text.lower()
            if "informação" in title or "information" in title:
                active_window.findById("tbar[0]/btn[0]").press()
                time.sleep(0.3)
            elif "credit" in title or "crédito" in title:
                active_window.findById("tbar[0]/btn[0]").press()
                time.sleep(0.3)
            else:
                break
    except:
        pass

def obter_dados_etapas(entreposto_nome, cargas_selecionadas):
    """
    Carrega as planilhas do SharePoint e extrai as informações estruturadas
    necessárias para processar as cargas/remessas selecionadas.
    """
    log_sys.write(f"📊 Carregando dados para processar as cargas selecionadas: {', '.join(cargas_selecionadas)}")
    dados = carregar_planilhas_em_memoria(entreposto_nome)
    df_cargas = dados.get("Planilha de Cargas")
    df_estoque = dados.get("Planilha de Estoque")
    
    if df_cargas is None or df_estoque is None:
        raise ValueError("Não foi possível carregar as planilhas de Cargas e Estoque.")
        
    # Promover cabeçalho das Cargas
    colunas_norm = [str(c).upper().replace(" ", "").replace("_", "") for c in df_cargas.columns]
    tem_headers_ja = any(n in colunas_norm for n in ["REMESSAPICKING", "SEQ", "NOCARGA", "CARGA"])
    if not tem_headers_ja:
        linha_cabecalho_idx = -1
        for idx in range(min(5, len(df_cargas))):
            valores_linha = [str(x).upper() for x in df_cargas.iloc[idx].values]
            if any("REMESSA / PICKING" in v or "REMESSA/PICKING" in v or "SEQ" in v or "CARGA" in v for v in valores_linha):
                linha_cabecalho_idx = idx
                break
        if linha_cabecalho_idx != -1:
            novas_colunas = [str(col_val).strip() if not pd.isna(col_val) else str(df_cargas.columns[col_idx]) for col_idx, col_val in enumerate(df_cargas.iloc[linha_cabecalho_idx])]
            df_cargas.columns = novas_colunas
            df_cargas = df_cargas.iloc[linha_cabecalho_idx + 1:].reset_index(drop=True)
            
    # Promover cabeçalho do Estoque
    colunas_est_norm = [str(c).upper().replace(" ", "").replace("_", "") for c in df_estoque.columns]
    tem_headers_est_ja = any(n in colunas_est_norm for n in ["NOCARGA", "CARGA", "MATERIAL", "LOTE"])
    if not tem_headers_est_ja:
        linha_cabecalho_est_idx = -1
        for idx in range(min(5, len(df_estoque))):
            valores_linha = [str(x).upper() for x in df_estoque.iloc[idx].values]
            if any("CARGA" in v or "MATERIAL" in v or "LOTE" in v for v in valores_linha):
                linha_cabecalho_est_idx = idx
                break
        if linha_cabecalho_est_idx != -1:
            novas_colunas = [str(col_val).strip() if not pd.isna(col_val) else str(df_estoque.columns[col_idx]) for col_idx, col_val in enumerate(df_estoque.iloc[linha_cabecalho_est_idx])]
            df_estoque.columns = novas_colunas
            df_estoque = df_estoque.iloc[linha_cabecalho_est_idx + 1:].reset_index(drop=True)

    # Identificar colunas cruciais
    col_cargas_n_carga = encontrar_coluna(df_cargas, ["Nº DA CARGA", "N° DA CARGA", "Nº CARGA", "N° CARGA", "CARGA", "NUM CARGA"], "Planilha de Cargas")
    col_cargas_remessa = encontrar_coluna(df_cargas, ["REMESSA", "REMESSA / PICKING", "REMESSA/PICKING", "STATUS"], "Planilha de Cargas")
    col_cargas_transp = encontrar_coluna(df_cargas, ["TRANSP.", "TRANSPORTADORA", "TRANSP", "TRANSPORT"], "Planilha de Cargas")
    col_cargas_peso_liq = encontrar_coluna(df_cargas, ["PESO LIQ", "PESO LIQUIDO", "P LIQ", "PESO LIQ. DADOS", "NET WEIGHT"], "Planilha de Cargas")
    col_cargas_pllt = encontrar_coluna(df_cargas, ["PLLT", "PALETE", "PALETES", "QTD PALETES", "PALLETS"], "Planilha de Cargas")

    col_estoque_n_carga = encontrar_coluna(df_estoque, ["Nº CARGA", "N° CARGA", "CARGA", "NUM CARGA"], "Planilha de Estoque")
    col_estoque_remessa = encontrar_coluna(df_estoque, ["REMESSA", "REMESSA/PICKING", "REMESSA / PICKING", "DELIVERY", "REMESSA SAP", "REMESSAPICKING", "Nº REMESSA", "N° REMESSA"], "Planilha de Estoque")
    col_estoque_peso_liq = encontrar_coluna(df_estoque, ["PESO LIQUIDO", "PESO LIQ", "NET WEIGHT"], "Planilha de Estoque")
    col_estoque_peso_bruto = encontrar_coluna(df_estoque, ["PESO BRUTO", "GROSS WEIGHT"], "Planilha de Estoque")
    col_estoque_lote = encontrar_coluna(df_estoque, ["LOTE", "LOTES", "BATCH"], "Planilha de Estoque")
    
    # Montar mapa de cargas
    resultado_cargas = {}
    
    # Converter colunas de carga para comparação
    df_cargas[col_cargas_n_carga] = df_cargas[col_cargas_n_carga].astype(str).str.strip()
    if col_estoque_n_carga:
        df_estoque[col_estoque_n_carga] = df_estoque[col_estoque_n_carga].astype(str).str.strip()
        
    for carga_id in cargas_selecionadas:
        # Encontra transportadora na planilha de Cargas
        linhas_carga = df_cargas[df_cargas[col_cargas_n_carga] == carga_id]
        transp_original = ""
        if not linhas_carga.empty and col_cargas_transp:
            transp_original = str(linhas_carga[col_cargas_transp].iloc[0]).strip()
            
        # Extrair código da transportadora
        transp_codigo = ""
        if transp_original:
            match = re.search(r'\((\d+)\)', transp_original)
            if match:
                transp_codigo = match.group(1)
            else:
                transp_codigo = "".join(c for c in transp_original if c.isdigit())
                
        # Procura remessas correspondentes
        remessas_map = {}
        
        # Primeiro tenta carregar do estoque
        linhas_estoque = pd.DataFrame()
        if col_estoque_n_carga and df_estoque is not None:
            linhas_estoque = df_estoque[df_estoque[col_estoque_n_carga] == carga_id]
            
        if not linhas_estoque.empty:
            # Cruzamento com estoque
            for remessa_val, grupo_rem in linhas_estoque.groupby(col_estoque_remessa):
                rem_str = str(remessa_val).strip()
                if rem_str.lower() in ["nan", "", "none"]:
                    continue
                    
                # Peso líquido, bruto, paletes do lote/estoque
                p_liq = sum(grupo_rem[col_estoque_peso_liq].apply(converter_para_float))
                p_bruto = sum(grupo_rem[col_estoque_peso_bruto].apply(converter_para_float))
                plts = len(grupo_rem)
                
                lotes_list = []
                for idx_row, r_row in grupo_rem.iterrows():
                    lote_val = str(r_row.get(col_estoque_lote, "")).strip()
                    if lote_val and lote_val.lower() != "nan":
                        if lote_val.endswith(".0"):
                            lote_val = lote_val[:-2]
                        lotes_list.append({
                            "lote": lote_val,
                            "peso_liq": converter_para_float(r_row.get(col_estoque_peso_liq, 0)),
                            "peso_bruto": converter_para_float(r_row.get(col_estoque_peso_bruto, 0))
                        })

                remessas_map[rem_str] = {
                    "remessa": rem_str,
                    "peso_liquido": round(p_liq, 3),
                    "peso_bruto": round(p_bruto, 3),
                    "qtd_paletes": plts,
                    "unidade_medida": "KG",  # Padrão
                    "lotes": lotes_list
                }
        else:
            # Não existe no estoque, tenta pegar das Cargas diretamente
            for idx, row in linhas_carga.iterrows():
                rem_str = str(row.get(col_cargas_remessa, "")).strip()
                if rem_str.lower() in ["nan", "", "none"]:
                    continue
                p_liq = converter_para_float(row.get(col_cargas_peso_liq, 0))
                plts = int(converter_para_float(row.get(col_cargas_pllt, 0)))
                
                remessas_map[rem_str] = {
                    "remessa": rem_str,
                    "peso_liquido": round(p_liq, 3),
                    "peso_bruto": "-",
                    "qtd_paletes": plts,
                    "unidade_medida": "KG",
                    "lotes": []
                }
                
        resultado_cargas[carga_id] = {
            "carga": carga_id,
            "transportadora_codigo": transp_codigo,
            "remessas": list(remessas_map.values())
        }
        
    return resultado_cargas

def rodar_atualizar_basico(session, dados_cargas, status_etapas, remessas_a_processar=None):
    log_sys.write("=== [Passo 1] Iniciando Atualização Básica (VL02N) ===")
    for carga_id, c_info in dados_cargas.items():
        for rem_info in c_info["remessas"]:
            remessa = rem_info["remessa"]
            if remessas_a_processar is not None and remessa not in remessas_a_processar:
                continue
            peso_liq = rem_info["peso_liquido"]
            paletes = rem_info["qtd_paletes"]
            
            log_sys.write(f"🚚 Processando Remessa Básica: {remessa} (Peso: {peso_liq} | Paletes: {paletes})")
            status_etapas[remessa]["basico"] = "running"
            try:
                # Transação VL02N
                session.findById("wnd[0]/tbar[0]/okcd").text = "/nvl02n"
                session.findById("wnd[0]").sendVKey(0)
                
                # Aguarda a tela inicial carregar
                if not esperar_id(session, ["wnd[0]/usr/ctxtLIKP-VBELN"]):
                    raise Exception("Tela inicial da transação VL02N não carregou.")
                    
                session.findById("wnd[0]/usr/ctxtLIKP-VBELN").text = remessa
                session.findById("wnd[0]").sendVKey(0)
                time.sleep(0.5)
                fechar_popups_VL02N(session)
                
                # Verificar se o picking já está concluído
                session.findById(r"wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\02").select()
                picking = session.findById(r"wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\02/ssubSUBSCREEN_BODY:SAPMV50A:1104/ctxtVBUK-KOSTK").text.strip()
                if picking == "C":
                    log_sys.write(f"ℹ️ Remessa {remessa} já possui Picking completo (C). Marcando básico e picking como concluídos.")
                    status_etapas[remessa]["basico"] = "success"
                    status_etapas[remessa]["picking"] = "success"
                    session.findById("wnd[0]/tbar[0]/btn[3]").press()
                    time.sleep(0.5)
                    continue
                
                # Aguarda e seleciona aba de Item Overview
                overview_tab_id = "wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\01"
                if not esperar_id(session, [overview_tab_id]):
                    raise Exception("Tela de Overview de Remessas não carregou.")
                    
                session.findById(overview_tab_id).select()
                time.sleep(0.5)
                
                # Aguarda o campo de unidade de medida carregar
                uom_field_id = (
                    "wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\01"
                    "/ssubSUBSCREEN_BODY:SAPMV50A:1102/"
                    "tblSAPMV50ATC_LIPS_OVER/ctxtLIPS-VRKME[3,0]"
                )
                if not esperar_id(session, [uom_field_id]):
                    raise Exception("Campo de Unidade de Medida (UOM) não carregou a tempo.")
                
                # Obter unidade direto da tela do SAP
                unidade = session.findById(uom_field_id).text.strip().upper()
                log_sys.write(f"ℹ️ Unidade identificada no SAP para a remessa {remessa}: {unidade}")
                
                rem_info["unidade_medida"] = unidade
                
                peso_liq_formatado = valorFloatexcel(peso_liq)
                paletes_formatado = str(paletes)
                
                if unidade == "KG":
                    # Preenche na tela inicial mesmo
                   
                    session.findById(r"wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\01/ssubSUBSCREEN_BODY:SAPMV50A:1102/tblSAPMV50ATC_LIPS_OVER/txtLIPSD-G_LFIMG[2,0]").text = peso_liq_formatado
                    session.findById("wnd[0]").sendVKey(0)
                    fechar_popups_VL02N(session)
                else:
                    # Entrar na linha do item (Double click na primeira linha da tabela)
                    log_sys.write(f"ℹ️ Item não é KG (Unidade: {unidade}). Entrando na linha do item...")
                    session.findById("wnd[0]").sendVKey(2)
                    time.sleep(0.5)
                    
                    # Seleciona a aba Dados Gerais do item
                    session.findById(r"wnd[0]/usr/tabsTAXI_TABSTRIP_ITEM/tabpT\04").select()
                    time.sleep(0.3)
                    
                    # Preenche quantidade e unidade
                    session.findById(r"wnd[0]/usr/tabsTAXI_TABSTRIP_ITEM/tabpT\04/ssubSUBSCREEN_BODY:SAPMV50A:3106/txtLIPS-BRGEW").text = peso_liq_formatado
                    session.findById(r"wnd[0]/usr/tabsTAXI_TABSTRIP_ITEM/tabpT\04/ssubSUBSCREEN_BODY:SAPMV50A:3106/txtLIPS-NTGEW").text = peso_liq_formatado
                    session.findById("wnd[0]").sendVKey(0)
                    time.sleep(0.3)
                    
                    # Volta para a tela de Overview
                    session.findById("wnd[0]/tbar[0]/btn[3]").press()
                    time.sleep(0.5)
                
                # Preenche paletes
                if paletes_formatado and paletes_formatado != "0":
                    session.findById(
                        "wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\01"
                        "/ssubSUBSCREEN_BODY:SAPMV50A:1102/"
                        "txtLIKP-ANZPK"
                    ).text = paletes_formatado
                    session.findById("wnd[0]").sendVKey(0)
                
                # Salvar
                session.findById("wnd[0]/tbar[0]/btn[11]").press()
                time.sleep(0.5)
                fechar_popups_VL02N(session)
                
                status_etapas[remessa]["basico"] = "success"
                log_sys.write(f"✅ Informações básicas da remessa {remessa} salvas com sucesso.")
            except Exception as e:
                status_etapas[remessa]["basico"] = "error"
                log_sys.write(f"❌ Erro básico na remessa {remessa}: {e}")

def rodar_picking(session, dados_cargas, multiplos_custom, status_etapas, remessas_a_processar=None):
    log_sys.write("=== [Passo 2] Iniciando Picking (VL02N) ===")
    for carga_id, c_info in dados_cargas.items():
        for rem_info in c_info["remessas"]:
            remessa = rem_info["remessa"]
            if remessas_a_processar is not None and remessa not in remessas_a_processar:
                continue
            
            # Se o picking já está concluído, pula
            if status_etapas.get(remessa, {}).get("picking") == "success":
                log_sys.write(f"⏭️ Ignorando Picking para a remessa {remessa} pois já está concluído.")
                continue

            # Se a etapa básica desta remessa falhou anteriormente, pula
            if status_etapas.get(remessa, {}).get("basico") == "error":
                log_sys.write(f"⏭️ Ignorando Picking para a remessa {remessa} pois a Atualização Básica falhou.")
                continue
                
            lotes = rem_info["lotes"]
            
            log_sys.write(f"🚚 Processando Picking da Remessa: {remessa} (Lotes: {len(lotes)})")
            status_etapas[remessa]["picking"] = "running"
            
            if not lotes:
                status_etapas[remessa]["picking"] = "error"
                log_sys.write(f"⚠️ Sem lotes para processar o picking da remessa {remessa}. Certifique-se de que a carga existe no Estoque.")
                continue
                
            try:
                # Transação VL02N
                session.findById("wnd[0]/tbar[0]/okcd").text = "/nvl02n"
                session.findById("wnd[0]").sendVKey(0)
                
                if not esperar_id(session, ["wnd[0]/usr/ctxtLIKP-VBELN"]):
                    raise Exception("Tela inicial da transação VL02N não carregou.")
                    
                session.findById("wnd[0]/usr/ctxtLIKP-VBELN").text = remessa
                session.findById("wnd[0]").sendVKey(0)
                time.sleep(0.5)
                fechar_popups_VL02N(session)
                
                # Verificar se o picking já está concluído
                session.findById(r"wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\02").select()
                picking = session.findById(r"wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\02/ssubSUBSCREEN_BODY:SAPMV50A:1104/ctxtVBUK-KOSTK").text.strip()
                if picking == "C":
                    log_sys.write(f"ℹ️ Remessa {remessa} já possui Picking completo (C). Marcando picking como concluído.")
                    status_etapas[remessa]["picking"] = "success"
                    session.findById("wnd[0]/tbar[0]/btn[3]").press()
                    time.sleep(0.5)
                    continue
                
                # Acessa aba de Item Overview para identificar a unidade diretamente no SAP
                overview_tab_id = "wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\01"
                if not esperar_id(session, [overview_tab_id]):
                    raise Exception("Tela de Overview de Remessas não carregou.")
                session.findById(overview_tab_id).select()
                time.sleep(0.3)
                
                uom_field_id = (
                    "wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\01"
                    "/ssubSUBSCREEN_BODY:SAPMV50A:1102/"
                    "tblSAPMV50ATC_LIPS_OVER/ctxtLIPS-VRKME[3,0]"
                )
                if not esperar_id(session, [uom_field_id]):
                    raise Exception("Campo de Unidade de Medida (UOM) não carregou a tempo.")
                    
                unidade = session.findById(uom_field_id).text.strip().upper()
                log_sys.write(f"ℹ️ Unidade identificada no SAP para o picking da remessa {remessa}: {unidade}")
                
                rem_info["unidade_medida"] = unidade
                
                # Navegar para aba Overview (Picking)
                picking_tab_id = "wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\02"
                session.findById(picking_tab_id).select()
                time.sleep(0.5)
                
                # Identificar o código de material direto do SAP
                material_sap = ""
                try:
                    material_field_id = (
                        "wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\02/"
                        "ssubSUBSCREEN_BODY:SAPMV50A:1104/"
                        "tblSAPMV50ATC_LIPS_PICK/ctxtLIPS-MATNR[1,0]"
                    )
                    material_sap = session.findById(material_field_id).text.strip().upper()
                    log_sys.write(f"ℹ️ Material identificado no SAP para a remessa {remessa}: {material_sap}")
                except Exception as mat_err:
                    log_sys.write(f"⚠️ Não foi possível obter o material direto do SAP: {mat_err}")
                
                # Selecionar a primeira linha e abrir edição de lote
                pick_table_id = (
                    "wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\02/"
                    "ssubSUBSCREEN_BODY:SAPMV50A:1104/"
                    "tblSAPMV50ATC_LIPS_PICK"
                )
                session.findById(pick_table_id).getAbsoluteRow(0).Selected = True
                
                session.findById(
                    "wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\02/"
                    "ssubSUBSCREEN_BODY:SAPMV50A:1104/"
                    "subSUBSCREEN_ICONBAR:SAPMV50A:1708/btnBT_CHSP_T"
                ).press()
                time.sleep(0.5)
                
                # Preencher lote & peso
                scroll = 1
                for idx, lote_item in enumerate(lotes):
                    lote_cod = lote_item["lote"]
                    p_liq = lote_item["peso_liq"]
                    
                    if unidade != "KG":
                        val_custom = None
                        if material_sap:
                            val_custom = db.obter_multiplicador_por_material(material_sap)
                            if val_custom is not None:
                                log_sys.write(f"ℹ️ Aplicando multiplicador do banco para o material {material_sap}: {val_custom}")
                                
                        if val_custom is None:
                            key_custom = f"{remessa}"
                            if key_custom in multiplos_custom and multiplos_custom[key_custom]:
                                try:
                                    val_custom = float(multiplos_custom[key_custom])
                                    log_sys.write(f"ℹ️ Aplicando multiplicador manual para remessa {remessa}: {val_custom}")
                                except ValueError:
                                    log_sys.write(f"⚠️ Multiplicador customizado inválido para a remessa {remessa}: {multiplos_custom[key_custom]}")
                                    
                        if val_custom is not None:
                            if len(lotes) > 1:
                                #p_total_estoque = sum(lt["peso_liq"] for lt in lotes)
                                p_liq = val_custom 
                            else:
                                p_liq = val_custom
                                
                    p_liq_formatado = valorFloatexcel(p_liq)
                    
                    log_sys.write(f"    ➡ Lote: {lote_cod} | Qtd/Peso: {p_liq_formatado}")
                    
                    if lote_cod:
                        session.findById(
                            "wnd[0]/usr/tabsTAXI_TABSTRIP_ITEM/tabpT\\03/"
                            "ssubSUBSCREEN_BODY:SAPMV50A:3112/"
                            "tblSAPMV50ATC_LIPS_CHND/ctxtLIPS-CHARG[1,0]"
                        ).text = lote_cod
                    
                    if p_liq_formatado:
                        session.findById(
                            "wnd[0]/usr/tabsTAXI_TABSTRIP_ITEM/tabpT\\03/"
                            "ssubSUBSCREEN_BODY:SAPMV50A:3112/"
                            "tblSAPMV50ATC_LIPS_CHND/txtLIPS-LFIMG[4,0]"
                        ).text = p_liq_formatado
                        
                    session.findById("wnd[0]").sendVKey(0)
                    time.sleep(0.3)
                    
                    scroll += 1
                    session.findById(
                        "wnd[0]/usr/tabsTAXI_TABSTRIP_ITEM/tabpT\\03/"
                        "ssubSUBSCREEN_BODY:SAPMV50A:3112/"
                        "tblSAPMV50ATC_LIPS_CHND"
                    ).verticalScrollbar.Position = scroll
                    time.sleep(0.2)
                
                # Volta para Overview
                session.findById("wnd[0]/tbar[0]/btn[3]").press()
                time.sleep(0.3)
                
                # Seleciona aba Overview (Picking)
                session.findById(picking_tab_id).select()
                time.sleep(0.5)
                
                # Clica em Multi-edição
                multi_id = (
                    "wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\02/"
                    "ssubSUBSCREEN_BODY:SAPMV50A:1104/"
                    "tblSAPMV50ATC_LIPS_PICK/btnRV50A-CHMULT[10,0]"
                )
                session.findById(multi_id).press()
                time.sleep(0.5)
                
                scroll = 1
                session.findById(pick_table_id).verticalScrollbar.Position = scroll
                time.sleep(0.2)
                
                # Copiar qty -> picking e preencher peso bruto original
                for idx, lote_item in enumerate(lotes):
                    p_bruto = lote_item["peso_bruto"]
                    p_bruto_formatado = valorFloatexcel(p_bruto)
                    
                    qty_id  = pick_table_id + "/txtLIPSD-G_LFIMG[5,0]"
                    pick_id = pick_table_id + "/txtLIPSD-PIKMG[7,0]"
                    qtd = session.findById(qty_id).Text
                    session.findById(pick_id).Text = qtd
                    
                    if p_bruto_formatado:
                        br_id = pick_table_id + "/txtLIPS-BRGEW[19,0]"
                        session.findById(br_id).Text = p_bruto_formatado
                        
                    scroll += 1
                    session.findById(pick_table_id).verticalScrollbar.Position = scroll
                    time.sleep(0.2)
                    
                # Confirma
                session.findById("wnd[0]").sendVKey(0)
                time.sleep(0.3)
                session.findById(pick_table_id).verticalScrollbar.Position = 0
                time.sleep(0.2)
                
                # Salvar
                session.findById("wnd[0]/tbar[0]/btn[11]").press()
                time.sleep(0.5)
                fechar_popups_VL02N(session)
                
                status_etapas[remessa]["picking"] = "success"
                log_sys.write(f"✅ Picking e Lotes da remessa {remessa} concluídos com sucesso.")
            except Exception as e:
                status_etapas[remessa]["picking"] = "error"
                log_sys.write(f"❌ Erro no Picking da remessa {remessa}: {e}")

def rodar_sm(session, dados_cargas, status_etapas, remessas_a_processar=None):
    log_sys.write("=== [Passo 3] Iniciando SM / Transportadora (VL02N) ===")
    for carga_id, c_info in dados_cargas.items():
        transp_cod = c_info["transportadora_codigo"]
        
        for rem_info in c_info["remessas"]:
            remessa = rem_info["remessa"]
            if remessas_a_processar is not None and remessa not in remessas_a_processar:
                continue
            
            # Se alguma etapa anterior falhou, pula
            if status_etapas.get(remessa, {}).get("basico") == "error" or status_etapas.get(remessa, {}).get("picking") == "error":
                log_sys.write(f"⏭️ Ignorando SM para a remessa {remessa} pois etapas anteriores falharam.")
                continue
                
            log_sys.write(f"🚚 Atualizando Transportadora da Remessa: {remessa} (Parceiro: {transp_cod or 'vazio'})")
            status_etapas[remessa]["sm"] = "running"
            
            if not transp_cod:
                status_etapas[remessa]["sm"] = "error"
                log_sys.write(f"⚠️ Carga {carga_id} não possui código de transportadora válido. Pulando.")
                continue
                
            try:
                # Transação VL02N
                session.findById("wnd[0]/tbar[0]/okcd").text = "/nvl02n"
                session.findById("wnd[0]").sendVKey(0)
                
                if not esperar_id(session, ["wnd[0]/usr/ctxtLIKP-VBELN"]):
                    raise Exception("Tela inicial da transação VL02N não carregou.")
                    
                session.findById("wnd[0]/usr/ctxtLIKP-VBELN").text = remessa
                session.findById("wnd[0]").sendVKey(0)
                time.sleep(0.5)
                
                # Limites de erro
                sb_text = session.findById("wnd[0]/sbar").text.lower()
                if "não existe" in sb_text or "does not exist" in sb_text:
                    raise Exception(f"Remessa {remessa} não existe no SAP.")
                    
                # Cabeçalho da remessa -> aba parceiros
                session.findById("wnd[0]/tbar[1]/btn[8]").press() # F8 / Header
                time.sleep(0.5)
                
                partner_tab_id = "wnd[0]/usr/tabsTAXI_TABSTRIP_HEAD/tabpT\\08"
                if not esperar_id(session, [partner_tab_id]):
                    raise Exception("Tela de Parceiros do Cabeçalho não carregou.")
                session.findById(partner_tab_id).select() # Aba Parceiros
                time.sleep(0.5)
                
                # Define chave SP e insere transportadora
                tbl_partner = "wnd[0]/usr/tabsTAXI_TABSTRIP_HEAD/tabpT\\08/ssubSUBSCREEN_BODY:SAPMV50A:2114/subSUBSCREEN_PARTNER_OVERVIEW:SAPLV09C:1000/tblSAPLV09CGV_TC_PARTNER_OVERVIEW"
                session.findById(tbl_partner + "/cmbGVS_TC_DATA-REC-PARVW[0,5]").key = "SP"
                session.findById(tbl_partner + "/ctxtGVS_TC_DATA-REC-PARTNER_EXT[1,5]").text = transp_cod
                session.findById("wnd[0]").sendVKey(0)
                time.sleep(0.5)
                
                # Salvar (SM)
                session.findById("wnd[0]/tbar[1]/btn[20]").press() # Botão Registrar saída de mercadorias
                time.sleep(0.5)
                fechar_popups_VL02N(session)
                
                status_etapas[remessa]["sm"] = "success"
                log_sys.write(f"✅ Remessa {remessa} - Transportadora parceira (SM) registrada!")
            except Exception as e:
                status_etapas[remessa]["sm"] = "error"
                log_sys.write(f"❌ Erro ao registrar SM/Transportadora da remessa {remessa}: {e}")

def rodar_verificar_tolerancia(session, dados_cargas, status_etapas, remessas_a_processar=None):
    log_sys.write("=== [Tolerância MM] Iniciando Verificação de Tolerâncias (VL03N) ===")
    for carga_id, c_info in dados_cargas.items():
        for rem_info in c_info["remessas"]:
            remessa = rem_info["remessa"]
            if remessas_a_processar is not None and remessa not in remessas_a_processar:
                continue
            log_sys.write(f"🔍 Checando tolerância para a Remessa: {remessa}")
            
            if remessa not in status_etapas:
                status_etapas[remessa] = {}
            status_etapas[remessa]["tolerancia"] = "running"
            
            try:
                # Transação VL03N
                session.findById("wnd[0]/tbar[0]/okcd").text = "/nvl03n"
                session.findById("wnd[0]").sendVKey(0)
                
                if not esperar_id(session, ["wnd[0]/usr/ctxtLIKP-VBELN"]):
                    raise Exception("Tela inicial da transação VL03N não carregou.")
                    
                session.findById("wnd[0]/usr/ctxtLIKP-VBELN").text = remessa
                session.findById("wnd[0]").sendVKey(0)
                time.sleep(0.5)
                
                # Tratar se a remessa não existe no SAP
                sb_text = session.findById("wnd[0]/sbar").text.lower()
                if "não existe" in sb_text or "does not exist" in sb_text or "nenhum documento" in sb_text:
                    raise Exception(f"Remessa {remessa} não encontrada no SAP.")
                
                # Entrar na linha do item (F2/Double Click)
                session.findById("wnd[0]").sendVKey(2)
                time.sleep(0.5)
                
                # Selecionar a aba de Tolerâncias
                tab_tol_id = r"wnd[0]/usr/tabsTAXI_TABSTRIP_ITEM/tabpT\04"
                if not esperar_id(session, [tab_tol_id]):
                    raise Exception("Aba de Tolerâncias do item não carregou.")
                
                session.findById(tab_tol_id).select()
                time.sleep(0.3)
                
                # Obter limites de tolerância excedente e insuficiente
                tolExc = session.findById(r"wnd[0]/usr/tabsTAXI_TABSTRIP_ITEM/tabpT\04/ssubSUBSCREEN_BODY:SAPMV50A:3106/txtLIPS-UEBTO").text.strip()
                tolInc = session.findById(r"wnd[0]/usr/tabsTAXI_TABSTRIP_ITEM/tabpT\04/ssubSUBSCREEN_BODY:SAPMV50A:3106/txtLIPS-UNTTO").text.strip()
                
                # Converter para float para validações
                val_exc = 0.0
                val_inc = 0.0
                if tolExc:
                    try:
                        val_exc = float(tolExc.replace(",", "."))
                    except:
                        pass
                if tolInc:
                    try:
                        val_inc = float(tolInc.replace(",", "."))
                    except:
                        pass
                
                # Se ambas forem zero, fica vermelho (erro)
                if val_exc == 0.0 and val_inc == 0.0:
                    raise Exception("Ambas as tolerâncias (Excedente e Insuficiente) são zero.")
                
                log_sys.write(f"✅ Remessa {remessa} | Tolerância Excedente: {tolExc}% | Tolerância Insuficiente: {tolInc}%")
                
                # Se qualquer uma for abaixo de 10%, informa (alerta/log)
                if val_exc < 10.0 or val_inc < 10.0:
                    log_sys.write(f"⚠️ Alerta: Tolerância abaixo de 10% detectada na remessa {remessa} (Excedente: {tolExc}%, Insuficiente: {tolInc}%)")
                
                # Volta para a tela inicial
                session.findById("wnd[0]/tbar[0]/btn[3]").press() # voltar do item
                time.sleep(0.3)
                session.findById("wnd[0]/tbar[0]/btn[3]").press() # voltar para tela de consulta
                time.sleep(0.3)
                
                status_etapas[remessa]["tolerancia"] = "success"
                rem_info["tolerancia_exc"] = tolExc
                rem_info["tolerancia_inc"] = tolInc
                
            except Exception as e:
                status_etapas[remessa]["tolerancia"] = "error"
                log_sys.write(f"❌ Erro ao verificar tolerância da remessa {remessa}: {e}")

