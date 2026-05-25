import time
from src.utils.common import log_sys
from src.utils.sap_utils import conectar_sap
from src.utils.excel_utils import ler_excel_universal, valorFloatPy, valorFloatexcel

def executar_prdi(caminho, auto=False, inbound="", filtro=""):
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
        criterio = "REFDOCNO_ERP_I" if inbound.startswith("18") else "REFDOCNO_PPO_I"
        campo_busca = "2003" if inbound.startswith("18") else "2015"
        tipo_inbound = "ERP" if inbound.startswith("18") else "PPO"

        session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/cmb/SCWM/S_UI_DLV-V_CRITERION").Key = criterio
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
        
        # Packing Dialog
        session.findById("wnd[0]/mbar/menu[0]/menu[2]/menu[2]").Select() # Função Follow-up -> Pack
        
        if tamanho>99:
            restante = tamanho
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
            session.findById("wnd[0]/usr/subSUB_SCANNER:/SCWM/SAPLUI_PACKING:0200/tabsTS_SCANNER/tabpHU_CREATE/ssubSS_SCANNER:/SCWM/SAPLUI_PACKING:0202/txt/SCWM/S_PACK_VIEW_SCANNER-NUMBER_HUS").Text = str(tamanho)
            session.findById("wnd[0]/usr/subSUB_SCANNER:/SCWM/SAPLUI_PACKING:0200/tabsTS_SCANNER/tabpHU_CREATE/ssubSS_SCANNER:/SCWM/SAPLUI_PACKING:0202/btnPB_CREATE").press()
        time.sleep(2)
        session.findById("wnd[0]/usr/subSUB_SCANNER:/SCWM/SAPLUI_PACKING:0200/tabsTS_SCANNER/tabpMAT_PACK").Select()

        for i, (index, row) in enumerate(df_filtrado.iterrows()):

            print(f"\r📦 Embalando: {i + 1} de {tamanho}...", end="", flush=True)
            # --- VARIAVEIS AUTO VS MANUAL ---
            if auto:
                peso = valorFloatexcel(row['Peso Líquido']).strip()
                bob = valorFloatexcel(row['Nº Bobinas']).strip()
                peso_bruto = float(row['Peso Bruto'])
                peso_liq_float = float(row['Peso Líquido'])
                print(f"Peso Bruto: {peso_bruto}, Peso Líquido: {peso_liq_float}")
                tara = valorFloatexcel(peso_bruto - peso_liq_float)
            else:
                peso = valorFloatexcel(row["Peso líquido"]).strip()
                bob = valorFloatexcel(row["Bobinas"]).strip()
                tara = valorFloatexcel(row["Tara"])

            itemNum = i + 1
            node_id = str(tamanho + itemNum + 1).rjust(11)

            # Preenche Scanner
            session.findById("wnd[0]/usr/subSUB_SCANNER:/SCWM/SAPLUI_PACKING:0200/tabsTS_SCANNER/tabpMAT_PACK/ssubSS_SCANNER:/SCWM/SAPLUI_PACKING:0209/txt/SCWM/S_SCAN_PLAN-DOCNO").Text = doc_ref
            time.sleep(0.1)
            session.findById("wnd[0]/usr/subSUB_SCANNER:/SCWM/SAPLUI_PACKING:0200/tabsTS_SCANNER/tabpMAT_PACK/ssubSS_SCANNER:/SCWM/SAPLUI_PACKING:0209/txt/SCWM/S_SCAN_PLAN-ITMNO").Text = str((itemNum * 10))
            session.findById("wnd[0]/usr/subSUB_SCANNER:/SCWM/SAPLUI_PACKING:0200/tabsTS_SCANNER/tabpMAT_PACK/ssubSS_SCANNER:/SCWM/SAPLUI_PACKING:0209/txt/SCWM/S_SCAN_PLAN-UIQUAN").Text = peso
            
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

            # Finaliza Packing do item
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
