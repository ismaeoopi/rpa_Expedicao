import win32com.client as win32
import pandas as pd
import time
import sys

SapGuiAuto = win32.GetObject("SAPGUI")
application = SapGuiAuto.GetScriptingEngine
connection = application.Children(0)
session = connection.Children(0) 

session.findById("wnd[0]").maximize()
session.findById("wnd[0]/tbar[0]/okcd").text = "/ncs15"
session.findById("wnd[0]").sendVKey(0)
session.findById("wnd[0]/usr/chkRC29L-DIRKT").selected = True
semiAcabado= input("Digite o item semi acabado: ")
session.findById("wnd[0]/usr/ctxtRC29L-MATNR").text = semiAcabado

session.findById("wnd[0]/tbar[1]/btn[5]").press()
session.findById("wnd[0]/usr/ctxtRC29L-WERKS").text = "P716"

session.findById("wnd[0]/tbar[1]/btn[8]").press()
texto_status = session.findById("wnd[0]/sbar").text
if "Nenhuma" in texto_status:
    print("Material sem roteiro, favor verificar")
    sys.exit()
totaldeLinha = session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell").rowCount

semiAcabado = session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell/shellcont[1]/shell").getCellValue(0,"MATNR")
print(semiAcabado, totaldeLinha)
