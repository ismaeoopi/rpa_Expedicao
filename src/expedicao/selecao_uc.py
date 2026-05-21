import time
from src.utils.common import log_sys
from src.utils.sap_utils import conectar_sap
from src.utils.excel_utils import lerDados, colunaRemessa, colunaUc, valorFloatPy, valorFloatexcel

logsErro = []
logsSucesso = []

def filtrarUcs(session, grupo):
    try:
        session.findById("wnd[0]/usr/subSUB_COMPLETE_ODP:/SCWM/SAPLUI_TODLV:4000/tabsGV_TAB_ODP/tabpOK_TAB_ODP_AVSTKDLV/ssubSUB_ODP_AVSTKDLV:/SCWM/SAPLUI_TODLV:4400/subSUB_ODP_AVSTKDLV_DATA:/SCWM/SAPLUI_TODLV:4410/cntlCC_ALV_OD_AVSTKDLV/shellcont/shell").selectColumn("HUIDENT")
        session.findById("wnd[0]/usr/subSUB_COMPLETE_ODP:/SCWM/SAPLUI_TODLV:4000/tabsGV_TAB_ODP/tabpOK_TAB_ODP_AVSTKDLV/ssubSUB_ODP_AVSTKDLV:/SCWM/SAPLUI_TODLV:4400/subSUB_ODP_AVSTKDLV_DATA:/SCWM/SAPLUI_TODLV:4410/cntlCC_ALV_OD_AVSTKDLV/shellcont/shell").pressToolbarButton("&MB_FILTER")
        session.findById("wnd[1]/usr/ssub%_SUBSCREEN_FREESEL:SAPLSSEL:1105/btn%_%%DYN001_%_APP_%-VALU_PUSH").press()
        
        scroll = 0
        for _, i in grupo.iterrows():
            uc = i[colunaUc]
            if scroll == 0:
                campoUC = "wnd[2]/usr/tabsTAB_STRIP/tabpSIVA/ssubSCREEN_HEADER:SAPLALDB:3010/tblSAPLALDBSINGLE/ctxtRSCSEL_255-SLOW_I[1,0]"
                session.findById(campoUC).text = uc
            else:
                session.findById("wnd[2]/usr/tabsTAB_STRIP/tabpSIVA/ssubSCREEN_HEADER:SAPLALDB:3010/tblSAPLALDBSINGLE").verticalScrollbar.position = scroll
                campoUC = "wnd[2]/usr/tabsTAB_STRIP/tabpSIVA/ssubSCREEN_HEADER:SAPLALDB:3010/tblSAPLALDBSINGLE/ctxtRSCSEL_255-SLOW_I[1,1]"
                session.findById(campoUC).text = uc
            scroll += 1
            
        session.findById("wnd[2]/tbar[0]/btn[0]").press()
        session.findById("wnd[2]/tbar[0]/btn[8]").press()
        session.findById("wnd[1]/tbar[0]/btn[0]").press()
        return True
    except Exception as e:
        log_sys.write(f"❌ Erro ao filtrar as UC's: {e}")
        return False

