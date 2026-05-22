import time
from datetime import datetime
from src.utils.common import log_sys
from src.utils.sap_utils import conectar_sap
from src.utils.excel_utils import ler_excel_universal, valorFloatPy, valorFloatexcel

centroP = "P716"
depOrigem = "INT"
depDestino = "005"

def selecionar_acao_migo(session, acao_key):
    """Tenta setar a ação na MIGO em diferentes IDs possíveis."""
    ids = [
        "wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0003/subSUB_FIRSTLINE:SAPLMIGO:0011/cmbGODYNPRO-ACTION",
        "wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0007/subSUB_FIRSTLINE:SAPLMIGO:0011/cmbGODYNPRO-ACTION",
        "wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0006/subSUB_FIRSTLINE:SAPLMIGO:0011/cmbGODYNPRO-ACTION",
        "wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0002/subSUB_FIRSTLINE:SAPLMIGO:0011/cmbGODYNPRO-ACTION"
    ]
    for sap_id in ids:
        try:
            session.findById(sap_id).key = acao_key
            session.findById(sap_id).setFocus()
            return
        except: continue

def ajustar_layout_migo(session,tipo):
    lista_ids_possiveis = ["0003", "0004", "0005", "0002", "0007", "0006", "0008", "0009"]
    
    for id_sap in lista_ids_possiveis:
        try:
            campo = session.findById(f"wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:{id_sap}/subSUB_FIRSTLINE:SAPLMIGO:0011/cmbGODYNPRO-REFDOC")
            campo.key = tipo
        except:
            continue
    for id_sap in lista_ids_possiveis:
        try:
            session.findById(f"wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:{id_sap}/subSUB_HEADER:SAPLMIGO:0102/btnOK_HEADER").press()
        except:
            continue
    for id_sap in lista_ids_possiveis:
        try:
            session.findById(f"wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:{id_sap}/subSUB_ITEMDETAIL:SAPLMIGO:0302/btnBUTTON_DETAIL").press()
        except:
            continue

