import win32com.client as win32
import time
from src.utils.common import log_sys

def conectar_sap():
    try:
        SapGuiAuto = win32.GetObject("SAPGUI")
        application = SapGuiAuto.GetScriptingEngine
        connection = application.Children(0)
        session = connection.Children(0)
        log_sys.write("✅ Conectado ao SAP GUI com sucesso!")
        return session
    except Exception as e:
        log_sys.write(f"❌ Erro ao conectar ao SAP GUI: {e}")
        log_sys.write("👉 Por favor, certifique-se de que o SAP Logon está aberto e logado.")
        return None

def fechar_popups(session, keywords):
    """Trata janelas pop-up do SAP."""
    try:
        janela = session.ActiveWindow
        titulo = janela.Text.lower()
        if isinstance(keywords, str):
            keywords = [keywords]
        for kw in keywords:
            if kw.lower() in titulo:
                log_sys.write(f"🤖 Fechando popup: {titulo}")
                if "liberar" in titulo or "ordem" in titulo:
                    janela.findById("usr/btnSPOP-VAROPTION1").press() # Sim/Confirmar
                elif "determ" in titulo or "custos" in titulo:
                    session.findById("wnd[1]/usr/btnSPOP-OPTION1").press()
                elif "data" in titulo:
                    session.findById("wnd[0]").sendVKey(0)
                elif "monitor" in titulo:
                    session.findById("wnd[1]/usr/ctxtP_LGNUM").text = "sp10"
                    session.findById("wnd[1]/tbar[0]/btn[8]").press()
                elif "verific" in titulo:
                    session.findById("wnd[1]/usr/btnSPOP-VAROPTION1").press()
                    
                else:
                    janela.sendVKey(0) # Enter padrão
                time.sleep(0.5)
                return True
    except: pass
    return False
