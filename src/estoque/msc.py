from datetime import datetime
from src.utils.common import log_sys
from src.utils.sap_utils import conectar_sap, fechar_popups
from src.utils.excel_utils import ler_excel_universal, tratar_datas, valorFloatPy

centroP = "P716"

def executar_msc1n(caminho):

    if isinstance(caminho, str):
        df = ler_excel_universal(caminho, "Criar e Alterar Lotes", 0)
        auto = False
    else:
        df = caminho
        auto = True

    session = conectar_sap()
    if not df is None and session:
        if auto == True:
            info = 1
            #df['Lote'] = ""
            df['dep'] = ""
            df['centro'] = centroP
            df["Dt produção"] = datetime.now()
        else:
            log_sys.write("1 - Sem referência | 2 - Referência múltipla")
            try:
                info = float(input("Opção: "))
            except: info = 0

        for i, row in df.iterrows():
            if auto == True:
                material = "ACABADO"
                centro = "centro"
                dep = 'dep'
                lote = 'Lote'
                
            else:
                material = "Material"
                centro = "Centro"
                dep = "Depósito"
                lote = "Lote"
            try:
                session.findById("wnd[0]/tbar[0]/okcd").Text = "/nmsc1n"
                session.findById("wnd[0]").sendVKey(0)
                
                # Campos básicos
                session.findById("wnd[0]/usr/subSUBSCR_BATCH_MASTER:SAPLCHRG:1111/subSUBSCR_HEADER:SAPLCHRG:1401/ctxtDFBATCH-MATNR").Text = str(row[material]).strip()
                lote_val = str(row[lote]).strip()
                if lote_val and lote_val.lower() != "nan":
                    session.findById("wnd[0]/usr/subSUBSCR_BATCH_MASTER:SAPLCHRG:1111/subSUBSCR_HEADER:SAPLCHRG:1401/ctxtDFBATCH-CHARG").Text = lote_val
                
                session.findById("wnd[0]/usr/subSUBSCR_BATCH_MASTER:SAPLCHRG:1111/subSUBSCR_HEADER:SAPLCHRG:1401/ctxtDFBATCH-WERKS").Text = str(row[centro]).strip()
                session.findById("wnd[0]/usr/subSUBSCR_BATCH_MASTER:SAPLCHRG:1111/subSUBSCR_HEADER:SAPLCHRG:1401/ctxtDFBATCH-LGORT").Text = str(row[dep]).strip()
                
                # Referência
                if info == 2: # Múltipla
                    session.findById("wnd[0]/usr/subSUBSCR_BATCH_MASTER:SAPLCHRG:1111/subSUBSCR_HEADER:SAPLCHRG:1401/ctxtDFBATCH-REF_MATNR").Text = str(row["Material referencia"]).strip()
                    session.findById("wnd[0]/usr/subSUBSCR_BATCH_MASTER:SAPLCHRG:1111/subSUBSCR_HEADER:SAPLCHRG:1401/ctxtDFBATCH-REF_CHARG").Text = lote_val
                
                session.findById("wnd[0]").sendVKey(0)

                # Tratamento popup atribuição automática
                try:
                    if session.Children.Count > 1 and "Atribuição automática" in session.ActiveWindow.Text:
                         session.findById("wnd[1]/usr/btnBUTTON_1").press()
                except: pass

                # Se não der erro, preenche datas e características
                if session.findById("wnd[0]/sbar").messagetype != "E":
                    if info == 1: # Sem referência
                        dt_p, dt_v = tratar_datas(row.get("Dt produção"))
                        if dt_p:
                             session.findById("wnd[0]/usr/subSUBSCR_BATCH_MASTER:SAPLCHRG:1111/subSUBSCR_TABSTRIP:SAPLCHRG:2000/tabsTS_BODY/tabpGRHD/ssubSUBSCR_BODY:SAPLCHRG:2100/ctxtMCHA-HSDAT").Text = dt_p
                             session.findById("wnd[0]").sendVKey(0)
                             # Vencimento se vazio
                             if session.findById("wnd[0]/usr/subSUBSCR_BATCH_MASTER:SAPLCHRG:1111/subSUBSCR_TABSTRIP:SAPLCHRG:2000/tabsTS_BODY/tabpGRHD/ssubSUBSCR_BODY:SAPLCHRG:2100/ctxtDFBATCH-MHD_IO").Text == "":
                                 session.findById("wnd[0]/usr/subSUBSCR_BATCH_MASTER:SAPLCHRG:1111/subSUBSCR_TABSTRIP:SAPLCHRG:2000/tabsTS_BODY/tabpGRHD/ssubSUBSCR_BODY:SAPLCHRG:2100/ctxtDFBATCH-MHD_IO").Text = dt_v
                    
                    # Aba Classificação (OP e Fator)
                    session.findById("wnd[0]").sendVKey(0)
                    fechar_popups(session, "Data de vencimento")
                    op = str(row.get("OP", "")).strip()
                    fator = ""
                    if auto==False:
                        fator = str(row.get("Fator Conversão", "")).strip()
                    
                    if op or fator:
                        session.findById("wnd[0]/usr/subSUBSCR_BATCH_MASTER:SAPLCHRG:1111/subSUBSCR_TABSTRIP:SAPLCHRG:2000/tabsTS_BODY/tabpCLAS").Select()
                        if op:
                            session.findById("wnd[0]/usr/subSUBSCR_BATCH_MASTER:SAPLCHRG:1111/subSUBSCR_TABSTRIP:SAPLCHRG:2000/tabsTS_BODY/tabpCLAS/ssubSUBSCR_BODY:SAPLCHRG:2300/ssubSUBSCR_CLASS:SAPLCTMS:5000/tabsTABSTRIP_CHAR/tabpTAB1/ssubTABSTRIP_CHAR_GR:SAPLCTMS:5100/tblSAPLCTMSCHARS_S/ctxtRCTMS-MWERT[1,4]").Text = op
                        if fator:
                            scroll = session.findById("wnd[0]/usr/subSUBSCR_BATCH_MASTER:SAPLCHRG:1111/subSUBSCR_TABSTRIP:SAPLCHRG:2000/tabsTS_BODY/tabpCLAS/ssubSUBSCR_BODY:SAPLCHRG:2300/ssubSUBSCR_CLASS:SAPLCTMS:5000/tabsTABSTRIP_CHAR/tabpTAB1/ssubTABSTRIP_CHAR_GR:SAPLCTMS:5100/tblSAPLCTMSCHARS_S")
                            scroll.verticalScrollbar.Position = 10
                            session.findById("wnd[0]/usr/subSUBSCR_BATCH_MASTER:SAPLCHRG:1111/subSUBSCR_TABSTRIP:SAPLCHRG:2000/tabsTS_BODY/tabpCLAS/ssubSUBSCR_BODY:SAPLCHRG:2300/ssubSUBSCR_CLASS:SAPLCTMS:5000/tabsTABSTRIP_CHAR/tabpTAB1/ssubTABSTRIP_CHAR_GR:SAPLCTMS:5100/tblSAPLCTMSCHARS_S/ctxtRCTMS-MWERT[1,4]").Text = fator

                    session.findById("wnd[0]/tbar[0]/btn[11]").press() # Salvar
                    log_sys.write(f"✅ Salvo: {session.findById('wnd[0]/sbar').Text}")
                    loteG = session.findById('wnd[0]/sbar').Text
                    loteG = "".join(filter(str.isdigit, loteG))
                    df.at[i, 'Lote'] = loteG
                    
            except Exception as e:
                log_sys.write(f"❌ Erro linha {i}: {e}")

