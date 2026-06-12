from src.utils.common import log_sys
from src.utils.sap_utils import conectar_sap
from src.utils.excel_utils import lerDados, colunaRemessa

def smRemessa(caminhoExcel, dados_colados=None, status_etapas=None):
    session = conectar_sap()
    if not session: return
    df = lerDados(caminhoExcel, dados_colados)
    if df is None: return
    
    for remessa, _ in df.groupby(colunaRemessa):
        log_sys.write(f"🚛 Processando SM para remessa: {remessa}")
        if status_etapas is not None and remessa in status_etapas:
            status_etapas[remessa]["sm"] = "running"
            status_etapas[remessa]["erro_detalhe"] = ""
            
        try:
            session.findById("wnd[0]").maximize()
            session.findById("wnd[0]/tbar[0]/okcd").text = "/n/scwm/prdo"
            session.findById("wnd[0]").sendVKey(0)
            session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/cmb/SCWM/S_UI_DLV-V_CRITERION").key = "REFDOCNO_ERP_I"
            session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_SEARCH_VALUE:/SCWM/SAPLUI_DLV_PRD:2003/txt/SCWM/S_SP_Q_HEAD-REFDOCNO_ERP_I").text = remessa
            session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_SEARCH_VALUE:/SCWM/SAPLUI_DLV_PRD:2003/btnCMD_GO").press()
            
            if session.findById("wnd[0]/sbar").text == 'Nenhum documento encontrado':
                log_sys.write(f"⚠️ Remessa {remessa} não localizada.")
                if status_etapas is not None and remessa in status_etapas:
                    status_etapas[remessa]["sm"] = "error"
                    status_etapas[remessa]["erro_detalhe"] = "Remessa não localizada"
                continue
 
            statusCarregar = session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_OIP_DATA_AREA:/SCWM/SAPLUI_DLV_PRD:2210/subSUB_OIP_1_CONTENT:/SCWM/SAPLUI_DLV_PRD:2211/cntlCONTAINER_ALV_OIP_1/shellcont/shell").getCellValue(0, "STATUS_LOADING")
            statusSm = session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_OIP_DATA_AREA:/SCWM/SAPLUI_DLV_PRD:2210/subSUB_OIP_1_CONTENT:/SCWM/SAPLUI_DLV_PRD:2211/cntlCONTAINER_ALV_OIP_1/shellcont/shell").getCellValue(0,"STATUS_GI")
            
            if statusSm == "Encerrada":
                log_sys.write(f"✅ Remessa {remessa} já está com SM realizado.")
                if status_etapas is not None and remessa in status_etapas:
                    status_etapas[remessa]["sm"] = "success"
                continue
                 
            if statusCarregar == "Não iniciado":
                session.findById("wnd[0]/usr/subSUB_COMPLETE_ODP1:/SCWM/SAPLUI_DLV_PRD:3000/tabsTABSTRIP_ODP1/tabpOK_ODP1_TAB12").select()
                session.findById("wnd[0]/usr/subSUB_COMPLETE_ODP1:/SCWM/SAPLUI_DLV_PRD:3000/tabsTABSTRIP_ODP1/tabpOK_ODP1_TAB12/ssubSUB_ODP1_TAB12:/SCWM/SAPLUI_DLV_CORE:3310/cntlCONTAINER_TB_ODP1_12/shellcont/shell").pressButton("ODP1_DISPLAY_TU")
                statusUT = session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_TU:2000/tabsTABSTRIP_OIP/tabpOK_OIP_TAB1/ssubSUB_OIP_TAB1:/SCWM/SAPLUI_TU:2210/ssubSUB_OIP_1_DATA:/SCWM/SAPLUI_TU:2211/cntlCONTAINER_ALV_OIP_1/shellcont/shell").getCellValue(0, "SR_ACT_STATE_TXT")
                
                if statusUT == "Ativo":
                    session.findById("wnd[0]/tbar[0]/btn[3]").press()
                    session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_OIP_DATA_AREA:/SCWM/SAPLUI_DLV_PRD:2210/cntlCONTAINER_TB_OIP_1/shellcont/shell").pressButton("OIP_LOAD")
                    session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_OIP_DATA_AREA:/SCWM/SAPLUI_DLV_PRD:2210/cntlCONTAINER_TB_OIP_1/shellcont/shell").pressButton("OIP_POST_GM")
                else:
                    session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_TU:2000/tabsTABSTRIP_OIP/tabpOK_OIP_TAB1/ssubSUB_OIP_TAB1:/SCWM/SAPLUI_TU:2210/cntlCONTAINER_TB_OIP_1/shellcont/shell").pressContextButton("OK_GOTO_YMOVE")
                    session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_TU:2000/tabsTABSTRIP_OIP/tabpOK_OIP_TAB1/ssubSUB_OIP_TAB1:/SCWM/SAPLUI_TU:2210/cntlCONTAINER_TB_OIP_1/shellcont/shell").selectContextMenuItem("OK_GOTO_OPEN_CICO")
                    session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_CICO:2000/subSUB_OIP_DATA_AREA:/SCWM/SAPLUI_CICO:2210/cntlCONTAINER_TB_OIP_1/shellcont/shell").pressButton("OK_SR27")
                    session.findById("wnd[1]/tbar[0]/btn[0]").press()
                    session.findById("wnd[0]/tbar[0]/btn[11]").press()
                    session.findById("wnd[0]/tbar[0]/btn[3]").press()
                    session.findById("wnd[0]/tbar[0]/btn[3]").press()
                    session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_OIP_DATA_AREA:/SCWM/SAPLUI_DLV_PRD:2210/cntlCONTAINER_TB_OIP_1/shellcont/shell").pressButton("OIP_LOAD")
                    session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_OIP_DATA_AREA:/SCWM/SAPLUI_DLV_PRD:2210/cntlCONTAINER_TB_OIP_1/shellcont/shell").pressButton("OIP_POST_GM")
                log_sys.write("✅ SM Realizado")
                if status_etapas is not None and remessa in status_etapas:
                    status_etapas[remessa]["sm"] = "success"
            elif statusCarregar == "Concluído":
                session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_OIP_DATA_AREA:/SCWM/SAPLUI_DLV_PRD:2210/cntlCONTAINER_TB_OIP_1/shellcont/shell").pressButton("OIP_POST_GM")
                log_sys.write("✅ SM Realizado")
                if status_etapas is not None and remessa in status_etapas:
                    status_etapas[remessa]["sm"] = "success"
        except Exception as e:
            log_sys.write(f"❌ ERRO no SM da remessa {remessa}: {e}")
            if status_etapas is not None and remessa in status_etapas:
                status_etapas[remessa]["sm"] = "error"
                status_etapas[remessa]["erro_detalhe"] = f"Erro no SM: {e}"
