import os
import sys
import time
import re
from src.utils.common import log_sys
from src.expedicao.sap_packlist import _garantir_playwright_instalado

SAP_FO_URL = "https://appprod.sap.valgroupco.com/sap/bc/ui2/flp?sap-client=200&sap-language=EN#FreightOrder-createRoad?sap-ui-tech-hint=WDA"

def preencher_campo_por_titulo(app_iframe, titulos: list, valor: str, press_enter: bool = True, digitar: bool = False) -> bool:
    for tit in titulos:
        selector = f"input[title='{tit}']"
        try:
            # Espera até o elemento estar visível na página (aumentado para 15 segundos para SAP lento)
            app_iframe.locator(selector).first.wait_for(state="visible", timeout=15000)
        except Exception:
            continue
            
        loc = app_iframe.locator(selector)
        count = loc.count()
        for idx in range(count):
            ipt = loc.nth(idx)
            try:
                if ipt.is_visible() and ipt.is_enabled():
                    ipt.click()
                    if digitar:
                        ipt.press("Control+a")
                        ipt.press("Backspace")
                        ipt.press_sequentially(valor, delay=100)
                    else:
                        ipt.fill(valor)
                    if press_enter:
                        ipt.press("Enter")
                    log_sys.write(f"✅ Campo '{tit}' preenchido com '{valor}'")
                    return True
            except Exception:
                pass
    return False


def aguardar_fim_carregamento_sap(app_iframe, timeout: int = 30000) -> None:
    """Aguarda o overlay de carregamento do SAP desaparecer dentro do iframe."""
    # Um pequeno delay para permitir que o SAP inicie a requisição (click) e exiba o loading.
    # Sem isso, o Playwright vê que já está oculto e pula a espera instantaneamente.
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