def executar_transferencia_migo(caminho, auto=False, filtro="", ui_tpMigo=None):
    if isinstance(caminho, str):
        aba = "Exportação SAPUI5" if auto else "MIGO 311 411 ZP1"
        df = ler_excel_universal(caminho, aba, 0)
        cBrid = False
    else:
        df = caminho
        cBrid = True

    session = conectar_sap()
    if df is None or not session: return

    try:
        session.findById("wnd[0]").maximize()
        session.findById("wnd[0]/tbar[0]/okcd").text = "/nmigo"
        session.findById("wnd[0]").sendVKey(0)
        
        selecionar_acao_migo(session, "A08") # Transferência
        ajustar_layout_migo(session,"R10")
        
        # Lógica Auto vs Manual
        if auto:
            tpMigo = "411"
            df_filtrado = df[df['ACABADO'] == filtro].copy()
        else:
            if ui_tpMigo:
                tpMigo = str(ui_tpMigo)
            else:
                tpMigo = input("Digite 311 ou 411: ")
            df_filtrado = df.copy()

        session.findById("wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0007/subSUB_FIRSTLINE:SAPLMIGO:0011/ctxtGODEFAULT_TV-BWART").Text = tpMigo
        session.findById("wnd[0]").sendVKey(0)
        
        for contador, (_, row) in enumerate(df_filtrado.iterrows()):
            
            if auto:
                material = str(row['ACABADO']).strip()
                centro = centroP
                dep_origem = depOrigem
                dep_destino = depDestino
                if cBrid:
                    lote_origem = str(row['Lote']).strip()
                    lote_destino = str(row['Lote']).strip()
                else:
                    lote_origem = str(row['LOTE']).strip()
                    lote_destino = str(row['LOTE']).strip()
                qtd = valorFloatexcel(row['Peso Líquido'])
            else:
                material = str(row["Material"]).strip()
                centro = str(row["Centro"]).strip()
                dep_origem = str(row["Dep Origem"]).strip()
                dep_destino = str(row["Dep Destino"]).strip()
                lote_origem = str(row["Lote Origem"]).strip()
                lote_destino = str(row["Lote Destino"]).strip()
                qtd = valorFloatexcel(row["Quantidade"])
            
            # --- PREENCHIMENTO SAP ---
            # Item Detail
            session.findById("wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0007/subSUB_ITEMDETAIL:SAPLMIGO:0303/subSUB_DETAIL:SAPLMIGO:0305/tabsTS_GOITEM/tabpOK_GOITEM_TRANS/ssubSUB_TS_GOITEM_TRANS:SAPLMIGO:0390/ctxtGODYNPRO-MAKTX").Text = material
            session.findById("wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0007/subSUB_ITEMDETAIL:SAPLMIGO:0303/subSUB_DETAIL:SAPLMIGO:0305/tabsTS_GOITEM/tabpOK_GOITEM_TRANS/ssubSUB_TS_GOITEM_TRANS:SAPLMIGO:0390/ctxtGODYNPRO-NAME1").Text = centro
            session.findById("wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0007/subSUB_ITEMDETAIL:SAPLMIGO:0303/subSUB_DETAIL:SAPLMIGO:0305/tabsTS_GOITEM/tabpOK_GOITEM_TRANS/ssubSUB_TS_GOITEM_TRANS:SAPLMIGO:0390/ctxtGODYNPRO-LGOBE").Text = dep_origem
            session.findById("wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0007/subSUB_ITEMDETAIL:SAPLMIGO:0303/subSUB_DETAIL:SAPLMIGO:0305/tabsTS_GOITEM/tabpOK_GOITEM_TRANS/ssubSUB_TS_GOITEM_TRANS:SAPLMIGO:0390/ctxtGOITEM-UMLGOBE").Text = dep_destino
            session.findById("wnd[0]").sendVKey(0)

            # Lotes
            if lote_origem:
                session.findById("wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0007/subSUB_ITEMDETAIL:SAPLMIGO:0303/subSUB_DETAIL:SAPLMIGO:0305/tabsTS_GOITEM/tabpOK_GOITEM_TRANS/ssubSUB_TS_GOITEM_TRANS:SAPLMIGO:0390/ctxtGODYNPRO-CHARG").Text = lote_origem
                session.findById("wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0007/subSUB_ITEMDETAIL:SAPLMIGO:0303/subSUB_DETAIL:SAPLMIGO:0305/tabsTS_GOITEM/tabpOK_GOITEM_TRANS/ssubSUB_TS_GOITEM_TRANS:SAPLMIGO:0390/ctxtGODYNPRO-UMCHA").Text = lote_destino
            
            # Quantidade
            session.findById("wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0007/subSUB_ITEMDETAIL:SAPLMIGO:0303/subSUB_DETAIL:SAPLMIGO:0305/tabsTS_GOITEM/tabpOK_GOITEM_TRANS/ssubSUB_TS_GOITEM_TRANS:SAPLMIGO:0390/txtGODYNPRO-ERFMG").Text = qtd
            session.findById("wnd[0]").sendVKey(0)
            max_tentativas = 30 
            contadortentativa = 0 

            while session.findById("wnd[0]/sbar").text.startswith("Lote") and auto and contadortentativa < max_tentativas:
                log_sys.write(f"Aguardando integração. Tentativa {contadortentativa + 1} de {max_tentativas}...")
                time.sleep(2) # Reduzi para 2s (5s é muito tempo, mas ajuste conforme precisar)
                session.findById("wnd[0]").sendVKey(0) # Pressiona Enter
                session.findById("wnd[0]/tbar[0]/okcd").text = "/nmigo"
                session.findById("wnd[0]").sendVKey(0)
                session.findById("wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0007/subSUB_FIRSTLINE:SAPLMIGO:0011/ctxtGODEFAULT_TV-BWART").Text = tpMigo
                session.findById("wnd[0]").sendVKey(0)
                session.findById("wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0007/subSUB_ITEMDETAIL:SAPLMIGO:0303/subSUB_DETAIL:SAPLMIGO:0305/tabsTS_GOITEM/tabpOK_GOITEM_TRANS/ssubSUB_TS_GOITEM_TRANS:SAPLMIGO:0390/ctxtGODYNPRO-MAKTX").Text = material
                session.findById("wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0007/subSUB_ITEMDETAIL:SAPLMIGO:0303/subSUB_DETAIL:SAPLMIGO:0305/tabsTS_GOITEM/tabpOK_GOITEM_TRANS/ssubSUB_TS_GOITEM_TRANS:SAPLMIGO:0390/ctxtGODYNPRO-NAME1").Text = centro
                session.findById("wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0007/subSUB_ITEMDETAIL:SAPLMIGO:0303/subSUB_DETAIL:SAPLMIGO:0305/tabsTS_GOITEM/tabpOK_GOITEM_TRANS/ssubSUB_TS_GOITEM_TRANS:SAPLMIGO:0390/ctxtGODYNPRO-LGOBE").Text = dep_origem
                session.findById("wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0007/subSUB_ITEMDETAIL:SAPLMIGO:0303/subSUB_DETAIL:SAPLMIGO:0305/tabsTS_GOITEM/tabpOK_GOITEM_TRANS/ssubSUB_TS_GOITEM_TRANS:SAPLMIGO:0390/ctxtGOITEM-UMLGOBE").Text = dep_destino
                session.findById("wnd[0]").sendVKey(0)

                # Lotes
                if lote_origem:
                    session.findById("wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0007/subSUB_ITEMDETAIL:SAPLMIGO:0303/subSUB_DETAIL:SAPLMIGO:0305/tabsTS_GOITEM/tabpOK_GOITEM_TRANS/ssubSUB_TS_GOITEM_TRANS:SAPLMIGO:0390/ctxtGODYNPRO-CHARG").Text = lote_origem
                    session.findById("wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0007/subSUB_ITEMDETAIL:SAPLMIGO:0303/subSUB_DETAIL:SAPLMIGO:0305/tabsTS_GOITEM/tabpOK_GOITEM_TRANS/ssubSUB_TS_GOITEM_TRANS:SAPLMIGO:0390/ctxtGODYNPRO-UMCHA").Text = lote_destino
                
                # Quantidade
                session.findById("wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0007/subSUB_ITEMDETAIL:SAPLMIGO:0303/subSUB_DETAIL:SAPLMIGO:0305/tabsTS_GOITEM/tabpOK_GOITEM_TRANS/ssubSUB_TS_GOITEM_TRANS:SAPLMIGO:0390/txtGODYNPRO-ERFMG").Text = qtd
                session.findById("wnd[0]").sendVKey(0)                

                contadortentativa += 1


            # Próximo item (se não for o último)
            if contador <= len(df_filtrado):
                 session.findById("wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0007/subSUB_ITEMDETAIL:SAPLMIGO:0303/subSUB_DETAIL:SAPLMIGO:0305/btnOK_NEXT_ITEM").press()

        if auto:
             session.findById("wnd[0]/tbar[1]/btn[23]").press() # Postar

        log_sys.write("✅ MIGO Transferência Concluída.")
        return True

    except Exception as e:
        log_sys.write(f"❌ Erro MIGO: {e}")
        return False

