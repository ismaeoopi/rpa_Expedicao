import win32com.client as win32
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