def rodar_criacao_of_cabotagem_playwright(
    remessas: list, 
    transportadora: str, 
    valor_frete: float, 
    usuario: str, 
    senha: str,
    headless: bool = False
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
        # Executa no modo oculto (headless=True por padrão, ou False para debug/visualização)
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
        
        type_input = app_iframe.get_by_role("textbox", name="Freight Order Type")
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

        log_sys.write("⏳ Clicando na aba de Itens...")
        try:
            app_iframe.locator("span[role='tab']", has_text=re.compile(r"^(Items|Itens)$", re.IGNORECASE)).click(timeout=10000)
            time.sleep(2)
        except Exception:
            pass
        
        # Inserir FUs baseadas no ID do Documento
        log_sys.write("⏳ Inserindo FUs baseadas nas remessas...")

        # Localiza pelo título para não depender de ID dinâmico (ex: #WDF6)
        btn_insert = app_iframe.locator('[title="Insert FUs Based on Freight Unit ID"]')
        btn_insert.wait_for(state="visible", timeout=20000)
        # force=True ignora checagens de "clickable" que o Web Dynpro costuma travar
        btn_insert.click(force=True)
        try:
            page.locator('iframe[name="__container1-iframe"]').content_frame.get_by_text("Insert FUs Based on Base").click(timeout=8000)
        except Exception:
            try:
                app_iframe.get_by_text("Insert FUs Based on Base").click(timeout=5000)
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
                
        log_sys.write("⏳ Aguardando o fim do carregamento da ação de inserir remessas...")
        aguardar_fim_carregamento_sap(app_iframe, timeout=30000)
        log_sys.write("✅ Carregamento concluído após clique em OK.")

        # ── Detectar se a tela de inserir remessa continua aberta (erro) ────────
        tela_insert_aberta_com_erro = False
        erros_sap = []
        time.sleep(2)

        # Verificação principal: o diálogo de inserção ainda está visível?
        # (txt_planning é o campo de texto exclusivo do diálogo de inserir remessas)
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


        # Acessar a aba "General Data Assignment Block"
        log_sys.write("⏳ Acessando aba General Data...")
        try:
            time.sleep(1.5)
            aguardar_fim_carregamento_sap(app_iframe, timeout=30000)
            app_iframe.get_by_role("tab", name=re.compile(r"^(General Data|Dados gerais)", re.IGNORECASE)).click(timeout=10000)
        except Exception:
            pass
            
        # Meio de Transporte: 0007
        # 1. Veículo: preenche e dá Enter para disparar o auto-preenchimento do Meio de Transporte
        log_sys.write("🚚 Preenchendo Veículo: CARRETA_CAR_SIDER_LS")
        campo_veiculo = app_iframe.get_by_role("textbox", name=re.compile(r"^(Vehicle|Veículo)", re.IGNORECASE))
        campo_veiculo.click()
        campo_veiculo.fill("CARRETA_CAR_SIDER_LS")
        campo_veiculo.press("Enter")

        # Aguarda o SAP processar a requisição e carregar o Meio de Transporte (0007)
        aguardar_fim_carregamento_sap(app_iframe, timeout=15000)
        time.sleep(1)

        # 2. Empresa: vma1
        log_sys.write("🚚 Preenchendo Empresa: vma1")
        campo_empresa = app_iframe.get_by_role("textbox", name=re.compile(r"^(Procuring Company Code|Empresa de compras|Empresa)", re.IGNORECASE))
        campo_empresa.click()
        campo_empresa.fill("vma1")

        # 3. Transportadora (Carrier)
        transportadora_fixa = os.getenv("CABOTAGEM_TRANSPORTADORA_PADRAO", "9190617").strip() or transportadora
        log_sys.write(f"🚚 Preenchendo Transportador: {transportadora_fixa}")
        campo_carrier = app_iframe.get_by_role("textbox", name=re.compile(r"^(Carrier|Transportador)", re.IGNORECASE))
        campo_carrier.click()
        campo_carrier.fill(transportadora_fixa)
        campo_carrier.press("Enter")

        aguardar_fim_carregamento_sap(app_iframe, timeout=15000)
        
        # Acessar a aba "Charges Assignment Block"

# Acessar a aba "Charges" / "Despesas"
        log_sys.write("⏳ Acessando aba de Despesas (Charges)...")

        # 1. Scroll e clique na aba Charges
        try:
            app_iframe.evaluate("() => { window.scrollTo(0, 0); document.querySelectorAll('*').forEach(e => { if (e.scrollTop > 0) e.scrollTop = 0; }); }")
            time.sleep(0.5)
        except Exception:
            pass

        tab_charges = app_iframe.get_by_role("tab", name=re.compile(r"^(Charges|Despesas)", re.IGNORECASE))
        tab_charges.scroll_into_view_if_needed()
        tab_charges.click(timeout=10000)
        aguardar_fim_carregamento_sap(app_iframe, timeout=30000)

        # 2. Expand All
        log_sys.write("⏳ Expandindo linhas de Charges...")
        try:
            expand_btn = app_iframe.get_by_role("button", name=re.compile(r"^(Expand All|Expandir tudo)", re.IGNORECASE)).first
            if expand_btn.is_visible():
                expand_btn.click()
                aguardar_fim_carregamento_sap(app_iframe, timeout=15000)
        except Exception as e:
            log_sys.write(f"⚠️ Aviso ao tentar Expand All: {e}")

        # Formatação do valor do frete
        valor_formatado = f"{valor_frete:.2f}".replace(".", ",") if isinstance(valor_frete, (int, float)) else str(valor_frete)

        # 3. Localização da Linha: Cenário A (FB02 já existe) vs Cenário B (Criar em linha vazia)
        # Como o SAP pode colocar o FB02 num campo editável (<input>), o has_text não o encontra.
        # Por isso usamos uma combinação de seletores para buscar tanto texto visível quanto o value do input.
        linha_fb02 = app_iframe.locator("tr, [role='row']").filter(
            has=app_iframe.locator("text=/\\bFB02\\b/").or_(app_iframe.locator("input[value='FB02']"))
        )

        if linha_fb02.count() > 0:
            log_sys.write("🏷️ Linha FB02 encontrada na tabela. Atualizando valor...")
            # Procura o campo de montante/taxa dentro da linha específica do FB02
            campo_rate = linha_fb02.first.get_by_role("textbox", name=re.compile(r"(Rate Amount|Montante da taxa|Montante)", re.IGNORECASE))
            
            if campo_rate.count() == 0:
                # Fallback caso o SAP trate como combobox na célula
                campo_rate = linha_fb02.first.get_by_role("combobox", name=re.compile(r"(Rate Amount|Montante da taxa|Montante)", re.IGNORECASE))
            
            campo_rate.first.click()
            time.sleep(0.5)
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.keyboard.insert_text(valor_formatado)
            page.keyboard.press("Enter")
            aguardar_fim_carregamento_sap(app_iframe, timeout=15000)
            log_sys.write(f"✅ Valor do frete {valor_formatado} preenchido na linha existente do FB02")

        else:
            log_sys.write("⚠️ FB02 não encontrado nas linhas automáticas. Inserindo nova linha de despesa...")
            
            # Localiza campos de Charge Type (o último visível costuma ser a linha em branco)
            campos_tipo = app_iframe.get_by_role("textbox", name=re.compile(r"^(Charge Type|Tipo de despesa|Tipo de encargo)", re.IGNORECASE))
            
            if campos_tipo.count() == 0:
                # Fallback se o label acessível não estiver nomeado como textbox
                campos_tipo = app_iframe.locator("input[title*='Charge Type'], input[title*='Tipo de encargo']")
            
            # Preenche FB02 na última linha disponível
            input_tipo_novo = campos_tipo.last
            input_tipo_novo.click()
            input_tipo_novo.fill("FB02")
            input_tipo_novo.press("Enter")
            aguardar_fim_carregamento_sap(app_iframe, timeout=15000)
            
            # Agora que o SAP confirmou a inserção do FB02, busca a linha recém-criada
            linha_recem_criada = app_iframe.locator("tr, [role='row']").filter(has=app_iframe.locator("text=/\\bFB02\\b/").or_(app_iframe.locator("input[value='FB02']"))).first
            campo_rate_novo = linha_recem_criada.get_by_role("textbox", name=re.compile(r"(Rate Amount|Montante da taxa|Montante)", re.IGNORECASE))
            
            if campo_rate_novo.count() == 0:
                campo_rate_novo = linha_recem_criada.get_by_role("combobox", name=re.compile(r"(Rate Amount|Montante da taxa|Montante)", re.IGNORECASE))
                
            campo_rate_novo.first.click()
            time.sleep(0.5)
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.keyboard.insert_text(valor_formatado)
            page.keyboard.press("Enter")
            aguardar_fim_carregamento_sap(app_iframe, timeout=15000)
            log_sys.write(f"✅ FB02 criado e valor {valor_formatado} inserido com sucesso")

        # Clicar em "BID Freight Table" para confirmar/sair do campo editado
        try:
            app_iframe.get_by_label("BID Freight Table").click(timeout=5000)
            log_sys.write("✅ Clicou em BID Freight Table para confirmar")
        except Exception:
            pass

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

        log_sys.write(f"🎉 OF {of_numero} criada com sucesso!")
        log_sys.write(
            f"📊 Remessas confirmadas: {remessas_confirmadas_early} | "
            f"Ausentes: {remessas_ausentes_early}"
        )

        return {
            "of_numero": of_numero,
            "remessas_confirmadas": remessas_confirmadas_early,
            "remessas_ausentes": remessas_ausentes_early,
        }
        
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
