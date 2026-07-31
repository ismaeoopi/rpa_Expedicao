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
    loading_selectors = ["#ur-loading-box", "#ur-loading-itm2"]
    for selector in loading_selectors:
        try:
            loader = app_iframe.locator(selector)
            if loader.count() > 0:
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

        log_sys.write("⏳ Clicando na aba de Itens...")
        try:
            app_iframe.get_by_role("tab", name=re.compile(r"(Items|Itens).*Assignment Block", re.IGNORECASE)).click(timeout=10000)
            time.sleep(2)
        except Exception:
            pass
        
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
                
        log_sys.write("⏳ Aguardando o fim do carregamento da ação de inserir remessas...")
        aguardar_fim_carregamento_sap(app_iframe, timeout=30000)
        log_sys.write("✅ Carregamento concluído após clique em OK.")

        # ── Verificação antecipada: confirmar que as remessas foram aceitas ──────
        log_sys.write("🔎 Verificando se as remessas foram aceitas na aba Document Flow / Items...")
        remessas_ausentes_early = []
        remessas_confirmadas_early = []

        try:
            time.sleep(2)
            app_iframe.get_by_role("tab", name=re.compile(r"(Document\s+Flow|Fluxo\s+de\s+Documentos).*Assignment Block", re.IGNORECASE)).click(timeout=10000)
            time.sleep(2)
        except Exception:
            pass

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
            raise ValueError(
                f"As seguintes remessas não foram aceitas pelo SAP após inserção: "
                f"{', '.join(remessas_ausentes_early)}. "
                f"Verifique se os números estão corretos ou se já estão em outra OF."
            )

        log_sys.write(f"✅ Todas as {len(remessas_confirmadas_early)} remessa(s) confirmadas. Prosseguindo...")

        # Acessar a aba "General Data Assignment Block"
        log_sys.write("⏳ Acessando aba General Data...")
        try:
            time.sleep(1.5)
            app_iframe.get_by_role("tab", name=re.compile(r"(General Data|Dados gerais).*Assignment Block", re.IGNORECASE)).click(timeout=10000)
        except Exception:
            pass
            
        # Meio de Transporte: 0007
        log_sys.write("🚚 Preenchendo Meio de Transporte: 0007")
        time.sleep(1)

        target_input = None
        for selector in ["input[name=\"WD05F5\"]", "#WD0346"]:
            try:
                el = app_iframe.locator(selector)
                el.wait_for(state="visible", timeout=1000)
                target_input = el
                break
            except Exception:
                pass

        if not target_input:
            log_sys.write("⚠️ Não encontrou seletores padrões para Meio de Transporte. Listando inputs visíveis no iframe:")
            try:
                inputs = app_iframe.locator("input").all()
                visible_count = 0
                for i, ipt in enumerate(inputs):
                    if ipt.is_visible():
                        visible_count += 1
                        name = ipt.get_attribute("name") or ""
                        id_attr = ipt.get_attribute("id") or ""
                        val = ipt.input_value() or ""
                        role = ipt.get_attribute("role") or ""
                        title = ipt.get_attribute("title") or ""
                        log_sys.write(f"  - Input [{i}]: id='{id_attr}', name='{name}', title='{title}', value='{val}', role='{role}'")
                if visible_count == 0:
                    log_sys.write("  Nenhum input visível no iframe no momento.")
            except Exception as ex:
                log_sys.write(f"  Erro ao listar inputs: {ex}")

        # Tenta preencher por título primeiro (mais robusto contra IDs dinâmicos)
        preenchido_meio = preencher_campo_por_titulo(app_iframe, ["Means of Transport", "Meio de transporte", "Meio de Transporte"], "0007",press_enter=True)
        if not preenchido_meio:
            if target_input:
                target_input.click()
                target_input.fill("0007")
                target_input.press("Enter")
            else:
                # Fallback antigo
                app_iframe.get_by_role("textbox", name="Means of Transport Value help").fill("0007")
                app_iframe.get_by_role("textbox", name="Means of Transport Value help").press("Enter")
        time.sleep(1)
        
        # Veículo: CARRETA_CAR_SIDER_LS
        log_sys.write("🚚 Preenchendo Veículo: CARRETA_CAR_SIDER_LS")
        preenchido_veiculo = preencher_campo_por_titulo(app_iframe, ["Vehicle", "Veículo"], "CARRETA_CAR_SIDER_LS", press_enter=True)
        if not preenchido_veiculo:
            app_iframe.get_by_role("textbox", name="Vehicle").click()
            app_iframe.get_by_role("textbox", name="Vehicle Value help available").fill("CARRETA_CAR_SIDER_LS")
            app_iframe.get_by_role("textbox", name="Vehicle Value help available").press("Enter")
        time.sleep(1)
        
        # Empresa: vma1
        log_sys.write("🚚 Preenchendo Empresa: vma1")
        preenchido_empresa = preencher_campo_por_titulo(app_iframe, ["Procuring Company Code", "Empresa de compras", "Empresa"], "vma1", press_enter=False)
        if not preenchido_empresa:
            app_iframe.get_by_role("textbox", name="Procuring Company Code").click()
            app_iframe.get_by_role("textbox", name="Procuring Company Code Value").fill("vma1")
        
        # Transportadora (Carrier)
        transportadora_fixa = os.getenv("CABOTAGEM_TRANSPORTADORA_PADRAO", "9190617").strip() or transportadora
        log_sys.write(f"🚚 Preenchendo Transportador: {transportadora_fixa}")
        preenchido_carrier = preencher_campo_por_titulo(app_iframe, ["Carrier", "Transportador"], transportadora_fixa)
        if not preenchido_carrier:
            app_iframe.get_by_role("textbox", name="Carrier", exact=True).click()
            app_iframe.get_by_role("textbox", name="Carrier Value help available").fill(transportadora_fixa)
            app_iframe.get_by_role("textbox", name="Carrier Value help available").press("Enter")
        time.sleep(2)
        
        # Acessar a aba "Charges Assignment Block"
        log_sys.write("⏳ Acessando aba de Despesas (Charges)...")
        app_iframe.get_by_role("tab", name=re.compile(r"(Charges|Despesas).*Assignment Block", re.IGNORECASE)).click()
        time.sleep(2)

        # Expandir todas as linhas — após Expand All o FB02 já aparece na tabela de Charges
        log_sys.write("⏳ Expandindo linhas de Charges (Expand All)...")
        try:
            expand_btns = app_iframe.get_by_role("button", name="Expand All")
            # If multiple buttons match, click the first one to avoid strict mode violation
            try:
                if expand_btns.count() > 1:
                    expand_btns.first.click()
                else:
                    expand_btns.click()
            except Exception:
                # As a safer fallback, target by the title attribute which SAP renders on the div
                app_iframe.locator("div[title='Expand All']").first.click()
        except Exception as e:
            log_sys.write(f"⚠️ Erro ao tentar clicar 'Expand All': {e}")
        time.sleep(2)

        # Clicar no texto FB02 para ativar/selecionar a linha de charge correspondente
        log_sys.write("🏷️ Selecionando linha do Charge Type FB02...")
        try:
            app_iframe.get_by_text("FB02").first.click(timeout=10000)
            log_sys.write("✅ Linha FB02 selecionada")
        except Exception as e:
            log_sys.write(f"⚠️ Não encontrou texto FB02: {e}")
        time.sleep(1)

        # Preencher o campo Rate Amount (ID dinâmico — usar múltiplos fallbacks)
        valor_str = str(int(valor_frete)) if valor_frete == int(valor_frete) else f"{valor_frete:.2f}".replace(".", ",")
        valor_formatado = f"{valor_frete:.2f}".replace(".", ",")
        log_sys.write(f"💰 Inserindo valor do frete: {valor_str}")
        preenchido_frete = False

        # Tentativa 1: via role combobox name="Rate Amount"
        if not preenchido_frete:
            try:
                rate_amount = app_iframe.get_by_role("combobox", name="Rate Amount").first
                rate_amount.wait_for(state="visible", timeout=5000)
                rate_amount.click()
                rate_amount.fill(valor_str)
                rate_amount.press("Enter")
                preenchido_frete = True
                log_sys.write(f"✅ Rate Amount preenchido via combobox com '{valor_str}'")
            except Exception:
                pass

        # Tentativa 2: via preencher_campo_por_titulo
        if not preenchido_frete:
            preenchido_frete = preencher_campo_por_titulo(
                app_iframe,
                ["Rate Amount", "Montante da taxa", "Montante taxa", "Montante da Taxa"],
                valor_formatado,
                press_enter=True
            )
            if preenchido_frete:
                log_sys.write(f"✅ Rate Amount preenchido via título com '{valor_formatado}'")

        if not preenchido_frete:
            raise RuntimeError("Não foi possível localizar o campo Rate Amount para inserir o valor do frete.")

        time.sleep(1)

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
