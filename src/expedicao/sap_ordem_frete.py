import os
import sys
import time
import re
from src.utils.common import log_sys
from src.expedicao.sap_packlist import _garantir_playwright_instalado

SAP_FO_URL = "https://appprod.sap.valgroupco.com/sap/bc/ui2/flp?sap-client=200&sap-language=EN#FreightOrder-createRoad?sap-ui-tech-hint=WDA"

def rodar_criacao_of_playwright(remessas: list, usuario: str, senha: str) -> str:
    """
    Executa a criação de Ordem de Frete (OF) no SAP Fiori via Playwright.
    Retorna o número da Ordem de Frete gerada (string).
    """
    if not remessas:
        raise ValueError("Nenhuma remessa fornecida para criação da OF.")
        
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
        # Executa em modo oculto (headless)
        browser = playwright_instance.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        log_sys.write("🔐 Acessando SAP Fiori - Criar Ordem de Frete...")
        page.goto(SAP_FO_URL, timeout=60000)
        
        # Login
        log_sys.write("🔐 Efetuando Login...")
        try:
            page.get_by_role("textbox", name="User").wait_for(state="visible", timeout=30000)
        except Exception:
            # Caso esteja em português
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
        
        # Preenche tipo da ordem (zcro)
        type_input.click()
        type_input.fill("zcro")
        
        # Tenta selecionar a sugestão correspondente na lista
        try:
            app_iframe.locator("div").filter(has_text="Freight Order TypeFreight").nth(4).click(timeout=3000)
        except Exception:
            pass
            
        type_input.click()
        type_input.press("Enter")
        
        # Clica na aba "Items Assignment Block"
        log_sys.write("⏳ Clicando na aba de Itens...")
        try:
            app_iframe.get_by_role("tab", name=re.compile(r"Items.*Assignment Block")).click(timeout=10000)
        except Exception:
            pass

        # Espera o botão "Insert Insert FUs Based on" aparecer
        log_sys.write("⏳ Aguardando botões de inserção de Unidades de Frete...")
        btn_insert = app_iframe.get_by_role("button", name="Insert Insert FUs Based on")
        btn_insert.wait_for(state="visible", timeout=20000)
        btn_insert.click()
        
        # Seleciona a opção "Insert FUs Based on Base Document ID"
        try:
            app_iframe.locator("span").filter(has_text=re.compile(r"^Insert FUs Based on Base Document ID$")).click(timeout=5000)
        except Exception:
            app_iframe.get_by_role("cell", name="Insert FUs Based on Base").click()
        
        # Espera a caixa de diálogo abrir e o campo "String for Text Planning" carregar
        txt_planning = app_iframe.get_by_role("textbox", name="String for Text Planning")
        txt_planning.wait_for(state="visible", timeout=15000)
        
        # Preenche com as remessas separadas por nova linha
        remessas_text = "\n".join(remessas) + "\n"
        log_sys.write(f"📝 Inserindo {len(remessas)} remessa(s) no campo de planejamento...")
        txt_planning.click()
        txt_planning.fill(remessas_text)
        
        # Clica em OK
        try:
            app_iframe.get_by_role("cell", name=re.compile(r"^OK\s+Emphasized$")).first.click(timeout=10000)
        except Exception:
            try:
                app_iframe.get_by_role("cell", name="OK\xa0 Emphasized", exact=True).first.click(timeout=5000)
            except Exception:
                app_iframe.get_by_role("cell", name=re.compile(r"OK.*Emphasized")).last.click()
        
        log_sys.write("⏳ Vinculando Unidades de Frete à Ordem de Frete...")
        time.sleep(4)  # Espera para carregar
        
        # Collapse All, Level, Checkbox
        log_sys.write("⚙️ Selecionando todas as linhas atribuídas...")
        try:
            app_iframe.get_by_role("button", name="Collapse All").click(timeout=5000)
            time.sleep(1)
            app_iframe.get_by_role("button", name="Level").click(timeout=5000)
            time.sleep(1)
        except Exception:
            pass
            
        app_iframe.get_by_role("checkbox", name="Column for row selection").click()
        
        # Conta a quantidade de linhas selecionadas para atender ao feedback
        try:
            num_checkboxes = app_iframe.get_by_role("checkbox").count()
            # O cabeçalho e a linha de seleção geral somam, então fazemos num_checkboxes - 2 se for maior que 2
            linhas_selecionadas = max(0, num_checkboxes - 2)
            log_sys.write(f"📊 Foram selecionadas {linhas_selecionadas} linha(s) na tabela do SAP.")
        except Exception as e:
            log_sys.write(f"⚠️ Não foi possível contar as linhas: {e}")
            
        # Salvar (Ctrl+S)
        log_sys.write("💾 Salvando Ordem de Frete (Ctrl+S)...")
        try:
            # 1. Envia o atalho de teclado Ctrl+S diretamente na página
            page.keyboard.press("Control+s")
            log_sys.write("✅ Atalho Ctrl+S enviado.")
            time.sleep(0.5)
            
            # 2. Clica no botão de Salvar físico
            btn_save = app_iframe.get_by_role("button", name="Save (Ctrl+S) Emphasized")
            btn_save.wait_for(state="visible", timeout=10000)
            btn_save.click()
            log_sys.write("✅ Clique no botão de salvar enviado.")
        except Exception as e:
            log_sys.write(f"⚠️ Erro no envio inicial de salvar: {e}")
            
        log_sys.write("⏳ Aguardando confirmação do SAP com o número da OF (polling de 2s em 2s)...")
        
        of_regex = re.compile(r"61\d{8}")
        of_numero = None
        max_tentativas = 12  # 12 * 2s = 24s total
        
        for tentativa in range(max_tentativas):
            time.sleep(2)
            log_sys.write(f"🔍 Buscando número da OF... Tentativa {tentativa + 1}/{max_tentativas}")
            
            # Se chegarmos na metade e não acharmos a OF, re-tentamos pressionar Salvar
            if tentativa == 5:
                log_sys.write("⚠️ OF não localizada até agora. Tentando forçar o comando de Salvar (Ctrl+S) novamente...")
                try:
                    # Tenta disparar atalho de teclado na página
                    page.keyboard.press("Control+s")
                    # Tenta clicar fisicamente de novo
                    app_iframe.get_by_role("button", name="Save (Ctrl+S) Emphasized").click(timeout=5000)
                    log_sys.write("✅ Comando de salvar re-enviado.")
                except Exception as ex:
                    log_sys.write(f"⚠️ Erro ao re-enviar salvamento: {ex}")
            
            # 1. Procurar nas tags de cabeçalho
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
                
            # 2. Procurar no texto do corpo
            try:
                body_text = page.inner_text("body")
                match = of_regex.search(body_text)
                if match:
                    of_numero = match.group(0)
                    log_sys.write(f"🎉 Número da OF localizado no corpo da página: {of_numero}")
                    break
            except Exception:
                pass
                
        if not of_numero:
            raise RuntimeError("Ordem de Frete não foi criada ou número não foi identificado. Verifique os logs no SAP.")
            
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