def executar_migo_zp1(caminho, auto=False, op="", filtro="", ui_opt=None):
    if isinstance(caminho, str):
        
        aba = "Exportação SAPUI5" if auto else "MIGO 311 411 ZP1"
        df = ler_excel_universal(caminho, aba, 0)
        cBrid = False
    else:
        df = caminho
        cBrid = True
        
    session = conectar_sap()
    if df is None or not session: return
    
    dt_hoje = datetime.now().strftime("%d.%m.%Y")

    try:
        session.findById("wnd[0]/tbar[0]/okcd").Text = "/nMIGO"
        session.findById("wnd[0]").sendVKey(0)

        movimento = "261"
        selecionar_acao_migo(session, "A07") # Saída de mercadoria
        ajustar_layout_migo(session,"R08")
        loop = 2 if auto else 1 # Seu script original faz 2 loops se auto=True, não sei porquê, mas mantive.

        if not auto:
            if not op:
                op = input("Informe a OP: ")
            
            if ui_opt:
                opt = str(ui_opt)
            else:
                opt = input("1-Consumo(261) | 2-Apontamento(ZP1): ")
                
            if opt == "2":
                movimento = "ZP1"
                selecionar_acao_migo(session, "A01") # Entrada de mercadoria

        for _ in range(loop):
            # Header
            session.findById("wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0003/subSUB_FIRSTLINE:SAPLMIGO:0011/ctxtGODEFAULT_TV-BWART").Text = movimento
            session.findById("wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0003/subSUB_FIRSTLINE:SAPLMIGO:0011/subSUB_FIRSTLINE_REFDOC:SAPLMIGO:2070/ctxtGODYNPRO-ORDER_NUMBER").Text = op
            session.findById("wnd[0]").sendVKey(0)
            
            # Checkbox "Take" (OK)
            session.findById("wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0003/subSUB_ITEMDETAIL:SAPLMIGO:0301/subSUB_DETAIL:SAPLMIGO:0300/subSUB_DETAIL_TAKE:SAPLMIGO:0304/chkGODYNPRO-DETAIL_TAKE").Selected = True

            if movimento == "ZP1":
                # Utilização Livre e Data
                session.findById("wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0003/subSUB_ITEMDETAIL:SAPLMIGO:0301/subSUB_DETAIL:SAPLMIGO:0300/tabsTS_GOITEM/tabpOK_GOITEM_DESTINAT./ssubSUB_TS_GOITEM_DESTINATION:SAPLMIGO:0325/cmbGOITEM-MIGO_INSMK").key = ""
                session.findById("wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0003/subSUB_ITEMDETAIL:SAPLMIGO:0301/subSUB_DETAIL:SAPLMIGO:0300/tabsTS_GOITEM/tabpOK_GOITEM_BATCH").select()
                session.findById("wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0003/subSUB_ITEMDETAIL:SAPLMIGO:0301/subSUB_DETAIL:SAPLMIGO:0300/tabsTS_GOITEM/tabpOK_GOITEM_BATCH/ssubSUB_TS_GOITEM_BATCH:SAPLMIGO:0335/ctxtGOITEM-HSDAT").text = dt_hoje
            
            # Botão Split
            session.findById("wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0003/subSUB_ITEMLIST:SAPLMIGO:0200/subSUB_BUTTONS:SAPLMIGO:0210/btnOK_SPLIT_QUANTITY").press()

            # Preenchimento Grid
            col_lote_sap = "4" if movimento == "ZP1" else "3"
            i_scroll = 0
            
            if auto:
                df_filtrado = df[df['ACABADO'] == filtro].copy()

            else:
                df_filtrado = df.copy()

            for idx, row in df_filtrado.iterrows():
                linha_sap = 0 if idx == 0 else 1 
                
                # --- VARIAVEIS AUTO VS MANUAL ---
                if auto:
                    if cBrid==True and movimento== "261":
                        lote = str(row['Lote cheio']).strip()
                    elif cBrid==True and movimento =="101":
                        lote = str(row['Lote']).strip()
                    else:
                        lote = str(row['LOTE']).strip()

                    qtd = valorFloatexcel(row['Peso Líquido'])
                else:
                    lote = str(row["Lote Origem"]).strip()
                    qtd = valorFloatexcel(row["Quantidade"])

                session.findById(f"wnd[1]/usr/tblSAPLMIGOTV_GOSPLIT/txtGOSPLIT-ERFMG[0,{linha_sap}]").Text = qtd
                session.findById(f"wnd[1]/usr/tblSAPLMIGOTV_GOSPLIT/ctxtGOSPLIT-CHARG[{col_lote_sap},{linha_sap}]").Text = lote
                session.findById("wnd[1]").sendVKey(0)
                
                print(f"\rLote: {lote} | Qtd: {qtd}...",end="", flush=True)

                if idx >= 1:
                    i_scroll += 1
                    session.findById("wnd[1]/usr/tblSAPLMIGOTV_GOSPLIT").verticalScrollbar.Position = i_scroll
            
            session.findById("wnd[1]/tbar[0]/btn[5]").press() # Confirma split
            
            if auto:
                session.findById("wnd[0]/tbar[1]/btn[23]").press() # Postar
            
            if movimento == "ZP1":
                log_sys.write("Apontamento Realizado com Sucesso...\n")
            else:
                log_sys.write("Consumo Realizado com Sucesso...\n")
            
            if cBrid==True:
                movimento = "101"
            else:
                movimento = "ZP1"
            selecionar_acao_migo(session, "A01")
            ajustar_layout_migo(session,"R08")
        return True

    except Exception as e:
        log_sys.write(f"❌ Erro MIGO ZP1: {e}")
        return False
