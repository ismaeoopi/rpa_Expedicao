import os
import sys
import threading
import time
import subprocess
from datetime import datetime
import pandas as pd
import openpyxl
import win32com
import win32com.client as win32
import win32gui
import win32con
from flask import Flask, render_template, jsonify, request
#import webview
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
import base64
from io import BytesIO
import io
from reportlab.lib.utils import ImageReader
import tkinter as tk
from tkinter import filedialog

# --- MECANISMO AUTOMÁTICO DE ATUALIZAÇÃO (SEM DEPENDÊNCIAS) ---
try:
    import updater
    updater.check_for_updates()
except Exception as e:
    print(f"Erro ao verificar atualizações: {e}")

# --- CONFIGURAÇÃO FLASK PARA PATH AMBIENTE EM EXECUTÁVEL ---
if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

template_folder = os.path.join(base_dir, 'templates')
app = Flask(__name__, template_folder=template_folder)

# --- GERENCIADOR DE LOGS PARA A INTERFACE ---
class LogBuffer:
    def __init__(self):
        self.logs = []
        self.is_running = False

    def write(self, msg):
        clean_msg = str(msg).strip()
        if clean_msg:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.logs.append(f"[{timestamp}] {clean_msg}")
            print(f"[{timestamp}] {clean_msg}") # Mantém no terminal do desenvolvedor

    def fetch_new(self):
        to_return = list(self.logs)
        self.logs.clear()
        return to_return

log_sys = LogBuffer()

# --- VARIÁVEIS GLOBAIS DO RPA ORIGINAL ---
LOGO_BASE64 = ""
ABA = "Picking"
colunaRemessa = "REMESSA"
colunaUc = "UC"
logsErro = []
logsSucesso = []

# --- ADAPTAÇÃO DAS FUNÇÕES ORIGINAIS (CONVERSÃO DE PRINT PARA LOG) ---
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

def valorFloatexcel(valor):
    if pd.isna(valor) or valor is None or str(valor).strip() == "":
        return ""
    valor_str = str(valor).strip()
    if "," in valor_str:
        valorParaFloat = valor_str.replace(".","").replace(",",".")
    else:
        valorParaFloat = valor_str
    try:
        valorRound = round(float(valorParaFloat),3)
        return f"{valorRound:.3f}".replace('.',',')
    except ValueError:
        log_sys.write(f"Erro ao converter o valor '{valor}' para float.")
        return 0.0

def valorFloatPy(valor):
    if valor is None:
        return 0.0
    valorStr = str(valor).strip()
    if not valorStr:
        return 0.0
    valorStr = valorStr.replace(".","").replace(",",".")
    try:
        return round(float(valorStr),3)
    except ValueError:
        log_sys.write(f"Erro ao converter o valor '{valor}' para float.")
        return 0.0

def lerExcel(caminho):
    caminhoAbsoluto = os.path.abspath(caminho)
    log_sys.write(f"📂 Lendo planilha em: {caminhoAbsoluto}")
    try:
        df = pd.read_excel(caminhoAbsoluto, sheet_name=ABA, dtype=str)
        df.dropna(subset=[colunaRemessa], inplace=True)
        log_sys.write(f"✅ Planilha lida com sucesso: {len(df)} linhas para processar.")
        return df
    except FileNotFoundError:
        log_sys.write(f"❌ ERRO: O arquivo '{caminhoAbsoluto}' não foi encontrado.")
        return None
    except PermissionError:
        log_sys.write("❌ ERRO: Permissão negada. A planilha está aberta! Feche-a para continuar.")
        return None
    except Exception as e:
        log_sys.write(f"❌ ERRO ao ler a planilha: {e}")
        return None

