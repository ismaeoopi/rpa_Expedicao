import time
from src.utils.common import log_sys
from src.utils.sap_utils import conectar_sap
from src.utils.excel_utils import ler_excel_universal, valorFloatPy, valorFloatexcel

def executar_prdi(caminho, auto=False, inbound="", filtro="", tamanho=None, nUcs_unicas=None):
    if isinstance(caminho, str):
        aba = "Exportação SAPUI5" if auto else "PRDI"
        df = ler_excel_universal(caminho, aba, 1) # Coluna validação index 1 conforme original
    else:
        df = caminho
    session = conectar_sap()
    if df is None or not session: return

    if auto:
        df_filtrado = df[df['ACABADO'] == filtro].copy()
    else:
        df_filtrado = df.copy()
    
    # Se o tamanho não for passado, calcula o padrão (tamanho do dataframe)
    if tamanho is None:
        tamanho = len(df_filtrado)
    log_sys.write(f"🚀 Iniciando PRDI para {tamanho} itens...")


    try:
        session.findById("wnd[0]").maximize()
        session.findById("wnd[0]/tbar[0]/okcd").Text = "/N/SCWM/PRDI"
        session.findById("wnd[0]").sendVKey(0)

        if not auto:
            if not inbound:
                inbound = input("Digite a inbound: ")
        
        # Busca Inbound
        if inbound:
            inbound = str(inbound).strip()
            if inbound.endswith(".0"):
                inbound = inbound[:-2]

        criterio = "REFDOCNO_ERP_I" if inbound.startswith("18") else "REFDOCNO_PPO_I"
        campo_busca = "2003" if inbound.startswith("18") else "2015"
        tipo_inbound = "ERP" if inbound.startswith("18") else "PPO"

        session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/cmb/SCWM/S_UI_DLV-V_CRITERION").key = criterio
        session.findById(f"wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_SEARCH_VALUE:/SCWM/SAPLUI_DLV_PRD:{campo_busca}/txt/SCWM/S_SP_Q_HEAD-REFDOCNO_{tipo_inbound}_I").Text = inbound
        session.findById(f"wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_SEARCH_VALUE:/SCWM/SAPLUI_DLV_PRD:{campo_busca}/btnCMD_GO").press()
        contadortentativa = 0
        max_tentativas = 30
        
        while session.findById("wnd[0]/sbar").text == "Nenhum documento encontrado" and auto==True and contadortentativa < max_tentativas:
                log_sys.write(f"Aguardando integração. Tentativa {contadortentativa + 1} de {max_tentativas}...")
                time.sleep(5)
                session.findById(f"wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_SEARCH_VALUE:/SCWM/SAPLUI_DLV_PRD:{campo_busca}/btnCMD_GO").press()
                contadortentativa += 1
        
        # Pega Doc Ref na Grid
        grid = session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_OIP_DATA_AREA:/SCWM/SAPLUI_DLV_PRD:2210/subSUB_OIP_1_CONTENT:/SCWM/SAPLUI_DLV_PRD:2211/cntlCONTAINER_ALV_OIP_1/shellcont/shell")
        grid.selectedRows = "0"
        doc_ref = grid.getcellvalue(0, "DOCNO")
        
        # Conta o número de linhas no Grid ODP1 para verificar lote único
        num_linhas = 0
        try:
            grid_odp1 = session.findById("wnd[0]/usr/subSUB_COMPLETE_ODP1:/SCWM/SAPLUI_DLV_PRD:3000/tabsTABSTRIP_ODP1/tabpOK_ODP1_TAB1/ssubSUB_ODP1_TAB1:/SCWM/SAPLUI_DLV_CORE:3210/ssubSUB_ODP1_1_CONTENT:/SCWM/SAPLUI_DLV_CORE:3211/cntlCONTAINER_ALV_ODP1_1/shellcont/shell")
            num_linhas = grid_odp1.rowCount
            log_sys.write(f"📊 Quantidade de linhas detectadas no ODP1: {num_linhas}")
        except Exception as e:
            log_sys.write(f"⚠️ Não foi possível obter rowCount do ODP1 (pode não estar visível): {e}")

        # Packing Dialog
        session.findById("wnd[0]/mbar/menu[0]/menu[2]/menu[2]").Select() # Função Follow-up -> Pack
        
        # Se nUcs_unicas for informado, usamos esse valor para NUMBER_HUS
        total_a_criar = nUcs_unicas if nUcs_unicas is not None else tamanho
        if total_a_criar > 99:
            restante = total_a_criar
            while restante > 0:
                if restante > 99:
                    nUcs = 99
                else:
                    nUcs = restante
                session.findById("wnd[0]/usr/subSUB_SCANNER:/SCWM/SAPLUI_PACKING:0200/tabsTS_SCANNER/tabpHU_CREATE/ssubSS_SCANNER:/SCWM/SAPLUI_PACKING:0202/ctxt/SCWM/S_PACK_VIEW_SCANNER-DEST_PMAT_NO").Text = "EWMS4-PAL06"
                session.findById("wnd[0]/usr/subSUB_SCANNER:/SCWM/SAPLUI_PACKING:0200/tabsTS_SCANNER/tabpHU_CREATE/ssubSS_SCANNER:/SCWM/SAPLUI_PACKING:0202/txt/SCWM/S_PACK_VIEW_SCANNER-NUMBER_HUS").Text = str(nUcs)
                session.findById("wnd[0]/usr/subSUB_SCANNER:/SCWM/SAPLUI_PACKING:0200/tabsTS_SCANNER/tabpHU_CREATE/ssubSS_SCANNER:/SCWM/SAPLUI_PACKING:0202/btnPB_CREATE").press()
                restante -= nUcs
        else:
            session.findById("wnd[0]/usr/subSUB_SCANNER:/SCWM/SAPLUI_PACKING:0200/tabsTS_SCANNER/tabpHU_CREATE/ssubSS_SCANNER:/SCWM/SAPLUI_PACKING:0202/ctxt/SCWM/S_PACK_VIEW_SCANNER-DEST_PMAT_NO").Text = "EWMS4-PAL06"
            session.findById("wnd[0]/usr/subSUB_SCANNER:/SCWM/SAPLUI_PACKING:0200/tabsTS_SCANNER/tabpHU_CREATE/ssubSS_SCANNER:/SCWM/SAPLUI_PACKING:0202/txt/SCWM/S_PACK_VIEW_SCANNER-NUMBER_HUS").Text = str(total_a_criar)
            session.findById("wnd[0]/usr/subSUB_SCANNER:/SCWM/SAPLUI_PACKING:0200/tabsTS_SCANNER/tabpHU_CREATE/ssubSS_SCANNER:/SCWM/SAPLUI_PACKING:0202/btnPB_CREATE").press()
        time.sleep(2)
        session.findById("wnd[0]/usr/subSUB_SCANNER:/SCWM/SAPLUI_PACKING:0200/tabsTS_SCANNER/tabpMAT_PACK").Select()

        # Lista de UCs únicas na ordem em que aparecem no df_filtrado
        ucs_unicas_lista = list(df_filtrado['UC'].unique()) if 'UC' in df_filtrado.columns else []
        ucs_processadas = {} # Cache para armazenar as UCs geradas e não repetir preenchimento de tara

        for i, (index, row) in enumerate(df_filtrado.iterrows()):

            print(f"\r📦 Embalando: {i + 1} de {tamanho}...", end="", flush=True)
            # --- VARIAVEIS AUTO VS MANUAL ---
            if auto:
                peso = valorFloatexcel(row['Peso Líquido']).strip()
                bob = valorFloatexcel(row['Nº Bobinas']).strip()
                peso_bruto = float(row['Peso Bruto'])
                # Se houver Peso LIQ (peso total do palete para a tara), usamos. Caso contrário, usamos Peso Líquido.
                peso_liq_total = float(row['Peso LIQ']) if 'Peso LIQ' in row else float(row['Peso Líquido'])
                print(f"Peso Bruto: {peso_bruto}, Peso Líquido Total para Tara: {peso_liq_total}")
                tara = valorFloatexcel(peso_bruto - peso_liq_total)
            else:
                peso = valorFloatexcel(row["Peso líquido"]).strip()
                bob = valorFloatexcel(row["Bobinas"]).strip()
                tara = valorFloatexcel(row["Tara"])

            itemNum = i + 1
            identificador_uc_excel = row.get('UC', None)

            # Preenche Scanner (Sempre ocorre para cada lote/item)
            session.findById("wnd[0]/usr/subSUB_SCANNER:/SCWM/SAPLUI_PACKING:0200/tabsTS_SCANNER/tabpMAT_PACK/ssubSS_SCANNER:/SCWM/SAPLUI_PACKING:0209/txt/SCWM/S_SCAN_PLAN-DOCNO").Text = doc_ref
            time.sleep(0.1)
            itm_no = "10" if num_linhas == 1 else str((itemNum * 10))
            session.findById("wnd[0]/usr/subSUB_SCANNER:/SCWM/SAPLUI_PACKING:0200/tabsTS_SCANNER/tabpMAT_PACK/ssubSS_SCANNER:/SCWM/SAPLUI_PACKING:0209/txt/SCWM/S_SCAN_PLAN-ITMNO").Text = itm_no
            session.findById("wnd[0]/usr/subSUB_SCANNER:/SCWM/SAPLUI_PACKING:0200/tabsTS_SCANNER/tabpMAT_PACK/ssubSS_SCANNER:/SCWM/SAPLUI_PACKING:0209/txt/SCWM/S_SCAN_PLAN-UIQUAN").Text = peso
            
            # Verifica se essa UC já teve tara/volume preenchidos neste processo
            if identificador_uc_excel and identificador_uc_excel in ucs_processadas:
                # Já processamos, reaproveita o ID e pula a seleção na árvore
                uc = ucs_processadas[identificador_uc_excel]
            else:
                # Primeira vez com esta UC, precisa ir na árvore, colocar tara/volume e pegar ID gerado
                if ucs_unicas_lista and identificador_uc_excel:
                    idx_uc = ucs_unicas_lista.index(identificador_uc_excel) + 1
                    node_id = str(tamanho + idx_uc + 1).rjust(11)
                else:
                    node_id = str(tamanho + itemNum + 1).rjust(11)

                # Seleciona Nó na árvore
                tree = session.findById("wnd[0]/shellcont/shellcont/shell/shellcont[0]/shell/shellcont[1]/shell[1]")
                tree.doubleClickNode(node_id)
                time.sleep(0.1)
    
                # Preenche Tara e Volume
                session.findById("wnd[0]/usr/subSUB_HUDETAIL:/SCWM/SAPLUI_PACKING:0300/tabsTS_HU/tabpHUDETAIL").Select()
                session.findById("wnd[0]/usr/subSUB_HUDETAIL:/SCWM/SAPLUI_PACKING:0300/tabsTS_HU/tabpHUDETAIL/ssubSUB_DETAIL:/SCWM/SAPLUI_PACKING:0320/txt/SCWM/S_PACK_VIEW_HUHDR-T_WEIGHT").Text = tara
                session.findById("wnd[0]/usr/subSUB_HUDETAIL:/SCWM/SAPLUI_PACKING:0300/tabsTS_HU/tabpHUDETAIL/ssubSUB_DETAIL:/SCWM/SAPLUI_PACKING:0320/txt/SCWM/S_PACK_VIEW_HUHDR-T_VOLUME").Text = bob
    
                # Pega ID da HU gerada
                session.findById("wnd[0]/usr/subSUB_HUDETAIL:/SCWM/SAPLUI_PACKING:0300/tabsTS_HU/tabpHUDETAIL2").Select()
                uc = session.findById("wnd[0]/usr/subSUB_HUDETAIL:/SCWM/SAPLUI_PACKING:0300/tabsTS_HU/tabpHUDETAIL2/ssubSUB_DETAIL:/SCWM/SAPLUI_PACKING:0335/txt/SCWM/S_PACK_VIEW_HUHDR-HUIDENT").Text
                time.sleep(0.5)

                # Salva no cache
                if identificador_uc_excel:
                    ucs_processadas[identificador_uc_excel] = uc

            # Finaliza Packing do item (Sempre executa, com o ID da UC lido ou salvo)
            session.findById("wnd[0]/usr/subSUB_SCANNER:/SCWM/SAPLUI_PACKING:0200/tabsTS_SCANNER/tabpMAT_PACK/ssubSS_SCANNER:/SCWM/SAPLUI_PACKING:0209/txt/SCWM/S_SCAN_PLAN-DHUNO").Text = uc
            session.findById("wnd[0]/usr/subSUB_SCANNER:/SCWM/SAPLUI_PACKING:0200/tabsTS_SCANNER/tabpMAT_PACK/ssubSS_SCANNER:/SCWM/SAPLUI_PACKING:0209/btnPB_PACK").press()
            df.at[i,"UC"] = uc
        
        log_sys.write(f"\n✅ {tamanho} itens embalados com sucesso!")

        if auto:
            session.findById("wnd[0]/tbar[0]/btn[11]").press() # Save global
        return True
    except Exception as e:
        log_sys.write(f"❌ Erro ao executar o PRDI: {e}")

        return False