def executar_msc2n(caminho):
    # Usa a mesma aba do MSC1N
    df = ler_excel_universal(caminho, "Criar e Alterar Lotes", 0)
    session = conectar_sap()
    if df is None or not session: return

    log_sys.write(f"🚀 Iniciando MSC2N para {len(df)} itens...")

    for i, row in df.iterrows():
        try:
            session.findById("wnd[0]/tbar[0]/okcd").Text = "/nmsc2n"
            session.findById("wnd[0]").sendVKey(0)

            # --- Preenchimento do Cabeçalho (MSC2N geralmente usa tela 1501) ---
            header_path = "wnd[0]/usr/subSUBSCR_BATCH_MASTER:SAPLCHRG:1111/subSUBSCR_HEADER:SAPLCHRG:1501"
            
            session.findById(f"{header_path}/ctxtDFBATCH-MATNR").Text = str(row["Material"]).strip()
            session.findById(f"{header_path}/ctxtDFBATCH-CHARG").Text = str(row["Lote"]).strip()
            session.findById(f"{header_path}/ctxtDFBATCH-WERKS").Text = str(row["Centro"]).strip()
            session.findById(f"{header_path}/ctxtDFBATCH-LGORT").Text = str(row.get("Depósito", "")).strip()
            
            session.findById("wnd[0]").sendVKey(0)

            # Se não houver erro bloqueante (tipo 'E')
            if session.findById("wnd[0]/sbar").messagetype != "E":
                
                # --- DATAS (Aba Dados Básicos 1) ---
                dt_p, dt_v = tratar_datas(row.get("Dt produção"))
                
                if dt_p:
                    # Caminho da aba Dados Básicos 1
                    body_path = "wnd[0]/usr/subSUBSCR_BATCH_MASTER:SAPLCHRG:1111/subSUBSCR_TABSTRIP:SAPLCHRG:2000/tabsTS_BODY/tabpGRHD/ssubSUBSCR_BODY:SAPLCHRG:2100"
                    
                    session.findById(f"{body_path}/ctxtMCHA-HSDAT").Text = dt_p
                    
                    # Preenche vencimento apenas se estiver vazio
                    vencimento_field = session.findById(f"{body_path}/ctxtDFBATCH-MHD_IO")
                    if vencimento_field.Text == "":
                        vencimento_field.Text = dt_v

                # --- CLASSIFICAÇÃO (Aba Classificação) ---
                op = str(row.get("OP", "")).strip()
                fator = str(row.get("Fator Conversão", "")).strip()

                if op or fator:
                    session.findById("wnd[0]/usr/subSUBSCR_BATCH_MASTER:SAPLCHRG:1111/subSUBSCR_TABSTRIP:SAPLCHRG:2000/tabsTS_BODY/tabpCLAS").Select()
                    
                    grid_path = "wnd[0]/usr/subSUBSCR_BATCH_MASTER:SAPLCHRG:1111/subSUBSCR_TABSTRIP:SAPLCHRG:2000/tabsTS_BODY/tabpCLAS/ssubSUBSCR_BODY:SAPLCHRG:2300/ssubSUBSCR_CLASS:SAPLCTMS:5000/tabsTABSTRIP_CHAR/tabpTAB1/ssubTABSTRIP_CHAR_GR:SAPLCTMS:5100/tblSAPLCTMSCHARS_S"
                    
                    # Garante scroll no topo para preencher OP
                    if op:
                        session.findById(grid_path).verticalScrollbar.Position = 0
                        # Índice [1,4] conforme seu script original
                        session.findById(f"{grid_path}/ctxtRCTMS-MWERT[1,4]").Text = op
                    
                    # Scroll para preencher Fator
                    if fator:
                        session.findById(grid_path).verticalScrollbar.Position = 10
                        session.findById(f"{grid_path}/ctxtRCTMS-MWERT[1,4]").Text = fator
                
                session.findById("wnd[0]/tbar[0]/btn[11]").press() # Salvar
                log_sys.write(f"✅ Alterado: {session.findById('wnd[0]/sbar').Text}")
            
            else:
                log_sys.write(f"⚠️ Bloqueio SAP item {i+1}: {session.findById('wnd[0]/sbar').Text}")

        except Exception as e:
            log_sys.write(f"❌ Erro MSC2N item {i+1}: {e}")

