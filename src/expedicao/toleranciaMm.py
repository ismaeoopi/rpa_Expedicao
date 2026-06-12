import win32com.client as win32



SapGuiAuto = win32.GetObject("SAPGUI")
application = SapGuiAuto.GetScriptingEngine
connection = application.Children(0)
session = connection.Children(0)




session.findById("wnd[0]").maximize()
session.findById("wnd[0]/tbar[0]/okcd").text = "/nvl03n"
session.findById("wnd[0]").sendVKey(0)
session.findById("wnd[0]/usr/ctxtLIKP-VBELN").text = "80702902"
session.findById("wnd[0]").sendVKey(0)
session.findById("wnd[0]").sendVKey(2)
session.findById(r"wnd[0]/usr/tabsTAXI_TABSTRIP_ITEM/tabpT\04").select()

tolExc = session.findById(r"wnd[0]/usr/tabsTAXI_TABSTRIP_ITEM/tabpT\04/ssubSUBSCREEN_BODY:SAPMV50A:3106/txtLIPS-UEBTO").text.strip()
tolInc = session.findById(r"wnd[0]/usr/tabsTAXI_TABSTRIP_ITEM/tabpT\04/ssubSUBSCREEN_BODY:SAPMV50A:3106/txtLIPS-UNTTO").text.strip()



"""session.findById("wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\02/ssubSUBSCREEN_BODY:SAPMV50A:1104/tblSAPMV50ATC_LIPS_PICK/ctxtLIPS-MATNR[1,0]").caretPosition = 6
session.findById("wnd[0]").sendVKey(2)
session.findById("wnd[0]/usr/tabsTAXI_TABSTRIP_ITEM/tabpT\04/ssubSUBSCREEN_BODY:SAPMV50A:3106/txtLIPS-UEBTO").setFocus()
session.findById("wnd[0]/usr/tabsTAXI_TABSTRIP_ITEM/tabpT\04/ssubSUBSCREEN_BODY:SAPMV50A:3106/txtLIPS-UEBTO").caretPosition = 2
session.findById("wnd[0]").sendVKey(1)"""
