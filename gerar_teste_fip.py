import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode import code128
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors

def gerar_pdf_teste_fip(caminho_pdf):
    # Dimensões da página A4
    largura, altura = A4
    c = canvas.Canvas(caminho_pdf, pagesize=A4)
    
    # --- Margens e Guias ---
    margem_esquerda = 40
    largura_util = largura - (margem_esquerda * 2) # 595.27 - 80 = 515.27
    
    # --- Cabeçalho (Foco no Cliente) ---
    y = altura - 60
    
    # Faixa decorativa no topo (azul escuro premium)
    c.setFillColor(colors.HexColor("#1A365D"))
    c.rect(margem_esquerda, y, largura_util, 8, fill=True, stroke=False)
    
    y -= 40
    # Nome do Cliente (Maior destaque - Centralizado)
    c.setFont("Helvetica-Bold", 36)
    c.setFillColor(colors.black)
    c.drawCentredString(largura / 2, y, "BRF SA")
    
    y -= 30
    # Unidade (Logo abaixo, menor mas em destaque - Centralizada)
    c.setFont("Helvetica-Bold", 20)
    c.setFillColor(colors.black)
    c.drawCentredString(largura / 2, y, "BRF LAJEAD2")
    
    # --- Identificação da Unidade de Carga (UC) ---
    # Trazendo o código de barras mais próximo do cabeçalho
    y -= 70
    
    # Conversão de milímetros para pontos (ReportLab usa pontos: 72 pontos = 1 polegada, 1 polegada = 25.4 mm)
    mm = 72 / 25.4
    
    # Gerando código de barras UC (número padrão de 18 dígitos)
    uc_numero = "112345676001089633"
    
    # Medidas exatas conforme engenharia do código de barras:
    # - Altura das barras: 20 mm
    # - Largura do módulo (barra estreita): 0.33 mm
    # - Margens silenciosas (laterais brancas): Mínimo de 6 mm de cada lado
    # - Largura Total resultante: ~56.2 mm (entre 55 mm e 65 mm)
    # O ReportLab Code128 realiza a compactação numérica (Subset C) automaticamente para dígitos pares.
    barcode = code128.Code128(
        uc_numero,
        barHeight=10 * mm,
        barWidth=0.90 * mm,
        lquiet=6 * mm,
        rquiet=6 * mm
    )
    
    # Centralizar o código de barras
    largura_barcode = barcode.width
    pos_x_barcode = margem_esquerda + (largura_util - largura_barcode) / 2
    
    # Desenhar código de barras no canvas
    barcode.drawOn(c, pos_x_barcode, y)
    
    # Exibir número da UC legível logo abaixo do código de barras (sem o prefixo 'UC:')
    y -= 25
    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(colors.black)
    c.drawCentredString(largura / 2, y, f"{uc_numero}")
    
    y -= 30
    c.line(margem_esquerda, y, margem_esquerda + largura_util, y)
    
    # --- Dados Técnicos (Grid) ---
    y -= 30
    
    # Grid background styling (Sem barra de título, apenas container clean com fundo suave)
    c.setFillColor(colors.HexColor("#F8FAFC")) # Slate-50 background
    c.rect(margem_esquerda, y - 375, largura_util, 375, fill=True, stroke=True)
    
    # Linhas de grade e dados
    # Cada tupla em dados: (label, valor, label_negrito, valor_negrito)
    dados = [
        [("OP:", "1000477624", False, True), ("Pedido:", "113176894", False, False)],
        [("Produto:", "676858", False, True), ("NF:", "16090", True, True)],
        [("Medida:", "800X0,020MM", False, False), ("Qtd:", "28,15 KM", False, False)],
        [("Peso Bruto:", "515 KG", False, False), ("Peso Liq:", "454,5 KG", False, True)],
        [("Fab.:", "05/09/2026", False, False), ("Val.:", "05/08/2028", False, False)]
    ]
    
    row_y = y - 30
    for idx, row in enumerate(dados):
        col1_label, col1_val, col1_lbl_bold, col1_val_bold = row[0]
        col2_label, col2_val, col2_lbl_bold, col2_val_bold = row[1]
        
        c.setFillColor(colors.black)
        
        # Coluna 1
        c.setFont("Helvetica-Bold" if col1_lbl_bold else "Helvetica", 15)
        c.drawString(margem_esquerda + 20, row_y, col1_label)
        c.setFont("Helvetica-Bold" if col1_val_bold else "Helvetica", 15)
        c.drawString(margem_esquerda + 130, row_y, col1_val)
        
        # Coluna 2
        c.setFont("Helvetica-Bold" if col2_lbl_bold else "Helvetica", 15)
        c.drawString(margem_esquerda + 280, row_y, col2_label)
        c.setFont("Helvetica-Bold" if col2_val_bold else "Helvetica", 15)
        c.drawString(margem_esquerda + 380, row_y, col2_val)
        
        # Linha horizontal sutil entre as linhas de dados
        row_y -= 15
        c.setStrokeColor(colors.HexColor("#E2E8F0"))
        c.line(margem_esquerda + 10, row_y, margem_esquerda + largura_util - 10, row_y)
        row_y -= 35
        
        # Se for a linha de Medida e Qtd (idx == 2), insere a UC abreviada abaixo dela
        if idx == 2:
            row_y -= 50
            c.setFont("Helvetica-Bold", 60)
            c.setFillColor(colors.black)
            # uc_numero[8:] é a UC abreviada a partir do 9º dígito (índice 8)
            c.drawCentredString(largura / 2, row_y, uc_numero[8:])
            
            row_y -= 20
            c.setStrokeColor(colors.HexColor("#E2E8F0"))
            c.line(margem_esquerda + 10, row_y, margem_esquerda + largura_util - 10, row_y)
            row_y -= 35
        
    # --- Rodapé ---
    import base64
    from io import BytesIO
    from reportlab.lib.utils import ImageReader
    from src.expedicao.logo import LOGO_BASE64

    try:
        cm = 72 / 2.54
        dados_imagem = base64.b64decode(LOGO_BASE64)
        buffer_imagem = BytesIO(dados_imagem)
        imagem_para_pdf = ImageReader(buffer_imagem)

        largura_img = 7.89 * cm
        altura_img = 1.84 * cm
        pos_x_imagem = (largura - largura_img) / 2
        pos_y_imagem = 45

        c.drawImage(imagem_para_pdf, pos_x_imagem, pos_y_imagem,
                    width=largura_img, height=altura_img, mask='auto')
    except Exception as e:
        print(f"Erro ao processar imagem: {e}")

    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.black)
    c.drawCentredString(largura / 2, 32, "INDUSTRIA DE EMBALAGENS LTDA.")

    c.setFont("Helvetica", 7)
    c.drawCentredString(largura / 2, 20, "Feito no Brasil / Made in Brazil / Hecho en Brasil")
    
    c.save()
    print(f"Ficha de teste PDF gerada com sucesso em: {caminho_pdf}")

if __name__ == "__main__":
    caminho_saida = os.path.join(os.getcwd(), "Ficha_Teste_FIP.pdf")
    gerar_pdf_teste_fip(caminho_saida)
