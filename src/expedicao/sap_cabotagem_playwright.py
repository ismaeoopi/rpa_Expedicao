import os
import sys
import time
import re
from src.utils.common import log_sys
from src.expedicao.sap_packlist import _garantir_playwright_instalado

SAP_FO_URL = "https://appprod.sap.valgroupco.com/sap/bc/ui2/flp?sap-client=200&sap-language=EN#FreightOrder-createRoad?sap-ui-tech-hint=WDA"

def rodar_criacao_of_cabotagem_playwright(
    remessas: list, 
    transportadora: str, 
    valor_frete: float, 
    usuario: str, 
    senha: str,
    headless: bool = True
) -> str:
    """
    Executa a criação de Ordem de Frete (OF) para Cabotagem no SAP Fiori via Playwright.
    Retorna o número da Ordem de Frete gerada (string).
    """
    if not remessas:
        raise ValueError("Nenhuma remessa fornecida para criação da OF de Cabotagem.")
        
    localappdata = os.environ.get("LOCALAPPDATA", "")
    ms_playwright_dir = os.path.join(localappdata, "ms-playwright")
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = ms_playwright_dir
    
    if not _garantir_playwright_instalado():
        raise RuntimeError("Playwright/Chromium não está instalado.")
        
    from playwright.sync_api import sync_playwright
    
    playwright_instance = None
    browser = None
    of_numero = None
    
    try:
        playwright_instance = sync_playwright().start()
        # Executa no modo configurado (headless por padrão, ou headed para debug/visualização)
        browser = playwright_instance.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()
        
        log_sys.write("🔐 Acessando SAP Fiori - Criar Ordem de Frete Cabotagem...")
        page.goto(SAP_FO_URL, timeout=60000)
        
        # Login
        log_sys.write("🔐 Efetuando Login...")
        try:
            page.get_by_role("textbox", name="User").wait_for(state="visible", timeout=30000)
        except Exception:
            try:
                page.get_by_role("textbox", name="Usuário").wait_for(state="visible", timeout=5000)
            except Exception:
                raise RuntimeError("Página de login do SAP Fiori não carregou.")
        
        if page.get_by_role("textbox", name="User").is_visible():
            page.get_by_role("textbox", name="User").fill(usuario)
            page.get_by_role("textbox", name="Password").fill(senha)
            page.get_by_role("button", name="Log On").click()
        else:
            page.get_by_role("textbox", name="Usuário").fill(usuario)
            page.get_by_role("textbox", name="Senha").fill(senha)
            page.get_by_role("button", name="Logon").click()
            
        time.sleep(2)
        
        # Verifica se o login teve sucesso esperando o iframe de aplicação carregar
        log_sys.write("⏳ Aguardando carregamento da aplicação SAP Dynpro...")
        app_iframe = page.frame_locator('iframe[title="Application"]')
        
        type_input = app_iframe.get_by_role("textbox", name="Freight Order Type Value help")
        try:
            type_input.wait_for(state="visible", timeout=45000)
        except Exception:
            content = page.content().lower()
            if "senha" in content or "password" in content or "incorret" in content or "inválid" in content:
                raise ValueError("Usuário ou senha incorretos no SAP Fiori.")
            raise RuntimeError("A aplicação Dynpro não carregou no tempo limite.")
            
        log_sys.write("✅ Conectado ao SAP Dynpro de criação de Ordem de Frete.")
        
        # Preenche tipo da ordem para Cabotagem: zout
        type_input.click()
        type_input.fill("zout")
        type_input.press("Enter")
        time.sleep(2)
        
        # Inserir FUs baseadas no ID do Documento
        log_sys.write("⏳ Inserindo FUs baseadas nas remessas...")
        btn_insert = app_iframe.get_by_role("button", name="Insert Insert FUs Based on")
        btn_insert.wait_for(state="visible", timeout=20000)
        btn_insert.click()
        
        try:
            app_iframe.locator("span").filter(has_text=re.compile(r"^Insert FUs Based on Base Document ID$")).click(timeout=5000)
        except Exception:
            try:
                app_iframe.get_by_role("cell", name="Insert FUs Based on Base").click(timeout=5000)
            except Exception:
                app_iframe.get_by_text("Base Document ID").click()
        
        # Inserir as remessas do container
        txt_planning = app_iframe.get_by_role("textbox", name="String for Text Planning")
        txt_planning.wait_for(state="visible", timeout=15000)
        
        remessas_text = "\n".join([str(r).strip() for r in remessas]) + "\n"
        log_sys.write(f"📝 Inserindo {len(remessas)} remessa(s): {', '.join(remessas)}")
        txt_planning.click()
        txt_planning.fill(remessas_text)
        
        # Clicar em OK
        try:
            app_iframe.get_by_role("button", name=re.compile(r"OK.*Emphasized")).click(timeout=10000)
        except Exception:
            try:
                app_iframe.get_by_role("cell", name=re.compile(r"^OK\s+Emphasized$")).first.click(timeout=5000)
            except Exception:
                app_iframe.get_by_role("button", name="OK").click()
                
        time.sleep(4)
        
        # Acessar a aba "General Data Assignment Block"
        log_sys.write("⏳ Acessando aba General Data...")
        try:
            app_iframe.get_by_role("tab", name=re.compile(r"General Data.*Assignment Block")).click(timeout=10000)
        except Exception:
            pass
            
        # Meio de Transporte: 0007
        log_sys.write("🚚 Preenchendo Meio de Transporte: 0007")
        try:
            # Tenta clicar no seletor/input antes
            app_iframe.locator("input[name=\"WD05F5\"]").click(timeout=3000)
        except Exception:
            pass
        app_iframe.get_by_role("textbox", name="Means of Transport Value help").fill("0007")
        app_iframe.get_by_role("textbox", name="Means of Transport Value help").press("Enter")
        time.sleep(1)
        
        # Veículo: CARRETA_CAR_SIDER_LS
        log_sys.write("🚚 Preenchendo Veículo: CARRETA_CAR_SIDER_LS")
        app_iframe.get_by_role("textbox", name="Vehicle").click()
        app_iframe.get_by_role("textbox", name="Vehicle Value help available").fill("car")
        app_iframe.get_by_text("CARRETA_CAR_SIDER_LS", exact=True).click()
        time.sleep(1)
        
        # Empresa: vma1
        log_sys.write("🚚 Preenchendo Empresa: vma1")
        app_iframe.get_by_role("textbox", name="Procuring Company Code").click()
        app_iframe.get_by_role("textbox", name="Procuring Company Code Value").fill("vma1")
        
        # Transportadora (Carrier)
        log_sys.write(f"🚚 Preenchendo Transportador: {transportadora}")
        app_iframe.get_by_role("textbox", name="Carrier", exact=True).click()
        app_iframe.get_by_role("textbox", name="Carrier Value help available").fill(transportadora)
        app_iframe.get_by_role("textbox", name="Carrier Value help available").press("Enter")
        time.sleep(2)
        
        # Acessar a aba "Charges Assignment Block"
        log_sys.write("⏳ Acessando aba de Despesas (Charges)...")
        app_iframe.get_by_role("tab", name=re.compile(r"Charges.*Assignment Block")).click()
        time.sleep(2)
        
        # Selecionar todas as linhas para Expandir
        app_iframe.get_by_role("checkbox", name="Column for row selection").click()
        app_iframe.get_by_role("button", name="Expand All").click()
        time.sleep(2)
        
        # Preencher o Valor do Frete
        valor_formatado = f"{valor_frete:.2f}".replace(".", ",")
        log_sys.write(f"💰 Inserindo valor do frete: R$ {valor_formatado}")
        
        # Tenta localizar o input do valor do frete. No script padrão, é o ID #WD1347 ou similar
        input_valor = app_iframe.locator("#WD1347")
        try:
            input_valor.wait_for(state="visible", timeout=5000)
            input_valor.click()
            input_valor.fill(valor_formatado)
            input_valor.press("Enter")
        except Exception:
            # Caso o ID mude, tenta buscar um input que aceite o valor
            log_sys.write("⚠️ ID do campo #WD1347 não encontrado. Tentando localizar via classe/tipo...")
            inputs = app_iframe.locator("input[type='text']").all()
            preenchido = False
            for ipt in inputs:
                if ipt.is_visible() and ipt.is_enabled():
                    # Tenta adivinhar se é o campo correto ou simplesmente preencher o primeiro vazio numérico
                    # Normalmente há poucos inputs visíveis após Expand All na tabela de Charges
                    val_atual = ipt.input_value()
                    if "," in val_atual or val_atual == "" or val_atual == "0,00":
                        ipt.click()
                        ipt.fill(valor_formatado)
                        ipt.press("Enter")
                        preenchido = True
                        break
            if not preenchido:
                raise RuntimeError("Não foi possível localizar o campo para inserir o valor do frete (Charges).")
                
        time.sleep(1)
        
        # Salvar (Ctrl+S)
        log_sys.write("💾 Salvando Ordem de Frete (Ctrl+S)...")
        try:
            page.keyboard.press("Control+s")
            time.sleep(0.5)
            btn_save = app_iframe.get_by_role("button", name="Save (Ctrl+S) Emphasized")
            btn_save.wait_for(state="visible", timeout=10000)
            btn_save.click()
        except Exception as e:
            log_sys.write(f"⚠️ Erro ao salvar inicial: {e}")
            
        log_sys.write("⏳ Aguardando confirmação do SAP com o número da OF...")
        of_regex = re.compile(r"61\d{8}")
        max_tentativas = 12
        
        for tentativa in range(max_tentativas):
            time.sleep(2)
            log_sys.write(f"🔍 Buscando número da OF... Tentativa {tentativa + 1}/{max_tentativas}")
            
            if tentativa == 5:
                # Re-tenta salvar caso esteja travado
                try:
                    page.keyboard.press("Control+s")
                    app_iframe.get_by_role("button", name="Save (Ctrl+S) Emphasized").click(timeout=5000)
                except Exception:
                    pass
            
            # Procurar nos cabeçalhos
            try:
                headings = page.get_by_role("heading").all()
                for h in headings:
                    txt = h.text_content()
                    match = of_regex.search(txt)
                    if match:
                        of_numero = match.group(0)
                        log_sys.write(f"🎉 Número da OF localizado no cabeçalho: {of_numero}")
                        break
            except Exception:
                pass
                
            if of_numero:
                break
                
            # Procurar no texto do corpo
            try:
                body_text = page.inner_text("body")
                match = of_regex.search(body_text)
                if match:
                    of_numero = match.group(0)
                    log_sys.write(f"🎉 Número da OF localizado no corpo: {of_numero}")
                    break
            except Exception:
                pass
                
        if not of_numero:
            raise RuntimeError("Ordem de Frete não foi criada ou número não identificado. Verifique os logs no SAP.")
            
        return of_numero
        
    finally:
        try:
            if browser:
                browser.close()
        except Exception:
            pass
        try:
            if playwright_instance:
                playwright_instance.stop()
        except Exception:
            pass
