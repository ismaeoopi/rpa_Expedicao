from src.utils.common import log_sys
from src.utils.sap_utils import fechar_popups
from src.utils.excel_utils import valorFloatexcel

centroP = "P716"
depOrigem = "INT"

def executar_co01_processo(session, acabado, semi, peso):
    """Lógica isolada da CO01 para não poluir o processoCompleto"""
    try:
        session.findById("wnd[0]").maximize()
        session.findById("wnd[0]/tbar[0]/okcd").text = "/nco01"
        session.findById("wnd[0]").sendVKey(0)
        session.findById("wnd[0]/usr/ctxtCAUFVD-MATNR").text = acabado
        session.findById("wnd[0]/usr/ctxtCAUFVD-WERKS").text = centroP
        session.findById("wnd[0]/usr/ctxtAUFPAR-PP_AUFART").text = "zPIN"
        session.findById("wnd[0]").sendVKey(0)
        if session.findById("wnd[0]/sbar").text != "":
            msgSbar = session.findById("wnd[0]/sbar").text
            log_sys.write(f"⚠️  {msgSbar}")
            session.findById("wnd[0]").sendVKey(0)
        
        session.findById("wnd[0]/usr/tabsTABSTRIP_0115/tabpKOZE/ssubSUBSCR_0115:SAPLCOKO1:0120/txtCAUFVD-GAMNG").text = peso
        session.findById("wnd[0]/usr/tabsTABSTRIP_0115/tabpKOZE/ssubSUBSCR_0115:SAPLCOKO1:0120/cmbCAUFVD-TERKZ").key = "4"

        session.findById("wnd[0]/usr/tabsTABSTRIP_0115/tabpKOWE").select()
        
        if session.findById("wnd[0]/sbar").text.startswith("Data de fornecimento pode ser cumprida?"):
            session.findById("wnd[0]").sendVKey(0)
        fechar_popups(session, ["Informação"])

        session.findById("wnd[0]/usr/tabsTABSTRIP_0115/tabpKOWE/ssubSUBSCR_0115:SAPLCOKO1:0190/ctxtAFPOD-LGORT").text = depOrigem

        session.findById("wnd[0]/tbar[1]/btn[5]").press()
        session.findById("wnd[0]/tbar[1]/btn[6]").press()

        # Limpeza de componentes
        session.findById("wnd[0]/usr/tblSAPLCOMKTCTRL_0120").columns.elementAt(1).selected = True
        tabela = session.findById("wnd[0]/usr/tblSAPLCOMKTCTRL_0120")
        totalLinhas = tabela.RowCount
        
        for i in range(totalLinhas):
            conteudo = session.findById(f"wnd[0]/usr/tblSAPLCOMKTCTRL_0120/ctxtRESBD-MATNR[1,{i}]").text
            if conteudo.strip() == "": break
            
            if conteudo != semi:
                session.findById(f"wnd[0]/usr/tblSAPLCOMKTCTRL_0120").getAbsoluteRow(i).selected = True
                session.findById("wnd[0]/usr/subBUTTONS:SAPLCOMK:0050/btnDELETEROW").press()
                session.findById("wnd[1]/usr/btnSPOP-VAROPTION1").press()

        session.findById("wnd[0]/usr/tblSAPLCOMKTCTRL_0120").columns.elementAt(1).selected = True
        session.findById("wnd[0]/tbar[1]/btn[25]").press() # Liberar
        fechar_popups(session, ["Liberar ordem"])
        session.findById("wnd[0]/tbar[0]/btn[11]").press() # Salvar
        fechar_popups(session, ["Determ.custos"])
        
        msg = session.findById("wnd[0]/sbar").text
        # Pega apenas os números da mensagem de sucesso
        return "".join(filter(str.isdigit, msg))

    except Exception as e:
        log_sys.write(f"❌ Erro CO01: {e}")
        return None
