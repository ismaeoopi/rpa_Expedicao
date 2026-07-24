import os
import openpyxl
import win32com.client as win32
import win32com.client
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from src.utils.common import log_sys
from src.utils.sap_utils import conectar_sap
import base64
from io import BytesIO
from reportlab.lib.utils import ImageReader
from .logo import LOGO_BASE64

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
    try:
        dados_imagem = base64.b64decode(LOGO_BASE64)
        buffer_imagem = BytesIO(dados_imagem)
        imagem_para_pdf = ImageReader(buffer_imagem)

        largura_img = 150
        altura_img = 35
        pos_x_imagem = (largura - largura_img) / 2
        pos_y_imagem = centroY + 250

        c.drawImage(imagem_para_pdf, pos_x_imagem, pos_y_imagem,
                    width=largura_img, height=altura_img, mask='auto')
    except Exception as e:
        print(f"Erro ao processar imagem: {e}")
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

    pasta_destino = os.path.normpath(pasta_destino)
    os.makedirs(pasta_destino, exist_ok=True)
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