def lerDados(caminhoExcel, dados_colados=None):
    if dados_colados and str(dados_colados).strip():
        try:
            log_sys.write("📄 Lendo dados colados diretamente da interface...")
            df = pd.read_csv(io.StringIO(dados_colados), sep='\t', dtype=str)
            df.columns = [str(c).strip().upper() for c in df.columns]
            if colunaRemessa not in df.columns:
                 log_sys.write(f"❌ ERRO: Coluna '{colunaRemessa}' não encontrada nos dados colados.")
                 return None
            df.dropna(subset=[colunaRemessa], inplace=True)
            log_sys.write(f"✅ Dados colados lidos com sucesso: {len(df)} linhas para processar.")
            return df
        except Exception as e:
            log_sys.write(f"❌ ERRO ao processar dados colados: {e}")
            return None
    else:
        return lerExcel(caminhoExcel)

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

def smRemessa(caminhoExcel, dados_colados=None):
    session = conectar_sap()
    if not session: return
    df = lerDados(caminhoExcel, dados_colados)
    if df is None: return
    
    for remessa, _ in df.groupby(colunaRemessa):
        log_sys.write(f"🚛 Processando SM para remessa: {remessa}")
        try:
            session.findById("wnd[0]").maximize()
            session.findById("wnd[0]/tbar[0]/okcd").text = "/n/scwm/prdo"
            session.findById("wnd[0]").sendVKey(0)
            session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/cmb/SCWM/S_UI_DLV-V_CRITERION").key = "REFDOCNO_ERP_I"
            session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_SEARCH_VALUE:/SCWM/SAPLUI_DLV_PRD:2003/txt/SCWM/S_SP_Q_HEAD-REFDOCNO_ERP_I").text = remessa
            session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_SEARCH_VALUE:/SCWM/SAPLUI_DLV_PRD:2003/btnCMD_GO").press()
            
            if session.findById("wnd[0]/sbar").text == 'Nenhum documento encontrado':
                log_sys.write(f"⚠️ Remessa {remessa} não localizada.")
                continue

            statusCarregar = session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_OIP_DATA_AREA:/SCWM/SAPLUI_DLV_PRD:2210/subSUB_OIP_1_CONTENT:/SCWM/SAPLUI_DLV_PRD:2211/cntlCONTAINER_ALV_OIP_1/shellcont/shell").getCellValue(0, "STATUS_LOADING")
            statusSm = session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_OIP_DATA_AREA:/SCWM/SAPLUI_DLV_PRD:2210/subSUB_OIP_1_CONTENT:/SCWM/SAPLUI_DLV_PRD:2211/cntlCONTAINER_ALV_OIP_1/shellcont/shell").getCellValue(0,"STATUS_GI")
            
            if statusSm == "Encerrada":
                log_sys.write(f"✅ Remessa {remessa} já está com SM realizado.")
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
            elif statusCarregar == "Concluído":
                session.findById("wnd[0]/usr/subSUB_COMPLETE_OIP:/SCWM/SAPLUI_DLV_PRD:2000/subSUB_OIP_DATA_AREA:/SCWM/SAPLUI_DLV_PRD:2210/cntlCONTAINER_TB_OIP_1/shellcont/shell").pressButton("OIP_POST_GM")
                log_sys.write("✅ SM Realizado")
        except Exception as e:
            log_sys.write(f"❌ ERRO no SM da remessa {remessa}: {e}")

