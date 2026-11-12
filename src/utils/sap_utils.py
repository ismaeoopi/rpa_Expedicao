import time
from src.utils.common import log_sys

def _garantir_desktop_interativo():
    try:
        import win32service, win32con
        hwinsta = win32service.OpenWindowStation('WinSta0', False, win32con.MAXIMUM_ALLOWED)
        hwinsta.SetProcessWindowStation()
        hdesk = win32service.OpenDesktop('default', 0, False, win32con.MAXIMUM_ALLOWED)
        hdesk.SetThreadDesktop()
    except Exception:
        pass
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except Exception:
        pass

def conectar_sap(session_index=0):
    _garantir_desktop_interativo()
    try:
        import win32com.client as win32
        SapGuiAuto = win32.GetObject("SAPGUI")
        application = SapGuiAuto.GetScriptingEngine
        if not application:
            log_sys.write("❌ ScriptingEngine do SAP não está habilitado ou disponível.")
            log_sys.write("👉 Verifique as opções do SAP GUI (Opções -> Acessibilidade e Scripting -> Scripting -> Habilitar criação de scripts).")
            return None

        if not hasattr(application, "Children") or application.Children.Count == 0:
            log_sys.write("❌ SAP GUI está aberto, mas nenhuma conexão foi iniciada.")
            log_sys.write("👉 Dê um duplo clique na conexão (ex: PRD) no SAP Logon e faça o login.")
            return None

        connection = application.Children(0)
        if not hasattr(connection, "Children") or connection.Children.Count <= session_index:
            log_sys.write(f"❌ Nenhuma sessão ativa encontrada no SAP no índice {session_index}.")
            return None

        session = connection.Children(session_index)
        log_sys.write("✅ Conectado ao SAP GUI com sucesso!")
        return session
    except Exception as e:
        eh_rot_vazia = False
        if hasattr(e, 'args') and e.args and e.args[0] == -2147221020:
            eh_rot_vazia = True
        elif "-2147221020" in str(e) or "Invalid syntax" in str(e):
            eh_rot_vazia = True

        if eh_rot_vazia:
            log_sys.write("❌ O SAP GUI não está em execução ou não possui nenhuma janela/sessão aberta.")
        else:
            log_sys.write(f"❌ Erro ao conectar ao SAP GUI: {e}")

        log_sys.write("👉 Por favor, certifique-se de que o SAP Logon está aberto e com login ativo na tela do SAP.")
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