def processarRemessaComUc(caminhoExcel, dados_colados=None):
    session = conectar_sap()
    if not session: return
    df = lerDados(caminhoExcel, dados_colados)
    if df is None: return
    
    global logsErro, logsSucesso
    remessasUnicas = df[colunaRemessa].unique()
    log_sys.write(f"🚀 Total de {len(remessasUnicas)} remessas para Seleção via UC.")
    
    for remessa, grupo in df.groupby(colunaRemessa):
        log_sys.write(f"🚛 Processando remessa: {remessa}")
        ucs = []; pesoUcs = 0; i = 0; scroll = 0; qtdUc = len(grupo); qtd = 0
        try:
            session.findById("wnd[0]").maximize()
            session.findById("wnd[0]/tbar[0]/okcd").text = "/n/scwm/prdo"
            session.findById("wnd[0]").sendVKey(0)
            session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/cmb/SCWM/S_UI_DLV-V_CRITERION").key = "REFDOCNO_ERP_I"
            session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_SEARCH_VALUE:/SCWM/SAPLUI_DLV_PRD:2003/txt/SCWM/S_SP_Q_HEAD-REFDOCNO_ERP_I").text = remessa
            session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_SEARCH_VALUE:/SCWM/SAPLUI_DLV_PRD:2003/btnCMD_GO").press()
            
            if session.findById("wnd[0]/sbar").text == 'Nenhum documento encontrado':
                log_sys.write(f"⚠️ AVISO: Remessa {remessa} não localizada.")
                logsErro.append(f"{remessa} não encontrada")
                continue

            session.findById("wnd[0]/usr/subSUB_COMPLETE_ODP1:/SCWM/SAPLUI_DLV_PRD:3000/tabsTABSTRIP_ODP1/tabpOK_ODP1_TAB1/ssubSUB_ODP1_TAB1:/SCWM/SAPLUI_DLV_CORE:3210/ssubSUB_ODP1_1_CONTENT:/SCWM/SAPLUI_DLV_CORE:3211/cntlCONTAINER_ALV_ODP1_1/shellcont/shell").currentCellColumn = "QTY_UI"
            session.findById("wnd[0]/usr/subSUB_COMPLETE_ODP1:/SCWM/SAPLUI_DLV_PRD:3000/tabsTABSTRIP_ODP1/tabpOK_ODP1_TAB1/ssubSUB_ODP1_TAB1:/SCWM/SAPLUI_DLV_CORE:3210/ssubSUB_ODP1_1_CONTENT:/SCWM/SAPLUI_DLV_CORE:3211/cntlCONTAINER_ALV_ODP1_1/shellcont/shell").clearSelection()
            session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_OIP_DATA_AREA:/SCWM/SAPLUI_DLV_PRD:2210/cntlCONTAINER_TB_OIP_1/shellcont/shell").pressButton("OIP_CHANGE")
            session.findById("wnd[0]/usr/subSUB_COMPLETE_ODP1:/SCWM/SAPLUI_DLV_PRD:3000/tabsTABSTRIP_ODP1/tabpOK_ODP1_TAB1/ssubSUB_ODP1_TAB1:/SCWM/SAPLUI_DLV_CORE:3210/ssubSUB_ODP1_1_CONTENT:/SCWM/SAPLUI_DLV_CORE:3211/cntlCONTAINER_ALV_ODP1_1/shellcont/shell").pressEnter()
            
            pesoRemessa = valorFloatPy(session.findById("wnd[0]/usr/subSUB_COMPLETE_ODP1:/SCWM/SAPLUI_DLV_PRD:3000/tabsTABSTRIP_ODP1/tabpOK_ODP1_TAB1/ssubSUB_ODP1_TAB1:/SCWM/SAPLUI_DLV_CORE:3210/ssubSUB_ODP1_1_CONTENT:/SCWM/SAPLUI_DLV_CORE:3211/cntlCONTAINER_ALV_ODP1_1/shellcont/shell").getCellValue(0,"QTY_UI"))
            ilimitado = session.findById("wnd[0]/usr/subSUB_COMPLETE_ODP1:/SCWM/SAPLUI_DLV_PRD:3000/tabsTABSTRIP_ODP1/tabpOK_ODP1_TAB1/ssubSUB_ODP1_TAB1:/SCWM/SAPLUI_DLV_CORE:3210/ssubSUB_ODP1_1_CONTENT:/SCWM/SAPLUI_DLV_CORE:3211/cntlCONTAINER_ALV_ODP1_1/shellcont/shell").getCellValue(0,"PART_DEL_UNLTD")

            if ilimitado == "X":
                pesoRemessaMin = pesoRemessa - (pesoRemessa * valorFloatPy(10) / 100)
                pesoRemessaMax = (pesoRemessa * valorFloatPy(10) / 100) + pesoRemessa
            else:
                tolerancia = session.findById("wnd[0]/usr/subSUB_COMPLETE_ODP1:/SCWM/SAPLUI_DLV_PRD:3000/tabsTABSTRIP_ODP1/tabpOK_ODP1_TAB1/ssubSUB_ODP1_TAB1:/SCWM/SAPLUI_DLV_CORE:3210/ssubSUB_ODP1_1_CONTENT:/SCWM/SAPLUI_DLV_CORE:3211/cntlCONTAINER_ALV_ODP1_1/shellcont/shell").getCellValue(0,"TOL_UNDERPCT")
                pesoRemessaMin = pesoRemessa - (pesoRemessa * valorFloatPy(tolerancia) / 100)
                tolerancia = session.findById("wnd[0]/usr/subSUB_COMPLETE_ODP1:/SCWM/SAPLUI_DLV_PRD:3000/tabsTABSTRIP_ODP1/tabpOK_ODP1_TAB1/ssubSUB_ODP1_TAB1:/SCWM/SAPLUI_DLV_CORE:3210/ssubSUB_ODP1_1_CONTENT:/SCWM/SAPLUI_DLV_CORE:3211/cntlCONTAINER_ALV_ODP1_1/shellcont/shell").getCellValue(0, "TOL_OVERPCT")
                pesoRemessaMax = (pesoRemessa * valorFloatPy(tolerancia) / 100) + pesoRemessa

            log_sys.write(f"P.Min: {pesoRemessaMin} | P.Max: {pesoRemessaMax} | Peso Alvo: {pesoRemessa}")
            
            session.findById("wnd[0]/usr/subSUB_COMPLETE_ODP1:/SCWM/SAPLUI_DLV_PRD:3000/tabsTABSTRIP_ODP1/tabpOK_ODP1_TAB1/ssubSUB_ODP1_TAB1:/SCWM/SAPLUI_DLV_CORE:3210/cntlCONTAINER_TB_ODP1_1/shellcont/shell").pressButton("OK_ODP1_TOGGLE")
            dep = session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_OIP_DATA_AREA:/SCWM/SAPLUI_DLV_PRD:2210/subSUB_OIP_1_CONTENT:/SCWM/SAPLUI_DLV_PRD:2211/cntlCONTAINER_ALV_OIP_1/shellcont/shell").getCellValue(0,"LGNUM")
            
            procty_path = "wnd[0]/usr/subSUB_COMPLETE_ODP1:/SCWM/SAPLUI_DLV_PRD:3000/tabsTABSTRIP_ODP1/tabpOK_ODP1_TAB1/ssubSUB_ODP1_TAB1:/SCWM/SAPLUI_DLV_CORE:3210/ssubSUB_ODP1_1_CONTENT:/SCWM/SAPLUI_DLV_PRD:3212/ctxt/SCWM/S_SP_A_ITEM_PRDO-/SCWM/PROCTY"
            session.findById(procty_path).text = "Y214" if dep == "ITP1" else "O001"
            session.findById("wnd[0]").sendVKey(0)
            
            session.findById("wnd[0]/tbar[0]/btn[11]").press()
            session.findById("wnd[0]").sendVKey(25)
            session.findById("wnd[0]/usr/subSUB_COMPLETE_ODP:/SCWM/SAPLUI_TODLV:4000/tabsGV_TAB_ODP/tabpOK_TAB_ODP_DEFDLV").select()
            session.findById("wnd[0]/usr/subSUB_COMPLETE_ODP:/SCWM/SAPLUI_TODLV:4000/tabsGV_TAB_ODP/tabpOK_TAB_ODP_DEFDLV/ssubSUB_ODP_DEFDLV:/SCWM/SAPLUI_TODLV:4300/subSUB_ODP_DEFDLV_DATA:/SCWM/SAPLUI_TODLV:4311/subSUB_ODP_DEFDLV_LOC:/SCWM/SAPLUI_TODLV:4312/ctxt/SCWM/S_ASP_TODLV_OD_DEFDLV-VLTYP").text = "pa01"
            session.findById("wnd[0]/usr/subSUB_COMPLETE_ODP:/SCWM/SAPLUI_TODLV:4000/tabsGV_TAB_ODP/tabpOK_TAB_ODP_AVSTKDLV").select()
            
            if not filtrarUcs(session, grupo):
                logsErro.append(f"{remessa} Erro ao filtrar as UC's")
                continue

            qtdUcReal = session.findById("wnd[0]/usr/subSUB_COMPLETE_ODP:/SCWM/SAPLUI_TODLV:4000/tabsGV_TAB_ODP/tabpOK_TAB_ODP_AVSTKDLV/ssubSUB_ODP_AVSTKDLV:/SCWM/SAPLUI_TODLV:4400/subSUB_ODP_AVSTKDLV_DATA:/SCWM/SAPLUI_TODLV:4410/cntlCC_ALV_OD_AVSTKDLV/shellcont/shell").RowCount
            if (qtdUcReal - 1) < qtdUc:
                logsErro.append(f"{remessa} Divergência na qtd de UCs SAP x Planilha")
                continue
                
            while qtd < (qtdUcReal - 1):
                shell_grid = session.findById("wnd[0]/usr/subSUB_COMPLETE_ODP:/SCWM/SAPLUI_TODLV:4000/tabsGV_TAB_ODP/tabpOK_TAB_ODP_AVSTKDLV/ssubSUB_ODP_AVSTKDLV:/SCWM/SAPLUI_TODLV:4400/subSUB_ODP_AVSTKDLV_DATA:/SCWM/SAPLUI_TODLV:4410/cntlCC_ALV_OD_AVSTKDLV/shellcont/shell")
                pesoPalete = valorFloatPy(shell_grid.getCellValue(i,"UI_AVLQTY_A"))
                pesoUcs += pesoPalete 
                ucs.append(shell_grid.getCellValue(i,"HUIDENT"))
                i += 1
                shell_grid.firstVisibleRow = scroll
                scroll += 1
                qtd += 1
                
            if pesoUcs < pesoRemessaMin or pesoRemessaMax < pesoUcs:
                log_sys.write("❌ Peso fora da tolerância. Verifique as UCs.")
                logsErro.append(f"{remessa} fora da tolerância")
                continue

            if pesoUcs != pesoRemessa: 
                session.findById("wnd[0]/tbar[0]/btn[3]").press()
                session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_OIP_DATA_AREA:/SCWM/SAPLUI_DLV_PRD:2210/cntlCONTAINER_TB_OIP_1/shellcont/shell").pressButton("OIP_CHANGE")
                time.sleep(1)
                pesoUcs_str = valorFloatexcel(pesoUcs)
                session.findById("wnd[0]/usr/subSUB_COMPLETE_ODP1:/SCWM/SAPLUI_DLV_PRD:3000/tabsTABSTRIP_ODP1/tabpOK_ODP1_TAB1/ssubSUB_ODP1_TAB1:/SCWM/SAPLUI_DLV_CORE:3210/ssubSUB_ODP1_1_CONTENT:/SCWM/SAPLUI_DLV_PRD:3212/txt/SCWM/S_SP_A_ITEM_PRDO-QTY_UI").text = pesoUcs_str
                session.findById("wnd[0]/tbar[0]/btn[11]").press()
                session.findById("wnd[0]").sendVKey(25)
                session.findById("wnd[0]/usr/subSUB_COMPLETE_ODP:/SCWM/SAPLUI_TODLV:4000/tabsGV_TAB_ODP/tabpOK_TAB_ODP_DEFDLV").select()
                session.findById("wnd[0]/usr/subSUB_COMPLETE_ODP:/SCWM/SAPLUI_TODLV:4000/tabsGV_TAB_ODP/tabpOK_TAB_ODP_DEFDLV/ssubSUB_ODP_DEFDLV:/SCWM/SAPLUI_TODLV:4300/subSUB_ODP_DEFDLV_DATA:/SCWM/SAPLUI_TODLV:4311/subSUB_ODP_DEFDLV_LOC:/SCWM/SAPLUI_TODLV:4312/ctxt/SCWM/S_ASP_TODLV_OD_DEFDLV-VLTYP").text = "pa01"
                session.findById("wnd[0]/usr/subSUB_COMPLETE_ODP:/SCWM/SAPLUI_TODLV:4000/tabsGV_TAB_ODP/tabpOK_TAB_ODP_AVSTKDLV").select()
                if not filtrarUcs(session, grupo): continue
                
            session.findById("wnd[0]/usr/subSUB_COMPLETE_ODP:/SCWM/SAPLUI_TODLV:4000/tabsGV_TAB_ODP/tabpOK_TAB_ODP_AVSTKDLV/ssubSUB_ODP_AVSTKDLV:/SCWM/SAPLUI_TODLV:4400/subSUB_ODP_AVSTKDLV_DATA:/SCWM/SAPLUI_TODLV:4410/cntlCC_ALV_OD_AVSTKDLV/shellcont/shell").selectAll()
            session.findById("wnd[0]/usr/subSUB_COMPLETE_ODP:/SCWM/SAPLUI_TODLV:4000/tabsGV_TAB_ODP/tabpOK_TAB_ODP_AVSTKDLV/ssubSUB_ODP_AVSTKDLV:/SCWM/SAPLUI_TODLV:4400/cntlCC_TB_ODP_AVSTKDLV/shellcont/shell").pressButton("OK_OD_AVSTKDLV_SPLIT_QTY")
            session.findById("wnd[0]/usr/subSUB_COMPLETE_ODP:/SCWM/SAPLUI_TODLV:4000/tabsGV_TAB_ODP/tabpOK_TAB_ODP_AVSTKDLV/ssubSUB_ODP_AVSTKDLV:/SCWM/SAPLUI_TODLV:4400/cntlCC_TB_ODP_AVSTKDLV/shellcont/shell").pressButton("OK_OD_AVSTKDLV_TAKE_QTY")
            session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_TODLV:1000/tabsGV_TAB_OIP/tabpOK_TAB_OIP_DLV/ssubSUB_OIP_DLV:/SCWM/SAPLUI_TODLV:3100/cntlCC_TB_OIP_DLV/shellcont/shell").pressButton("OK_OI_DLV_CREATE_AND_SAVE")
            session.findById("wnd[0]/tbar[0]/btn[3]").press()
            log_sys.write(f"✅ Remessa {remessa} Seleção concluída com sucesso.")
            logsSucesso.append(remessa)
        except Exception as e:
            log_sys.write(f"❌ ERRO GERAL na remessa {remessa}: {e}")