def process_shipment(session, shipment):
    session.findById("wnd[0]/tbar[0]/okcd").text = "/nvl03n"
    session.findById("wnd[0]").sendVKey(0)
    session.findById("wnd[0]/usr/ctxtLIKP-VBELN").text = shipment
    session.findById("wnd[0]").sendVKey(0)
    
    anzpk = int(session.findById(r"wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\01/ssubSUBSCREEN_BODY:SAPMV50A:1102/txtLIKP-ANZPK").text)
    customer_first_name = ""; city = ""; state = ""; invoice_number = ""
    
    try:
        session.findById("wnd[0]/tbar[0]/btn[3]").press()
        session.findById("wnd[0]/tbar[1]/btn[7]").press()
        session.findById("wnd[0]/usr/shell/shellcont[1]/shell[0]").pressButton("&FIND")
        session.findById("wnd[1]/usr/txtGS_SEARCH-VALUE").text = "FATURA"
        session.findById("wnd[1]").sendVKey(0)
        session.findById("wnd[1]/tbar[0]/btn[0]").press()
        session.findById("wnd[1]/tbar[0]/btn[0]").press()
        session.findById("wnd[0]/tbar[1]/btn[8]").press()
        session.findById("wnd[0]/tbar[1]/btn[16]").press()
        
        grid = session.findById("wnd[1]/usr/cntlCONTAINER/shellcont/shell")
        grid.currentCellRow = 1; grid.selectedRows = "1"; grid.doubleClickCurrentCell()
        
        invoice_number = session.findById("wnd[0]/usr/subNF_NUMBER:SAPLJ1BB2:2002/txtJ_1BDYDOC-NFENUM").text
        session.findById("wnd[0]/tbar[0]/btn[3]").press()
        session.findById("wnd[1]").close()
        session.findById("wnd[0]/tbar[0]/btn[3]").press()
        session.findById("wnd[0]/tbar[0]/btn[3]").press()
        session.findById("wnd[0]").sendVKey(0)
        session.findById("wnd[0]/usr/subSUBSCREEN_HEADER:SAPMV50A:1502/btnBT_WADR_T").press()
        
        name_full = session.findById("wnd[1]/usr/subGCS_ADDRESS:SAPLSZA1:0300/subCOUNTRY_SCREEN:SAPLSZA1:0301/txtADDR1_DATA-NAME1").text
        customer_first_name = name_full.strip().split()[0] if name_full else ""
        city = session.findById("wnd[1]/usr/subGCS_ADDRESS:SAPLSZA1:0300/subCOUNTRY_SCREEN:SAPLSZA1:0301/txtADDR1_DATA-CITY1").text
        state = session.findById("wnd[1]/usr/subGCS_ADDRESS:SAPLSZA1:0300/subCOUNTRY_SCREEN:SAPLSZA1:0301/ctxtADDR1_DATA-REGION").text
        session.findById("wnd[1]").close()
    except Exception as e:
        log_sys.write(f"Aviso: Erro ao coletar dados do cliente para a remessa {shipment}: {e}")

    session.findById("wnd[0]/tbar[1]/btn[18]").press()
    if anzpk > 1:
        session.findById("wnd[0]/usr/tabsTS_HU_VERP/tabpUE6HUS").select()
    else:
        session.findById("wnd[0]/tbar[0]/btn[3]").press()
        session.findById("wnd[0]/usr/tabsTS_HU_VERP/tabpUE6HUS").select()

    ucs = []
    for row in range(anzpk):
        session.findById("wnd[0]/usr/tabsTS_HU_VERP/tabpUE6HUS/ssubTAB:SAPLV51G:6020/tblSAPLV51GTC_HU_003").verticalScrollbar.position = row
        ucs.append(session.findById("wnd[0]/usr/tabsTS_HU_VERP/tabpUE6HUS/ssubTAB:SAPLV51G:6020/tblSAPLV51GTC_HU_003/ctxtV51VE-EXIDV[0,0]").text)
        
    session.findById("wnd[0]/tbar[0]/btn[3]").press()
    session.findById("wnd[0]/tbar[0]/btn[3]").press()
    return customer_first_name, invoice_number, city, state, ucs

def gerar_pdf_etiqueta(pasta_destino, cidade, estado, nf, uc):
    nome_arquivo = f"Etiqueta_NF_{nf}_UC_{uc}.pdf"
    caminho_arquivo = os.path.join(pasta_destino, nome_arquivo)
    c = canvas.Canvas(caminho_arquivo, pagesize=landscape(A4))
    largura, altura = landscape(A4)
    centro_x = largura / 2
    centroY = altura / 2

    c.setFont("Helvetica-Bold", 65)
    c.drawCentredString(centro_x, centroY, f"{cidade} - {estado}")
    c.setFont("Helvetica", 50)
    c.drawCentredString(centro_x, centroY - 60, f"NF {nf}")
    c.setFont("Helvetica", 24)
    c.drawCentredString(centro_x + centro_x - 210, 10, f"UC: {uc}")
    c.save()
    log_sys.write(f"PDF gerado com sucesso: {nome_arquivo}")

