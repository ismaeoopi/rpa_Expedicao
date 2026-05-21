import os
import threading
import queue
import win32gui
import win32con
import win32com.client as win32
import pythoncom
import pywintypes
from src.utils.common import log_sys

def abrir_seletor_ficheiro_excel():
    """
    Abre GetOpenFileNameW numa thread STA dedicada, para funcionar
    corretamente quando chamada a partir de uma thread do Flask.
    """
    result_q = queue.Queue()

    def _dialog_thread():
        # 1) STA é OBRIGATÓRIO para diálogos comuns do Windows
        pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
        try:
            # 2) Filtro: pares "descrição\\0padrão\\0", terminado por \\0 extra.
            file_filter = (
                "Arquivos Excel (*.xlsx;*.xls)\0*.xlsx;*.xls\0"
                "Todos os ficheiros (*.*)\0*.*\0"
            )

            # Pasta inicial: Downloads do utilizador
            initial_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            if not os.path.isdir(initial_dir):
                initial_dir = os.path.expanduser("~")

            # 3) Flags: explorer moderno + ficheiro tem de existir
            flags = (
                win32con.OFN_EXPLORER
                | win32con.OFN_FILEMUSTEXIST
                | win32con.OFN_PATHMUSTEXIST
                | win32con.OFN_HIDEREADONLY
                | win32con.OFN_NOCHANGEDIR
            )

            try:
                fname, customfilter, flags_out = win32gui.GetOpenFileNameW(
                    InitialDir=initial_dir,
                    Flags=flags,
                    Title="Selecione o arquivo Excel",
                    Filter=file_filter,
                    DefExt="xlsx",
                    File="",                 # nome inicial vazio
                    MaxFile=2048,            # buffer suficientemente grande
                )
                result_q.put(fname or "")
            except pywintypes.error as e:
                # Código 0 = utilizador cancelou; qualquer outro = erro real
                if getattr(e, "winerror", 0) == 0:
                    result_q.put("")
                else:
                    result_q.put(("__ERROR__", str(e)))
        except Exception as e:
            result_q.put(("__ERROR__", str(e)))
        finally:
            pythoncom.CoUninitialize()

    # 4) daemon=True para não prender o processo se algo correr mal
    t = threading.Thread(target=_dialog_thread, daemon=True)
    t.start()
    t.join(timeout=600)  # até 10 min para o utilizador escolher

    if t.is_alive():
        log_sys.write("⚠️ Diálogo de seleção ainda aberto após timeout.")
        return ""

    try:
        res = result_q.get_nowait()
    except queue.Empty:
        return ""

    # Propaga erro real para o log
    if isinstance(res, tuple) and res and res[0] == "__ERROR__":
        log_sys.write(f"❌ Erro no GetOpenFileNameW: {res[1]}")
        return ""

    return res if (res and os.path.isfile(res)) else ""

def abrir_seletor_pasta():
    """
    Abre a caixa de diálogo nativa do Windows para selecionar uma pasta.
    Usa Shell.Application.BrowseForFolder (funciona em qualquer thread).
    """
    try:
        pythoncom.CoInitialize()  # CRÍTICO para usar COM fora da main thread
        try:
            shell_obj = win32com.client.Dispatch("Shell.Application")
            # Flags: 1 = somente pastas do sistema de arquivos | 64 = mostrar campo "Nova Pasta"
            folder_obj = shell_obj.BrowseForFolder(
                0,
                "Selecione a pasta de destino para os PDFs",
                1 | 64
            )
            if folder_obj:
                return folder_obj.Self.Path
            return ""
        finally:
            pythoncom.CoUninitialize()
    except Exception as e:
        log_sys.write(f"❌ Erro ao abrir seletor de pasta: {e}")
        return ""
