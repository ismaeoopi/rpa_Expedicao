from datetime import datetime
from src.utils.common import log_sys
from src.utils.sap_utils import conectar_sap, fechar_popups
from src.utils.excel_utils import ler_excel_universal

def localizarMon(caminho):
    inicio = datetime.now() 
    df = ler_excel_universal(caminho, "Localizar Mon", 1)
    if df is None: return
    session = conectar_sap()
    if not session: return
    logErro = []    
    session.findById("wnd[0]").maximize()
    session.findById("wnd[0]/tbar[0]/okcd").text = "/n/scwm/mon"
    session.findById("wnd[0]").sendVKey(0)
    fechar_popups(session, ["Monitor"])

    try:
        for _, row in df.iterrows():
            uc = row['UC']
            posicao = row['Localização']
            tipo = row['Tipo']

            session.findById("wnd[0]/usr/shell/shellcont[0]/shell").selectedNode = "N000000039"
            session.findById("wnd[0]/usr/shell/shellcont[0]/shell").doubleClickNode("N000000039")
            session.findById("wnd[1]/usr/ctxtS_HUIDEN-LOW").text = uc

            session.findById("wnd[1]/tbar[0]/btn[8]").press()
            texto_sbar = session.findById("wnd[0]/sbar").text
            if  texto_sbar == 'Nenhum objeto correspondente aos critérios de seleção':
                log_sys.write(f"⚠️ AVISO: Remessa {uc} não encontrada. Pulando...") 
                logErro.append(f"{uc} não encontrada")
                continue
            log_sys.write(f"UC {uc} movida para {posicao}")
            session.findById("wnd[0]/usr/shell/shellcont[1]/shell/shellcont[0]/shell").setCurrentCell(-1, "")
            session.findById("wnd[0]/usr/shell/shellcont[1]/shell/shellcont[0]/shell").selectAll()
            session.findById("wnd[0]/usr/shell/shellcont[1]/shell/shellcont[0]/shell").pressToolbarContextButton("METHODS")
            session.findById("wnd[0]/usr/shell/shellcont[1]/shell/shellcont[0]/shell").selectContextMenuItem("@M00008")
            session.findById("wnd[1]/usr/chk/SCWM/S_ASP_HU_AD-SQUIT").selected = True
            session.findById("wnd[1]/usr/ctxt/SCWM/S_ASP_HU_AD-NLTYP").text = tipo
            session.findById("wnd[1]/usr/ctxt/SCWM/S_ASP_HU_AD-NLPLA").text = posicao
            session.findById("wnd[1]/usr/ctxt/SCWM/S_ASP_HU_AD-PROCTY").text = "y999"
            session.findById("wnd[1]/usr/chk/SCWM/S_ASP_HU_AD-SQUIT").setFocus()
            session.findById("wnd[1]/tbar[0]/btn[8]").press()
        for erro in logErro:
            log_sys.write("\n⚠️  Erros encontrados:")
            log_sys.write(f"❌ Erro: {erro}")
        logErro = [] 
        final = datetime.now() - inicio
        log_sys.write(f"\n🏁 Processo concluído em {final}!")
        log_sys.write("\n🏁 Processo concluído!\n")  
    except Exception as e:
        log_sys.write(f"❌ Erro ao localizar Mon: {e}")
        for erro in logErro:
            log_sys.write("\n⚠️  Erros encontrados:")
            log_sys.write(f"❌ Erro: {erro}")
        logErro = [] 
        return  