def salvarFIP(shipments_input, pasta_destino=None):
    shipments = [s.strip() for s in shipments_input.split(',')]
    log_sys.write("Conectando ao SAP para extrair dados...")
    session = conectar_sap()
    if not session: return

    all_data = []
    for ship in shipments:
        log_sys.write(f"Coletando dados da remessa {ship}...")
        customer, invoice, city, state, ucs = process_shipment(session, ship)
        for uc in ucs:
            all_data.append({"Shipment": ship, "Invoice": invoice, "Customer": customer, "City": city, "State": state, "UC": uc})

    if not all_data:
        log_sys.write("❌ Nenhum dado/UC foi encontrado nas remessas.")
        return

    # Se nenhuma pasta foi passada, usa o seletor nativo
    if not pasta_destino:
        log_sys.write("Por favor, selecione na janela nativa a pasta de destino dos arquivos.")
        shell = win32com.client.Dispatch("Shell.Application")
        folder_obj = shell.BrowseForFolder(0, "Selecione a pasta desejada", 1 | 64)
        
        if not folder_obj:
            log_sys.write("❌ Nenhuma pasta selecionada. Operação abortada.")
            return
            
        pasta_destino = folder_obj.Self.Path
    else:
        log_sys.write(f"✅ Usando pasta de destino selecionada: {pasta_destino}")

    caminho_excel = os.path.join(pasta_destino, "ucs_extraidas.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Shipment", "Invoice", "Customer", "City", "State", "UC"])
    for row in all_data:
        ws.append([row["Shipment"], row["Invoice"], row["Customer"], row["City"], row["State"], row["UC"]])
    wb.save(caminho_excel)
    log_sys.write(f"Planilha Excel salva em: {caminho_excel}")

    log_sys.write("Iniciando a geração das etiquetas PDF...")
    for item in all_data:
        cidade = item["City"] if item["City"] else "CIDADE NÃO ENCONTRADA"
        estado = item["State"] if item["State"] else "XX"
        nf = item["Invoice"] if item["Invoice"] else "S/N"
        gerar_pdf_etiqueta(pasta_destino, cidade, estado, nf, item["UC"])
        
    log_sys.write("✅ Processo finalizado com sucesso!")

# --- FUNÇÕES PARA SELEÇÃO DE FICHEIROS NATIVOS DO WINDOWS ---
def abrir_seletor_ficheiro_excel():
    """
    Abre a caixa de diálogo nativa do Windows para selecionar um Excel.
    Usa pywin32 (funciona em qualquer thread, ao contrário do tkinter).
    """
    try:
        import pythoncom
        pythoncom.CoInitialize()  # Necessário para usar COM em thread secundária
        try:
            # Cria um diálogo COM nativo via Shell
            from win32com.shell import shell, shellcon
            
            # Usa o GetOpenFileNameW da API do Windows (mais simples e robusto)
            import win32gui
            filtro = "Arquivos Excel (*.xlsx;*.xls)\0*.xlsx;*.xls\0Todos (*.*)\0*.*\0"
            customfilter = "Outros\0*.*\0"
            try:
                fname, customfilter_out, flags = win32gui.GetOpenFileNameW(
                    InitialDir=os.path.expanduser("~\\Downloads"),
                    Flags=0x00080000 | 0x00001000,  # OFN_EXPLORER | OFN_FILEMUSTEXIST
                    Title="Selecione o arquivo Excel",
                    Filter=filtro,
                    CustomFilter=customfilter,
                    FilterIndex=1,
                )
                return fname if fname else ""
            except Exception:
                return ""
        finally:
            pythoncom.CoUninitialize()
    except Exception as e:
        log_sys.write(f"❌ Erro ao abrir seletor de ficheiro: {e}")
        return ""

