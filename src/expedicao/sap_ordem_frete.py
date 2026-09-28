import os
import sys
import time
import re
from src.utils.common import log_sys
from src.expedicao.sap_packlist import _garantir_playwright_instalado

SAP_FO_URL = "https://appprod.sap.valgroupco.com/sap/bc/ui2/flp?sap-client=200&sap-language=EN#FreightOrder-createRoad?sap-ui-tech-hint=WDA"

def aguardar_fim_carregamento_sap(app_iframe, timeout: int = 30000) -> None:
    """Aguarda o overlay de carregamento do SAP desaparecer dentro do iframe."""
    time.sleep(1)
    loading_selectors = ["#ur-loading-box", "#ur-loading-itm2"]
    for selector in loading_selectors:
        try:
            loader = app_iframe.locator(selector)
            if loader.count() > 0:
                if loader.first.is_visible():
                    loader.first.wait_for(state="hidden", timeout=timeout)
        except Exception:
            pass

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
        
        # Clicar em OK
        try:
            app_iframe.get_by_role("button", name=re.compile(r"OK.*Emphasized")).click(timeout=10000)
        except Exception:
            try:
                app_iframe.get_by_role("cell", name=re.compile(r"^OK\s+Emphasized$")).first.click(timeout=5000)
            except Exception:
                app_iframe.get_by_role("button", name="OK").click()
                
        log_sys.write("⏳ Aguardando o fim do carregamento da ação de inserir remessas...")
        aguardar_fim_carregamento_sap(app_iframe, timeout=30000)
        log_sys.write("✅ Carregamento concluído após clique em OK.")

        # ── Detectar se a tela de inserir remessa continua aberta (erro) ────────
        tela_insert_aberta_com_erro = False
        erros_sap = []
        time.sleep(2)

        # Verificação principal: o diálogo de inserção ainda está visível?
        try:
            dialogo_visivel = txt_planning.is_visible()
        except Exception:
            dialogo_visivel = False

        if dialogo_visivel:
            # O diálogo ainda está aberto — coletar mensagens de erro
            try:
                error_msgs = app_iframe.locator('[role="listitem"][aria-label^="Error"]')
                error_count = error_msgs.count()
                if error_count > 0:
                    for i in range(error_count):
                        try:
                            aria = error_msgs.nth(i).get_attribute("aria-label") or ""
                            erros_sap.append(aria)
                            log_sys.write(f"  ⚠️ Erro SAP detectado: {aria}")
                        except Exception:
                            pass
            except Exception:
                pass

            # Fallback: verificar pelo texto genérico de erro dentro de divs de mensagem SAP
            if not erros_sap:
                try:
                    msg_error_divs = app_iframe.locator('div.lsMSGPad div.lsMSGText')
                    for i in range(msg_error_divs.count()):
                        try:
                            txt = msg_error_divs.nth(i).inner_text()
                            erros_sap.append(txt)
                            log_sys.write(f"  ⚠️ Erro SAP detectado (fallback): {txt}")
                        except Exception:
                            pass
                except Exception:
                    pass

            tela_insert_aberta_com_erro = True
            if not erros_sap:
                erros_sap.append("Diálogo de inserção permaneceu aberto (erro desconhecido)")
                log_sys.write("  ⚠️ Diálogo de inserção ainda aberto, mas nenhuma mensagem de erro encontrada.")

        # ── Se houver erro: clicar em Cancel e ir ao Document Flow ──────────────
        remessas_ausentes_early = []
        remessas_confirmadas_early = []

        if tela_insert_aberta_com_erro:
            log_sys.write(f"❌ Tela de inserir remessas ainda aberta com {len(erros_sap)} erro(s). Fechando tela...")
            
            fechou = False
            estrategias_fechar = [
                (
                    "Botão Close ('X') do container",
                    lambda: page.locator('iframe[name="__container1-iframe"]').content_frame.get_by_role("button", name="Close").first.click(timeout=3000, force=True)
                ),
                (
                    "Botão Cancel transparente (específico do diálogo)",
                    lambda: app_iframe.locator("div.lsButton--design-transparent:not([aria-disabled='true'])", has_text=re.compile(r"^Cancel$", re.IGNORECASE)).first.click(timeout=3000, force=True)
                ),
                (
                    "Botão Close ('X') via app_iframe",
                    lambda: app_iframe.get_by_role("button", name="Close").first.click(timeout=3000, force=True)
                ),
                (
                    "Botão Cancel via container iframe",
                    lambda: page.locator('iframe[name="__container1-iframe"]').content_frame.locator("div.lsButton--design-transparent:not([aria-disabled='true'])", has_text=re.compile(r"^Cancel$", re.IGNORECASE)).first.click(timeout=3000, force=True)
                ),
                (
                    "Span Cancel dentro do diálogo",
                    lambda: app_iframe.locator('div[ct="PW"], div[role="dialog"], table.urPWOuterTable').locator("span.lsButton__text", has_text=re.compile(r"^Cancel$", re.IGNORECASE)).first.click(timeout=3000, force=True)
                ),
                (
                    "Tecla Escape",
                    lambda: page.keyboard.press("Escape")
                ),
                (
                    "JS Click no botão Cancel transparente",
                    lambda: app_iframe.locator("div.lsButton--design-transparent", has_text=re.compile(r"^Cancel$", re.IGNORECASE)).first.evaluate("el => el.click()")
                ),
            ]

            for nome, acao in estrategias_fechar:
                try:
                    time.sleep(1)
                    acao()
                    # Aguarda até 3s para o campo de texto do diálogo sumir
                    txt_planning.wait_for(state="hidden", timeout=3000)
                    log_sys.write(f"✅ Diálogo de inserção fechado com sucesso (via {nome}).")
                    fechou = True
                    break
                except Exception:
                    try:
                        if not txt_planning.is_visible():
                            log_sys.write(f"✅ Diálogo de inserção fechado (confirmado após {nome}).")
                            fechou = True
                            break
                    except Exception:
                        pass

            if not fechou:
                log_sys.write("⚠️ Tentando tecla Escape final para fechar diálogo...")
                try:
                    page.keyboard.press("Escape")
                    time.sleep(1)
                except Exception:
                    pass

            aguardar_fim_carregamento_sap(app_iframe, timeout=30000)
            time.sleep(2)

            # Navegar até Document Flow para verificar quais remessas foram aceitas
            log_sys.write("🔎 Verificando remessas aceitas na aba Document Flow / Items...")
            try:
                page.locator("iframe[name=\"__container1-iframe\"]").content_frame.get_by_role("tab", name="Document Flow").click(timeout=10000)
                time.sleep(2)
            except Exception:
                try:
                    app_iframe.get_by_role("tab", name="Document Flow").click(timeout=5000)
                    time.sleep(2)
                except Exception:
                    pass
        else:
            # Tela passou direto — todas as remessas foram aceitas
            log_sys.write("✅ Tela de inserir remessas fechou sem erros — todas as remessas foram aceitas.")
            remessas_confirmadas_early = [str(r).strip() for r in remessas]
            log_sys.write(f"✅ {len(remessas_confirmadas_early)} remessa(s) confirmada(s): {', '.join(remessas_confirmadas_early)}")

        # ── Verificação no Document Flow: só executa se houve erro na inserção ──
        if tela_insert_aberta_com_erro:
            try:
                for rem in remessas:
                    rem_str = str(rem).strip()
                    encontrada = False

                    # 1. Verifica se o texto da remessa já está visível na página/iframe
                    try:
                        body_text = app_iframe.locator("body").inner_text()
                        if rem_str in body_text or app_iframe.get_by_text(rem_str).count() > 0:
                            encontrada = True
                    except Exception:
                        pass

                    # 2. Se não estiver visível diretamente, realiza a busca (Ctrl+F) no SAP
                    if not encontrada:
                        try:
                            time.sleep(1.5)
                            search_btn = app_iframe.get_by_role("button", name=re.compile(r"Search \(Ctrl\+F\)", re.IGNORECASE))
                            if search_btn.count() == 0:
                                search_btn = page.locator('iframe[title="Application"]').content_frame.get_by_role("button", name="Search (Ctrl+F)")
                            
                            search_btn.first.click(timeout=5000)
                            time.sleep(0.5)

                            search_box = app_iframe.get_by_role("textbox", name=re.compile(r"Search for", re.IGNORECASE))
                            if search_box.count() == 0:
                                search_box = page.locator('iframe[title="Application"]').content_frame.get_by_role("textbox", name="Search for")

                            search_box.fill(rem_str)
                            search_box.press("Enter")
                            time.sleep(1)

                            # Confirma se após o Enter o número da remessa é localizado na tela
                            body_text = app_iframe.locator("body").inner_text()
                            if rem_str in body_text or app_iframe.get_by_text(rem_str).count() > 0:
                                encontrada = True

                            # Fecha a caixa de busca
                            try:
                                cancel_btn = app_iframe.get_by_role("button", name=re.compile(r"Cancel Search", re.IGNORECASE))
                                if cancel_btn.count() > 0:
                                    cancel_btn.first.click(timeout=3000)
                                else:
                                    page.keyboard.press("Escape")
                            except Exception:
                                pass
                        except Exception as search_err:
                            log_sys.write(f"⚠️ Segunda tentativa")
                            try:
                                search_btn = app_iframe.get_by_role("button", name=re.compile(r"Search \(Ctrl\+F\)", re.IGNORECASE))
                                if search_btn.count() == 0:
                                    search_btn = page.locator('iframe[title="Application"]').content_frame.get_by_role("button", name="Search (Ctrl+F)")
                                    
                                search_btn.first.click(timeout=5000)
                                time.sleep(0.5)

                                search_box = app_iframe.get_by_role("textbox", name=re.compile(r"Search for", re.IGNORECASE))
                                if search_box.count() == 0:
                                    search_box = page.locator('iframe[title="Application"]').content_frame.get_by_role("textbox", name="Search for")

                                search_box.fill(rem_str)
                                search_box.press("Enter")
                                time.sleep(1)

                                # Confirma se após o Enter o número da remessa é localizado na tela
                                body_text = app_iframe.locator("body").inner_text()
                                if rem_str in body_text or app_iframe.get_by_text(rem_str).count() > 0:
                                    encontrada = True

                                # Fecha a caixa de busca
                                try:
                                    cancel_btn = app_iframe.get_by_role("button", name=re.compile(r"Cancel Search", re.IGNORECASE))
                                    if cancel_btn.count() > 0:
                                        cancel_btn.first.click(timeout=3000)
                                    else:
                                        page.keyboard.press("Escape")
                                except Exception:
                                    pass
                            except Exception as search_err:
                                    log_sys.write(f"⚠️ Erro ao executar busca no SAP para remessa {rem_str}: {search_err}")

                    if encontrada:
                        remessas_confirmadas_early.append(rem_str)
                        log_sys.write(f"  ✅ Remessa {rem_str} confirmada na OF")
                    else:
                        remessas_ausentes_early.append(rem_str)
                        log_sys.write(f"  ❌ Remessa {rem_str} NÃO encontrada na OF")

                    aguardar_fim_carregamento_sap(app_iframe, timeout=30000)

            except Exception as e:
                log_sys.write(f"⚠️ Erro ao verificar remessas após inserção: {e}")

            if remessas_ausentes_early:
                log_sys.write(f"⚠️ Remessas NÃO encontradas no SAP: {', '.join(remessas_ausentes_early)}")

            if not remessas_confirmadas_early:
                raise ValueError(
                    f"NENHUMA remessa foi aceita pelo SAP. Todas ausentes: "
                    f"{', '.join(remessas_ausentes_early)}. "
                    f"Verifique se os números estão corretos ou se já estão em outra OF."
                )

            log_sys.write(
                f"✅ {len(remessas_confirmadas_early)} remessa(s) confirmada(s). "
                f"Prosseguindo com a criação da OF..."
            )
            if remessas_ausentes_early:
                log_sys.write(
                    f"⚠️ {len(remessas_ausentes_early)} remessa(s) ausente(s) serão ignoradas na OF: "
                    f"{', '.join(remessas_ausentes_early)}"
                )
            
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
                
                # Clicar em OK
                try:
                    app_iframe.get_by_role("button", name=re.compile(r"OK.*Emphasized")).click(timeout=10000)
                except Exception:
                    try:
                        app_iframe.get_by_role("cell", name=re.compile(r"^OK\s+Emphasized$")).first.click(timeout=5000)
                    except Exception:
                        app_iframe.get_by_role("button", name="OK").click()
                        
                log_sys.write("⏳ Aguardando o fim do carregamento da ação de inserir remessas...")
                aguardar_fim_carregamento_sap(app_iframe, timeout=30000)
                log_sys.write("✅ Carregamento concluído após clique em OK.")

                # ── Detectar se a tela de inserir remessa continua aberta (erro) ────────
                tela_insert_aberta_com_erro = False
                erros_sap = []
                time.sleep(2)

                # Verificação principal: o diálogo de inserção ainda está visível?
                try:
                    dialogo_visivel = txt_planning.is_visible()
                except Exception:
                    dialogo_visivel = False

                if dialogo_visivel:
                    # O diálogo ainda está aberto — coletar mensagens de erro
                    try:
                        error_msgs = app_iframe.locator('[role="listitem"][aria-label^="Error"]')
                        error_count = error_msgs.count()
                        if error_count > 0:
                            for i in range(error_count):
                                try:
                                    aria = error_msgs.nth(i).get_attribute("aria-label") or ""
                                    erros_sap.append(aria)
                                    log_sys.write(f"  ⚠️ Erro SAP detectado: {aria}")
                                except Exception:
                                    pass
                    except Exception:
                        pass

                    # Fallback: verificar pelo texto genérico de erro dentro de divs de mensagem SAP
                    if not erros_sap:
                        try:
                            msg_error_divs = app_iframe.locator('div.lsMSGPad div.lsMSGText')
                            for i in range(msg_error_divs.count()):
                                try:
                                    txt = msg_error_divs.nth(i).inner_text()
                                    erros_sap.append(txt)
                                    log_sys.write(f"  ⚠️ Erro SAP detectado (fallback): {txt}")
                                except Exception:
                                    pass
                        except Exception:
                            pass

                    tela_insert_aberta_com_erro = True
                    if not erros_sap:
                        erros_sap.append("Diálogo de inserção permaneceu aberto (erro desconhecido)")
                        log_sys.write("  ⚠️ Diálogo de inserção ainda aberto, mas nenhuma mensagem de erro encontrada.")

                # ── Se houver erro: clicar em Cancel e ir ao Document Flow ──────────────
                remessas_ausentes_early = []
                remessas_confirmadas_early = []

                if tela_insert_aberta_com_erro:
                    log_sys.write(f"❌ Tela de inserir remessas ainda aberta com {len(erros_sap)} erro(s). Fechando tela...")
                    
                    fechou = False
                    estrategias_fechar = [
                        (
                            "Botão Close ('X') do container",
                            lambda: page.locator('iframe[name="__container1-iframe"]').content_frame.get_by_role("button", name="Close").first.click(timeout=3000, force=True)
                        ),
                        (
                            "Botão Cancel transparente (específico do diálogo)",
                            lambda: app_iframe.locator("div.lsButton--design-transparent:not([aria-disabled='true'])", has_text=re.compile(r"^Cancel$", re.IGNORECASE)).first.click(timeout=3000, force=True)
                        ),
                        (
                            "Botão Close ('X') via app_iframe",
                            lambda: app_iframe.get_by_role("button", name="Close").first.click(timeout=3000, force=True)
                        ),
                        (
                            "Botão Cancel via container iframe",
                            lambda: page.locator('iframe[name="__container1-iframe"]').content_frame.locator("div.lsButton--design-transparent:not([aria-disabled='true'])", has_text=re.compile(r"^Cancel$", re.IGNORECASE)).first.click(timeout=3000, force=True)
                        ),
                        (
                            "Span Cancel dentro do diálogo",
                            lambda: app_iframe.locator('div[ct="PW"], div[role="dialog"], table.urPWOuterTable').locator("span.lsButton__text", has_text=re.compile(r"^Cancel$", re.IGNORECASE)).first.click(timeout=3000, force=True)
                        ),
                        (
                            "Tecla Escape",
                            lambda: page.keyboard.press("Escape")
                        ),
                        (
                            "JS Click no botão Cancel transparente",
                            lambda: app_iframe.locator("div.lsButton--design-transparent", has_text=re.compile(r"^Cancel$", re.IGNORECASE)).first.evaluate("el => el.click()")
                        ),
                    ]

                    for nome, acao in estrategias_fechar:
                        try:
                            time.sleep(1)
                            acao()
                            # Aguarda até 3s para o campo de texto do diálogo sumir
                            txt_planning.wait_for(state="hidden", timeout=3000)
                            log_sys.write(f"✅ Diálogo de inserção fechado com sucesso (via {nome}).")
                            fechou = True
                            break
                        except Exception:
                            try:
                                if not txt_planning.is_visible():
                                    log_sys.write(f"✅ Diálogo de inserção fechado (confirmado após {nome}).")
                                    fechou = True
                                    break
                            except Exception:
                                pass

                    if not fechou:
                        log_sys.write("⚠️ Tentando tecla Escape final para fechar diálogo...")
                        try:
                            page.keyboard.press("Escape")
                            time.sleep(1)
                        except Exception:
                            pass

                    aguardar_fim_carregamento_sap(app_iframe, timeout=30000)
                    time.sleep(2)

                    # Navegar até Document Flow para verificar quais remessas foram aceitas
                    log_sys.write("🔎 Verificando remessas aceitas na aba Document Flow / Items...")
                    try:
                        page.locator("iframe[name=\"__container1-iframe\"]").content_frame.get_by_role("tab", name="Document Flow").click(timeout=10000)
                        time.sleep(2)
                    except Exception:
                        try:
                            app_iframe.get_by_role("tab", name="Document Flow").click(timeout=5000)
                            time.sleep(2)
                        except Exception:
                            pass
                else:
                    # Tela passou direto — todas as remessas foram aceitas
                    log_sys.write("✅ Tela de inserir remessas fechou sem erros — todas as remessas foram aceitas.")
                    remessas_confirmadas_early = [str(r).strip() for r in remessas]
                    log_sys.write(f"✅ {len(remessas_confirmadas_early)} remessa(s) confirmada(s): {', '.join(remessas_confirmadas_early)}")

                # ── Verificação no Document Flow: só executa se houve erro na inserção ──
                if tela_insert_aberta_com_erro:
                    try:
                        for rem in remessas:
                            rem_str = str(rem).strip()
                            encontrada = False

                            # 1. Verifica se o texto da remessa já está visível na página/iframe
                            try:
                                body_text = app_iframe.locator("body").inner_text()
                                if rem_str in body_text or app_iframe.get_by_text(rem_str).count() > 0:
                                    encontrada = True
                            except Exception:
                                pass

                            # 2. Se não estiver visível diretamente, realiza a busca (Ctrl+F) no SAP
                            if not encontrada:
                                try:
                                    time.sleep(1.5)
                                    search_btn = app_iframe.get_by_role("button", name=re.compile(r"Search \(Ctrl\+F\)", re.IGNORECASE))
                                    if search_btn.count() == 0:
                                        search_btn = page.locator('iframe[title="Application"]').content_frame.get_by_role("button", name="Search (Ctrl+F)")
                                    
                                    search_btn.first.click(timeout=5000)
                                    time.sleep(0.5)

                                    search_box = app_iframe.get_by_role("textbox", name=re.compile(r"Search for", re.IGNORECASE))
                                    if search_box.count() == 0:
                                        search_box = page.locator('iframe[title="Application"]').content_frame.get_by_role("textbox", name="Search for")

                                    search_box.fill(rem_str)
                                    search_box.press("Enter")
                                    time.sleep(1)

                                    # Confirma se após o Enter o número da remessa é localizado na tela
                                    body_text = app_iframe.locator("body").inner_text()
                                    if rem_str in body_text or app_iframe.get_by_text(rem_str).count() > 0:
                                        encontrada = True

                                    # Fecha a caixa de busca
                                    try:
                                        cancel_btn = app_iframe.get_by_role("button", name=re.compile(r"Cancel Search", re.IGNORECASE))
                                        if cancel_btn.count() > 0:
                                            cancel_btn.first.click(timeout=3000)
                                        else:
                                            page.keyboard.press("Escape")
                                    except Exception:
                                        pass
                                except Exception as search_err:
                                    log_sys.write(f"⚠️ Segunda tentativa")
                                    try:
                                        search_btn = app_iframe.get_by_role("button", name=re.compile(r"Search \(Ctrl\+F\)", re.IGNORECASE))
                                        if search_btn.count() == 0:
                                            search_btn = page.locator('iframe[title="Application"]').content_frame.get_by_role("button", name="Search (Ctrl+F)")
                                            
                                        search_btn.first.click(timeout=5000)
                                        time.sleep(0.5)

                                        search_box = app_iframe.get_by_role("textbox", name=re.compile(r"Search for", re.IGNORECASE))
                                        if search_box.count() == 0:
                                            search_box = page.locator('iframe[title="Application"]').content_frame.get_by_role("textbox", name="Search for")

                                        search_box.fill(rem_str)
                                        search_box.press("Enter")
                                        time.sleep(1)

                                        # Confirma se após o Enter o número da remessa é localizado na tela
                                        body_text = app_iframe.locator("body").inner_text()
                                        if rem_str in body_text or app_iframe.get_by_text(rem_str).count() > 0:
                                            encontrada = True

                                        # Fecha a caixa de busca
                                        try:
                                            cancel_btn = app_iframe.get_by_role("button", name=re.compile(r"Cancel Search", re.IGNORECASE))
                                            if cancel_btn.count() > 0:
                                                cancel_btn.first.click(timeout=3000)
                                            else:
                                                page.keyboard.press("Escape")
                                        except Exception:
                                            pass
                                    except Exception as search_err:
                                            log_sys.write(f"⚠️ Erro ao executar busca no SAP para remessa {rem_str}: {search_err}")

                            if encontrada:
                                remessas_confirmadas_early.append(rem_str)
                                log_sys.write(f"  ✅ Remessa {rem_str} confirmada na OF")
                            else:
                                remessas_ausentes_early.append(rem_str)
                                log_sys.write(f"  ❌ Remessa {rem_str} NÃO encontrada na OF")

                            aguardar_fim_carregamento_sap(app_iframe, timeout=30000)

                    except Exception as e:
                        log_sys.write(f"⚠️ Erro ao verificar remessas após inserção: {e}")

                    if remessas_ausentes_early:
                        log_sys.write(f"⚠️ Remessas NÃO encontradas no SAP: {', '.join(remessas_ausentes_early)}")

                    if not remessas_confirmadas_early:
                        raise ValueError(
                            f"NENHUMA remessa foi aceita pelo SAP. Todas ausentes: "
                            f"{', '.join(remessas_ausentes_early)}. "
                            f"Verifique se os números estão corretos ou se já estão em outra OF."
                        )

                    log_sys.write(
                        f"✅ {len(remessas_confirmadas_early)} remessa(s) confirmada(s). "
                        f"Prosseguindo com a criação da OF..."
                    )
                    if remessas_ausentes_early:
                        log_sys.write(
                            f"⚠️ {len(remessas_ausentes_early)} remessa(s) ausente(s) serão ignoradas na OF: "
                            f"{', '.join(remessas_ausentes_early)}"
                        )
                    
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