def ajustar_fator(caminho):
    df = ler_excel_universal(caminho, "Ajustar Fator", 0)
    session = conectar_sap()
    if not df is None and session:
        for i, row in df.iterrows():
            try:
                session.findById("wnd[0]/tbar[0]/okcd").Text = "/nmsc2n"
                session.findById("wnd[0]").sendVKey(0)
                
                # Cálculo do Fator
                peso = valorFloatPy(row["Peso líquido"])
                bob = valorFloatPy(row["Qtd bob"])
                fator_calc = f"{round(peso/bob, 10)}".replace(".", ",") if bob > 0 else "0"

                # Preenchimento Cabeçalho
                session.findById("wnd[0]/usr/subSUBSCR_BATCH_MASTER:SAPLCHRG:1111/subSUBSCR_HEADER:SAPLCHRG:1501/ctxtDFBATCH-MATNR").Text = str(row["Material"]).strip()
                session.findById("wnd[0]/usr/subSUBSCR_BATCH_MASTER:SAPLCHRG:1111/subSUBSCR_HEADER:SAPLCHRG:1501/ctxtDFBATCH-CHARG").Text = str(row["Lote"]).strip()
                session.findById("wnd[0]/usr/subSUBSCR_BATCH_MASTER:SAPLCHRG:1111/subSUBSCR_HEADER:SAPLCHRG:1501/ctxtDFBATCH-WERKS").Text = str(row["Centro"]).strip()
                session.findById("wnd[0]/usr/subSUBSCR_BATCH_MASTER:SAPLCHRG:1111/subSUBSCR_HEADER:SAPLCHRG:1501/ctxtDFBATCH-LGORT").Text = str(row["Depósito"]).strip()
                session.findById("wnd[0]").sendVKey(0)

                # Aba Classificação
                session.findById("wnd[0]/usr/subSUBSCR_BATCH_MASTER:SAPLCHRG:1111/subSUBSCR_TABSTRIP:SAPLCHRG:2000/tabsTS_BODY/tabpCLAS").Select()
                scroll = session.findById("wnd[0]/usr/subSUBSCR_BATCH_MASTER:SAPLCHRG:1111/subSUBSCR_TABSTRIP:SAPLCHRG:2000/tabsTS_BODY/tabpCLAS/ssubSUBSCR_BODY:SAPLCHRG:2300/ssubSUBSCR_CLASS:SAPLCTMS:5000/tabsTABSTRIP_CHAR/tabpTAB1/ssubTABSTRIP_CHAR_GR:SAPLCTMS:5100/tblSAPLCTMSCHARS_S")
                scroll.verticalScrollbar.Position = 10
                # Define fator na posição [1,0] conforme seu script original
                session.findById("wnd[0]/usr/subSUBSCR_BATCH_MASTER:SAPLCHRG:1111/subSUBSCR_TABSTRIP:SAPLCHRG:2000/tabsTS_BODY/tabpCLAS/ssubSUBSCR_BODY:SAPLCHRG:2300/ssubSUBSCR_CLASS:SAPLCTMS:5000/tabsTABSTRIP_CHAR/tabpTAB1/ssubTABSTRIP_CHAR_GR:SAPLCTMS:5100/tblSAPLCTMSCHARS_S/ctxtRCTMS-MWERT[1,0]").Text = fator_calc
                
                session.findById("wnd[0]/tbar[0]/btn[11]").press()
                log_sys.write(f"✅ Ajustado item {i}")
            except Exception as e:
                log_sys.write(f"❌ Erro item {i}: {e}")