def abrir_seletor_pasta():
    """
    Abre a caixa de diálogo nativa do Windows para selecionar uma pasta.
    Usa Shell.Application.BrowseForFolder (funciona em qualquer thread).
    """
    try:
        import pythoncom
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

# --- ROTAS DA API FLASK PARA INTEGRAÇÃO FRONTEND ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/inicializar', methods=['GET'])
def inicializar():
    usuario_completo = os.getlogin()
    primeiro_nome = usuario_completo.split('.')[0].capitalize()
    hora_atual = datetime.now().hour
    saudacao = "Bom dia" if 5 <= hora_atual < 12 else "Boa tarde" if 12 <= hora_atual < 18 else "Boa noite"
    return jsonify({"nome": primeiro_nome, "saudacao": saudacao})

@app.route('/api/selecionar_arquivo', methods=['GET'])
def selecionar_arquivo():
    """
    Abre a caixa de diálogo nativa do Windows para selecionar um ficheiro Excel.
    Retorna o caminho do ficheiro selecionado.
    """
    caminho = abrir_seletor_ficheiro_excel()
    if caminho:
        nome_ficheiro = os.path.basename(caminho)
        log_sys.write(f"📂 Ficheiro Excel selecionado: {nome_ficheiro}")
    else:
        log_sys.write("⚠️ Nenhum ficheiro Excel foi selecionado.")
    
    return jsonify({"caminho": caminho})

@app.route('/api/selecionar_pasta', methods=['GET'])
def selecionar_pasta():
    """
    Abre a caixa de diálogo nativa do Windows para selecionar uma pasta de destino.
    Retorna o caminho da pasta selecionada.
    """
    caminho = abrir_seletor_pasta()
    if caminho:
        nome_pasta = os.path.basename(caminho)
        log_sys.write(f"📁 Pasta de destino selecionada: {nome_pasta}")
    else:
        log_sys.write("⚠️ Nenhuma pasta foi selecionada.")
    
    return jsonify({"caminho": caminho})

@app.route('/api/executar', methods=['POST'])
def executar():
    dados = request.json
    opcao = int(dados.get('opcao'))
    caminho = dados.get('caminho', '')
    dados_colados = dados.get('dados_colados', '')
    remessas = dados.get('remessas', '')
    caminho_pasta = dados.get('caminho_pasta', '')

    if log_sys.is_running:
        return jsonify({"status": "error", "message": "Já existe uma automação em andamento."}), 400

    def worker():
        log_sys.is_running = True
        try:
            if opcao == 1:
                processarRemessaComUc(caminho, dados_colados)
            elif opcao == 2:
                processarPicking(caminho, dados_colados)
            elif opcao == 3:
                smRemessa(caminho, dados_colados)
            elif opcao == 4:
                salvarFIP(remessas, caminho_pasta if caminho_pasta else None)
        except Exception as e:
            log_sys.write(f"❌ Falha fatal na thread do processo: {e}")
        finally:
            log_sys.is_running = False

    t = threading.Thread(target=worker)
    t.daemon = True
    t.start()
    return jsonify({"status": "started"})

@app.route('/api/logs', methods=['GET'])
def buscar_logs():
    return jsonify({
        "novos_logs": log_sys.fetch_new(),
        "rodando": log_sys.is_running
    })

if __name__ == '__main__':
    print("=" * 60)
    print("🚛 RPA Expedição - Painel de Controle v1.0.5")
    print("=" * 60)
    print("📡 Servidor iniciando em: http://127.0.0.1:5000")
    print("👉 Abra esse endereço no navegador (Chrome/Edge)")
    print("=" * 60)
    
    # Abre o navegador automaticamente após 1.5s
    import webbrowser
    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    
    # Sobe o Flask (uma vez só, na thread principal)
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False, threaded=True)