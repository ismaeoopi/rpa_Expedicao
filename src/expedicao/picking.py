from src.utils.common import log_sys
from src.utils.sap_utils import conectar_sap
from src.utils.excel_utils import lerDados, colunaRemessa

logsErro = []
logsSucesso = []

def processarPicking(caminhoExcel, dados_colados=None):
    session = conectar_sap()
    if not session: return
    df = lerDados(caminhoExcel, dados_colados)
    if df is None: return
    
    remessasUnicas = df[colunaRemessa].unique()
    log_sys.write(f"🚀 Total de {len(remessasUnicas)} remessas para processar no Picking.")
    
    for remessa, grupo in df.groupby(colunaRemessa):
        log_sys.write(f"🚛 Processando remessa: {remessa}")
        try:
            session.findById("wnd[0]").maximize()
            session.findById("wnd[0]/tbar[0]/okcd").text = "/n/scwm/prdo"
            session.findById("wnd[0]").sendVKey(0)
            session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/cmb/SCWM/S_UI_DLV-V_CRITERION").key = "REFDOCNO_ERP_I"
            session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_SEARCH_VALUE:/SCWM/SAPLUI_DLV_PRD:2003/txt/SCWM/S_SP_Q_HEAD-REFDOCNO_ERP_I").text = remessa
            session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_SEARCH_VALUE:/SCWM/SAPLUI_DLV_PRD:2003/btnCMD_GO").press()
            
            texto_sbar = session.findById("wnd[0]/sbar").text
            if texto_sbar == 'Nenhum documento encontrado':
                log_sys.write(f"⚠️ AVISO: Remessa {remessa} não encontrada. Pulando...") 
                global logsErro
                logsErro.append(f"{remessa} não encontrada")
                continue

            session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_OIP_DATA_AREA:/SCWM/SAPLUI_DLV_PRD:2210/cntlCONTAINER_TB_OIP_1/shellcont/shell").pressContextButton("OIP_DETAIL_TO")
            session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_OIP_DATA_AREA:/SCWM/SAPLUI_DLV_PRD:2210/cntlCONTAINER_TB_OIP_1/shellcont/shell").selectContextMenuItem("OIP_DETAIL_TO")
            session.findById("wnd[0]/usr/subSUB_OIP:/SCWM/SAPLUI_TO_DISP:0120/subSUB_SEARCH_RESULT:/SCWM/SAPLUI_TO_DISP:0130/cntlCC_OIP/shellcont/shell").selectAll()
            session.findById("wnd[0]/usr/subSUB_OIP:/SCWM/SAPLUI_TO_DISP:0120/cntlCC_OIP_TB/shellcont/shell").pressContextButton("OIP_CALL_TO_CONF")
            session.findById("wnd[0]/usr/subSUB_OIP:/SCWM/SAPLUI_TO_DISP:0120/cntlCC_OIP_TB/shellcont/shell").selectContextMenuItem("OIP_CALL_TO_CONF")
            
            # Mapeamento estático de colunas SAP do script original
            cols = ["CHANGEABLE_ICON","WHO","STATUS_TXT","ARCHIVEFL","SUBSTFL","FLGINV","LM_ACTIVE","PROCESSOR","RSRC","QUEUE","START_DATE","START_TIME","START_FIXED","CONF_DATE","CONF_TIME","CONFIRMED_BY","WAVE","AREAWHO","WCR","PLANDURA","UNIT_T","CREA_DATE","CREA_TIME","CREATED_BY","WHOLOGNO","LSD","SPLITWHOID","MAN_ASSIGN","FLGSPLIT","START_BIN","WHO_DUMMY"]
            for col in cols:
                session.findById("wnd[0]/usr/subSUB_OIP:/SCWM/SAPLUI_TO_CONF:0120/subSUB_SEARCH_RESULT:/SCWM/SAPLUI_TO_CONF:0130/cntlCC_OIP/shellcont/shell").selectColumn(col)
                
            session.findById("wnd[0]/usr/subSUB_OIP:/SCWM/SAPLUI_TO_CONF:0120/cntlCC_OIP_TB/shellcont/shell").pressButton("OIP_CONF_SAVE")
            session.findById("wnd[0]/tbar[0]/btn[3]").press()
            session.findById("wnd[0]/tbar[0]/btn[3]").press()
            log_sys.write(f"✅ Remessa {remessa} Picking concluído.")
        except Exception as e:
            log_sys.write(f"❌ ERRO ao processar a remessa {remessa}: {e}")