def rodar_criacao_of_playwright_multipla(grupos: list, usuario: str, senha: str) -> list:
    """
    Executa a criação de múltiplas Ordens de Frete (OF) no SAP Fiori via Playwright,
    reutilizando a mesma sessão do navegador e realizando apenas refresh na página.
    Retorna uma lista de dicionários contendo os resultados para cada grupo de remessas.
    """
    if not grupos:
        return []
        
    localappdata = os.environ.get("LOCALAPPDATA", "")
    ms_playwright_dir = os.path.join(localappdata, "ms-playwright")
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = ms_playwright_dir
    
    if not _garantir_playwright_instalado():
        raise RuntimeError("Playwright/Chromium não está instalado.")
        
    from playwright.sync_api import sync_playwright
    
    playwright_instance = None
    browser = None
    resultados = []
    
    try:
        playwright_instance = sync_playwright().start()
        # Executa em modo oculto (headless)
        browser = playwright_instance.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        log_sys.write("🔐 Acessando SAP Fiori - Criar Múltiplas Ordens de Frete...")
        page.goto(SAP_FO_URL, timeout=60000)
        
        # Login
        log_sys.write("🔐 Efetuando Login...")
        try:
            page.get_by_role("textbox", name="User").wait_for(state="visible", timeout=30000)
        except Exception:
            try:
                page.get_by_role("textbox", name="Usuário").wait_for(state="visible", timeout=5000)
            except Exception:
                pass
        
        if page.get_by_role("textbox", name="User").is_visible():
            page.get_by_role("textbox", name="User").fill(usuario)
            page.get_by_role("textbox", name="Password").fill(senha)
            page.get_by_role("button", name="Log On").click()
        elif page.get_by_role("textbox", name="Usuário").is_visible():
            page.get_by_role("textbox", name="Usuário").fill(usuario)
            page.get_by_role("textbox", name="Senha").fill(senha)
            page.get_by_role("button", name="Logon").click()
            
        time.sleep(2)
        
        for idx, remessas in enumerate(grupos):
            log_sys.write(f"💼 Processando Grupo [{idx + 1}/{len(grupos)}] | Remessas: {', '.join(remessas)}")
            
            try:
                # Se não for o primeiro grupo, dá refresh na página
                if idx > 0:
                    log_sys.write("⏳ Recarregando página para o próximo cliente...")
                    page.goto(SAP_FO_URL, timeout=60000)
                    time.sleep(2)
                
                # Aguarda o iframe de aplicação carregar
                log_sys.write("⏳ Aguardando carregamento da aplicação SAP Dynpro...")
                app_iframe = page.frame_locator('iframe[title="Application"]')
                
                type_input = app_iframe.get_by_role("textbox", name="Freight Order Type Value help")
                try:
                    type_input.wait_for(state="visible", timeout=45000)
                except Exception:
                    content = page.content().lower()
                    if "senha" in content or "password" in content or "incorret" in content or "inválid" in content:
                        raise ValueError("Usuário ou senha incorretos no SAP Fiori.")
                    
                    # Tenta dar reload se falhar no carregamento inicial da página do próximo cliente
                    log_sys.write("⚠️ Timeout na aplicação. Tentando atualizar a página...")
                    page.reload(timeout=60000)
                    time.sleep(3)
                    type_input.wait_for(state="visible", timeout=30000)
                    
                log_sys.write("✅ Conectado ao SAP Dynpro de criação de Ordem de Frete.")
                
                # Preenche tipo da ordem (zcro)
                type_input.click()
                type_input.fill("zcro")
                
                # Tenta selecionar a sugestão correspondente na lista
                try:
                    app_iframe.locator("div").filter(has_text="Freight Order TypeFreight").nth(4).click(timeout=3000)
                except Exception:
                    pass
                    
                type_input.click()
                type_input.press("Enter")
                
                # Clica na aba "Items Assignment Block"
                log_sys.write("⏳ Clicando na aba de Itens...")
                try:
                    app_iframe.get_by_role("tab", name=re.compile(r"Items.*Assignment Block")).click(timeout=10000)
                except Exception:
                    pass
        
                # Espera o botão "Insert Insert FUs Based on" aparecer
                log_sys.write("⏳ Aguardando botões de inserção de Unidades de Frete...")
                btn_insert = app_iframe.get_by_role("button", name="Insert Insert FUs Based on")
                btn_insert.wait_for(state="visible", timeout=20000)
                btn_insert.click()
                
                # Seleciona a opção "Insert FUs Based on Base Document ID"
                try:
                    app_iframe.locator("span").filter(has_text=re.compile(r"^Insert FUs Based on Base Document ID$")).click(timeout=5000)
                except Exception:
                    app_iframe.get_by_role("cell", name="Insert FUs Based on Base").click()
                
                # Espera a caixa de diálogo abrir e o campo "String for Text Planning" carregar
                txt_planning = app_iframe.get_by_role("textbox", name="String for Text Planning")
                txt_planning.wait_for(state="visible", timeout=15000)
                
                # Preenche com as remessas separadas por nova linha
                remessas_text = "\n".join(remessas) + "\n"
                log_sys.write(f"📝 Inserindo {len(remessas)} remessa(s) no campo de planejamento...")
                txt_planning.click()
                txt_planning.fill(remessas_text)
                
                # Clica em OK
                try:
                    app_iframe.get_by_role("cell", name=re.compile(r"^OK\s+Emphasized$")).first.click(timeout=10000)
                except Exception:
                    try:
                        app_iframe.get_by_role("cell", name="OK\xa0 Emphasized", exact=True).first.click(timeout=5000)
                    except Exception:
                        app_iframe.get_by_role("cell", name=re.compile(r"OK.*Emphasized")).last.click()
                
                log_sys.write("⏳ Vinculando Unidades de Frete à Ordem de Frete...")
                time.sleep(4)  # Espera para carregar
                
                # Collapse All, Level, Checkbox
                log_sys.write("⚙️ Selecionando todas as linhas atribuídas...")
                try:
                    app_iframe.get_by_role("button", name="Collapse All").click(timeout=5000)
                    time.sleep(1)
                    app_iframe.get_by_role("button", name="Level").click(timeout=5000)
                    time.sleep(1)
                except Exception:
                    pass
                    
                app_iframe.get_by_role("checkbox", name="Column for row selection").click()
                
                # Conta a quantidade de linhas selecionadas para atender ao feedback
                try:
                    num_checkboxes = app_iframe.get_by_role("checkbox").count()
                    # O cabeçalho e a linha de seleção geral somam, então fazemos num_checkboxes - 2 se for maior que 2
                    linhas_selecionadas = max(0, num_checkboxes - 2)
                    log_sys.write(f"📊 Foram selecionadas {linhas_selecionadas} linha(s) na tabela do SAP.")
                except Exception as e:
                    log_sys.write(f"⚠️ Não foi possível contar as linhas: {e}")
                    
                # Salvar (Ctrl+S)
                log_sys.write("💾 Salvando Ordem de Frete (Ctrl+S)...")
                try:
                    page.keyboard.press("Control+s")
                    log_sys.write("✅ Atalho Ctrl+S enviado.")
                    time.sleep(0.5)
                    
                    btn_save = app_iframe.get_by_role("button", name="Save (Ctrl+S) Emphasized")
                    btn_save.wait_for(state="visible", timeout=10000)
                    btn_save.click()
                    log_sys.write("✅ Clique no botão de salvar enviado.")
                except Exception as e:
                    log_sys.write(f"⚠️ Erro no envio inicial de salvar: {e}")
                    
                log_sys.write("⏳ Aguardando confirmação do SAP com o número da OF (polling de 2s em 2s)...")
                
                of_regex = re.compile(r"61\d{8}")
                of_numero = None
                max_tentativas = 12  # 12 * 2s = 24s total
                
                for tentativa in range(max_tentativas):
                    time.sleep(2)
                    log_sys.write(f"🔍 Buscando número da OF... Tentativa {tentativa + 1}/{max_tentativas}")
                    
                    if tentativa == 5:
                        log_sys.write("⚠️ OF não localizada até agora. Tentando forçar o comando de Salvar (Ctrl+S) novamente...")
                        try:
                            page.keyboard.press("Control+s")
                            app_iframe.get_by_role("button", name="Save (Ctrl+S) Emphasized").click(timeout=5000)
                            log_sys.write("✅ Comando de salvar re-enviado.")
                        except Exception as ex:
                            log_sys.write(f"⚠️ Erro ao re-enviar salvamento: {ex}")
                    
                    # 1. Procurar nas tags de cabeçalho
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
                        
                    # 2. Procurar no texto do corpo
                    try:
                        body_text = page.inner_text("body")
                        match = of_regex.search(body_text)
                        if match:
                            of_numero = match.group(0)
                            log_sys.write(f"🎉 Número da OF localizado no corpo da página: {of_numero}")
                            break
                    except Exception:
                        pass
                        
                if not of_numero:
                    raise RuntimeError("Ordem de Frete não foi criada ou número não foi identificado. Verifique os logs no SAP.")
                
                resultados.append({
                    "remessas": remessas,
                    "of": of_numero,
                    "erro": None
                })
                
            except Exception as item_err:
                log_sys.write(f"❌ Erro ao criar OF para o grupo de remessas {', '.join(remessas)}: {item_err}")
                resultados.append({
                    "remessas": remessas,
                    "of": None,
                    "erro": str(item_err)
                })
                
        return resultados
        
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
