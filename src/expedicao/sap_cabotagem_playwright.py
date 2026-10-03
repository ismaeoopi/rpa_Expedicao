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


def _executar_criacao_of_na_pagina(
    page,
    remessas: list,
    usuario: str,
    senha: str,
    tipo_ordem: str = "zcro",
    transportadora: str = None,
    valor_frete: float = None,
    veiculo: str = None,
    empresa: str = None,
) -> dict:
    """
    Executa a criação de Ordem de Frete (OF) no SAP Fiori em uma página já aberta.
    Suporta criação para Entreposto (tipo 'zcro') e Cabotagem (tipo 'zout').
    Retorna um dicionário com o resultado:
    {
        "of_numero": of_numero,
        "remessas_confirmadas": remessas_confirmadas,
        "remessas_ausentes": remessas_ausentes
    }
    """
    if not remessas:
        raise ValueError("Nenhuma remessa fornecida para criação da OF.")

    # 1. Verifica se a página de login do SAP Fiori está aberta
    log_sys.write("🔐 Verificando autenticação no SAP Fiori...")
    try:
        user_field = page.get_by_role("textbox", name=re.compile(r"^(User|Usuário)", re.IGNORECASE))
        if user_field.first.is_visible(timeout=5000):
            log_sys.write("🔐 Efetuando Login...")
            if page.get_by_role("textbox", name="User").is_visible():
                page.get_by_role("textbox", name="User").fill(usuario)
                time.sleep(2)
                page.get_by_role("textbox", name="Password").fill(senha)
                page.get_by_role("button", name="Log On").click()
            else:
                page.get_by_role("textbox", name="Usuário").fill(usuario)
                time.sleep(2)
                page.get_by_role("textbox", name="Senha").fill(senha)
                page.get_by_role("button", name="Logon").click()
            time.sleep(2)
    except Exception:
        pass

    # 2. Aguarda o iframe da aplicação carregar
    log_sys.write("⏳ Aguardando carregamento da aplicação SAP Dynpro...")
    app_iframe = page.frame_locator('iframe[title="Application"]')
    
    # Campo Tipo de Ordem de Frete (busca resiliente por role ou selector de title)
    type_input = app_iframe.get_by_role("textbox", name=re.compile(r"Freight Order Type|Tipo de ordem de frete", re.IGNORECASE))
    try:
        type_input.first.wait_for(state="visible", timeout=45000)
    except Exception:
        fallback = app_iframe.locator("input[title*='Freight Order Type'], input[title*='Tipo de ordem de frete']")
        if fallback.count() > 0 and fallback.first.is_visible():
            type_input = fallback
        else:
            content = page.content().lower()
            if "senha" in content or "password" in content or "incorret" in content or "inválid" in content:
                raise ValueError("Usuário ou senha incorretos no SAP Fiori.")
            raise RuntimeError("A aplicação Dynpro não carregou no tempo limite.")
            
    log_sys.write("✅ Conectado ao SAP Dynpro de criação de Ordem de Frete.")
    
    # 3. Preenche tipo da ordem (zcro para Entreposto, zout para Cabotagem)
    log_sys.write(f"📝 Preenchendo tipo da Ordem de Frete: {tipo_ordem}")
    type_input.first.click()
    type_input.first.fill(tipo_ordem)
    type_input.first.press("Enter")
    aguardar_fim_carregamento_sap(app_iframe, timeout=15000)
    time.sleep(1.5)

    # 4. Aba de Itens
    log_sys.write("⏳ Clicando na aba de Itens...")
    try:
        tab_items = app_iframe.locator("span[role='tab']", has_text=re.compile(r"^(Items|Itens)", re.IGNORECASE))
        if tab_items.count() > 0:
            tab_items.first.click(timeout=10000)
        else:
            app_iframe.get_by_role("tab", name=re.compile(r"^(Items|Itens)", re.IGNORECASE)).first.click(timeout=10000)
        aguardar_fim_carregamento_sap(app_iframe, timeout=15000)
        time.sleep(1)
    except Exception as e:
        log_sys.write(f"⚠️ Aviso ao clicar na aba Itens: {e}")
    
    # 5. Inserir FUs baseadas nas remessas
    log_sys.write("⏳ Inserindo FUs baseadas nas remessas...")
    btn_insert = app_iframe.locator('[title="Insert FUs Based on Freight Unit ID"]')
    if btn_insert.count() == 0:
        btn_insert = app_iframe.get_by_role("button", name=re.compile(r"Insert.*FUs Based on", re.IGNORECASE))
        
    btn_insert.first.wait_for(state="visible", timeout=20000)
    btn_insert.first.click(force=True)
    time.sleep(1)

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
    
    # 6. Preencher as remessas
    txt_planning = app_iframe.get_by_role("textbox", name="String for Text Planning")
    txt_planning.wait_for(state="visible", timeout=15000)
    
    remessas_text = "\n".join([str(r).strip() for r in remessas]) + "\n"
    log_sys.write(f"📝 Inserindo {len(remessas)} remessa(s): {', '.join([str(r) for r in remessas])}")
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

    # 7. Detectar se a tela de inserir remessa continua aberta (erro)
    tela_insert_aberta_com_erro = False
    erros_sap = []
    time.sleep(2)

    try:
        dialogo_visivel = txt_planning.is_visible()
    except Exception:
        dialogo_visivel = False

    if dialogo_visivel:
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

    # Se houver erro: fechar modal com estratégias
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
        log_sys.write("✅ Tela de inserir remessas fechou sem erros — todas as remessas foram aceitas.")
        remessas_confirmadas_early = [str(r).strip() for r in remessas]
        log_sys.write(f"✅ {len(remessas_confirmadas_early)} remessa(s) confirmada(s): {', '.join(remessas_confirmadas_early)}")

    # Verificação no Document Flow caso tenha havido erro na inserção
    if tela_insert_aberta_com_erro:
        try:
            for rem in remessas:
                rem_str = str(rem).strip()
                encontrada = False

                try:
                    body_text = app_iframe.locator("body").inner_text()
                    if rem_str in body_text or app_iframe.get_by_text(rem_str).count() > 0:
                        encontrada = True
                except Exception:
                    pass

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

                        body_text = app_iframe.locator("body").inner_text()
                        if rem_str in body_text or app_iframe.get_by_text(rem_str).count() > 0:
                            encontrada = True

                        try:
                            cancel_btn = app_iframe.get_by_role("button", name=re.compile(r"Cancel Search", re.IGNORECASE))
                            if cancel_btn.count() > 0:
                                cancel_btn.first.click(timeout=3000)
                            else:
                                page.keyboard.press("Escape")
                        except Exception:
                            pass
                    except Exception as search_err:
                        log_sys.write(f"⚠️ Erro ao buscar remessa {rem_str}: {search_err}")

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

        log_sys.write(f"✅ {len(remessas_confirmadas_early)} remessa(s) confirmada(s). Prosseguindo com a criação...")

    # 8. Preenchimento de dados adicionais de Transporte (General Data) e Custos (Charges)
    # Entreposto (zcro) não usa transporte nem frete; Cabotagem (zout) ou parâmetros explícitos usam.
    deve_preencher_transporte = bool(transportadora or veiculo or empresa or (tipo_ordem.lower() == "zout"))
    deve_preencher_custos = bool(valor_frete is not None and valor_frete > 0)

    if deve_preencher_transporte:
        log_sys.write("⏳ Acessando aba General Data...")
        try:
            time.sleep(1.5)
            aguardar_fim_carregamento_sap(app_iframe, timeout=30000)
            app_iframe.get_by_role("tab", name=re.compile(r"^(General Data|Dados gerais)", re.IGNORECASE)).click(timeout=10000)
        except Exception:
            pass
            
        veiculo_val = veiculo or "CARRETA_CAR_SIDER_LS"
        log_sys.write(f"🚚 Preenchendo Veículo: {veiculo_val}")
        campo_veiculo = app_iframe.get_by_role("textbox", name=re.compile(r"^(Vehicle|Veículo)", re.IGNORECASE))
        campo_veiculo.click()
        campo_veiculo.fill(veiculo_val)
        campo_veiculo.press("Enter")
        aguardar_fim_carregamento_sap(app_iframe, timeout=15000)
        time.sleep(1)

        empresa_val = empresa or "vma1"
        log_sys.write(f"🚚 Preenchendo Empresa: {empresa_val}")
        campo_empresa = app_iframe.get_by_role("textbox", name=re.compile(r"^(Procuring Company Code|Empresa de compras|Empresa)", re.IGNORECASE))
        campo_empresa.click()
        campo_empresa.fill(empresa_val)

        transportadora_fixa = (transportadora or os.getenv("CABOTAGEM_TRANSPORTADORA_PADRAO", "9190617")).strip()
        log_sys.write(f"🚚 Preenchendo Transportador: {transportadora_fixa}")
        campo_carrier = app_iframe.get_by_role("textbox", name=re.compile(r"^(Carrier|Transportador)", re.IGNORECASE))
        campo_carrier.click()
        campo_carrier.fill(transportadora_fixa)
        campo_carrier.press("Enter")
        aguardar_fim_carregamento_sap(app_iframe, timeout=15000)
        time.sleep(1)

        # Tratar mensagens de aviso (warning/status) que o SAP costuma exibir no rodapé
        try:
            msgs_rodape = []
            msg_locs = app_iframe.locator("div.lsMSGPad div.lsMSGText, div.lsMessageBar, [role='listitem'][aria-label*='Warning'], [role='listitem'][aria-label*='Info'], [role='listitem'][aria-label*='Error']")
            total_msgs = msg_locs.count()
            for idx in range(min(total_msgs, 5)):
                try:
                    txt_m = msg_locs.nth(idx).inner_text().strip()
                    if txt_m and txt_m not in msgs_rodape:
                        msgs_rodape.append(txt_m)
                except Exception:
                    pass

            if msgs_rodape:
                log_sys.write(f"ℹ️ Mensagem SAP no rodapé após transportador: {' | '.join(msgs_rodape)}")
                # Se for aviso/warning que bloqueia o prosseguimento, tecla Enter para confirmar no SAP
                page.keyboard.press("Enter")
                aguardar_fim_carregamento_sap(app_iframe, timeout=10000)
                time.sleep(1)

            # Tenta fechar ou dispensar overlay de mensagens se houver botão fechar
            btn_close_msg = app_iframe.locator("div.lsMSGPad-close, button[title*='Close'], button[title*='Fechar'], [title*='Fechar lista de mensagens']").first
            if btn_close_msg.count() > 0 and btn_close_msg.is_visible():
                btn_close_msg.click(timeout=2000)
        except Exception as e_msg:
            log_sys.write(f"ℹ️ Verificação de rodapé SAP: {e_msg}")

    if deve_preencher_custos:
        log_sys.write("⏳ Subindo a página para acessar a aba de Despesas/Custos (Charges)...")

        # 1. Rolar para o topo (subir a tela)
        try:
            page.keyboard.press("Home")
            time.sleep(0.2)
            page.keyboard.press("PageUp")
            time.sleep(0.2)
        except Exception:
            pass

        try:
            app_iframe.locator("body").evaluate("""el => {
                window.scrollTo(0, 0);
                el.scrollTop = 0;
                if (document.documentElement) document.documentElement.scrollTop = 0;
                document.querySelectorAll('*').forEach(n => {
                    if (n.scrollTop > 0) n.scrollTop = 0;
                });
            }""")
        except Exception:
            pass

        try:
            page.evaluate("""() => {
                window.scrollTo(0, 0);
                document.querySelectorAll('iframe').forEach(ifr => {
                    try {
                        if (ifr.contentWindow) ifr.contentWindow.scrollTo(0, 0);
                        if (ifr.contentDocument) {
                            ifr.contentDocument.documentElement.scrollTop = 0;
                            ifr.contentDocument.body.scrollTop = 0;
                            ifr.contentDocument.querySelectorAll('*').forEach(n => {
                                if (n.scrollTop > 0) n.scrollTop = 0;
                            });
                        }
                    } catch(e) {}
                });
            }""")
        except Exception:
            pass

        time.sleep(0.5)

        # 2. Localizar e clicar na aba Charges / Custos / Despesas
        re_charges = re.compile(r"(Charges|Custos|Despesas)", re.IGNORECASE)
        log_sys.write("⏳ Clicando na aba de Despesas/Custos (Charges)...")

        aba_charges_confirmada = False
        for tentativa_aba in range(3):
            clicou_aba = False

            # Tenta clicar no botão de rolar abas caso esteja escondida por overflow
            try:
                btn_scroll_tab = app_iframe.locator("[title*='Scroll tabs right'], [title*='Rolar para a direita'], .lsTabStrip-scrollRight, [title*='Next Tab'], [title*='Próxima aba'], [title*='Seguinte']").first
                if btn_scroll_tab.count() > 0 and btn_scroll_tab.is_visible():
                    btn_scroll_tab.click(timeout=2000)
                    time.sleep(0.5)
            except Exception:
                pass

            # Estratégias para localizar a aba
            candidatos_aba = [
                lambda: app_iframe.get_by_role("tab", name=re_charges).first,
                lambda: app_iframe.locator("span[role='tab'], div[role='tab']").filter(has_text=re_charges).first,
                lambda: app_iframe.locator("[title*='Charges'], [title*='Custos'], [title*='Despesas']").first,
                lambda: app_iframe.locator("span, div, a").filter(has_text=re.compile(r"^(Charges|Custos|Despesas)$", re.IGNORECASE)).first,
            ]

            for cand_fn in candidatos_aba:
                try:
                    loc = cand_fn()
                    if loc.count() > 0 and loc.is_visible():
                        loc.scroll_into_view_if_needed()
                        loc.click(timeout=8000, force=True)
                        clicou_aba = True
                        break
                except Exception:
                    pass

            aguardar_fim_carregamento_sap(app_iframe, timeout=15000)
            time.sleep(1)

            # Verifica se os elementos da aba Charges apareceram na tela
            tem_elementos_charges = (
                app_iframe.locator("input[title*='Charge Type'], input[title*='Tipo de encargo'], input[title*='despesa']").count() > 0
                or app_iframe.locator("text=/\\bFB02\\b/").count() > 0
                or app_iframe.get_by_role("button", name=re.compile(r"^(Expand All|Expandir tudo)", re.I)).count() > 0
                or app_iframe.locator("div[title*='Expand All'], div[title*='Expandir tudo'], button:has-text('Expand All')").count() > 0
                or app_iframe.locator("[title*='BID Freight Table']").count() > 0
            )

            if tem_elementos_charges:
                aba_charges_confirmada = True
                log_sys.write("✅ Aba de Despesas/Custos (Charges) acessada com sucesso!")
                break
            else:
                log_sys.write(f"⚠️ Aba Charges ainda não confirmada (tentativa {tentativa_aba + 1}/3). Pressionando Enter para liberar avisos...")
                page.keyboard.press("Enter")
                time.sleep(0.5)
                page.keyboard.press("Escape")
                time.sleep(0.5)
                aguardar_fim_carregamento_sap(app_iframe, timeout=10000)

        # 3. Expandir linhas de Charges
        log_sys.write("⏳ Expandindo linhas de Charges...")
        try:
            expand_btn = app_iframe.get_by_role("button", name=re.compile(r"^(Expand All|Expandir tudo)", re.IGNORECASE)).first
            if expand_btn.count() == 0:
                expand_btn = app_iframe.locator("div[title*='Expand All'], div[title*='Expandir tudo'], button:has-text('Expand All'), button:has-text('Expandir tudo')").first
            if expand_btn.count() > 0 and expand_btn.is_visible():
                expand_btn.click(timeout=5000)
                aguardar_fim_carregamento_sap(app_iframe, timeout=15000)
        except Exception as e:
            log_sys.write(f"⚠️ Aviso ao tentar Expand All: {e}")

        valor_formatado = f"{valor_frete:.2f}".replace(".", ",") if isinstance(valor_frete, (int, float)) else str(valor_frete)

        cf = None
        try:
            cf = page.locator('iframe[name="__container1-iframe"]').content_frame
        except Exception:
            pass
        if not cf:
            try:
                cf = page.locator('iframe[title="Application"]').content_frame
            except Exception:
                pass

        target_frame = cf if cf is not None else app_iframe

        linha_fb02 = target_frame.locator("tr, [role='row']").filter(
            has=target_frame.locator("text=/\\bFB02\\b/i").or_(target_frame.locator("input[value='FB02' i]"))
        )

        fb02_atualizado = False
        if linha_fb02.count() > 0:
            log_sys.write("🏷️ Linha FB02 encontrada na tabela. Atualizando valor...")
            campo_rate = linha_fb02.first.get_by_role("textbox", name=re.compile(r"(Rate Amount|Montante da taxa|Montante)", re.IGNORECASE))
            if campo_rate.count() == 0:
                campo_rate = linha_fb02.first.get_by_role("combobox", name=re.compile(r"(Rate Amount|Montante da taxa|Montante)", re.IGNORECASE))
            if campo_rate.count() == 0:
                campo_rate = linha_fb02.first.locator("input[title*='Rate Amount'], input[title*='Montante'], input[type='text']")

            if campo_rate.count() > 0 and campo_rate.first.is_visible():
                try:
                    campo_rate.first.click(timeout=5000)
                    time.sleep(0.5)
                    page.keyboard.press("Control+A")
                    page.keyboard.press("Backspace")
                    page.keyboard.insert_text(valor_formatado)
                    page.keyboard.press("Enter")
                    aguardar_fim_carregamento_sap(app_iframe, timeout=15000)
                    log_sys.write(f"✅ Valor do frete {valor_formatado} preenchido na linha existente do FB02")
                    fb02_atualizado = True
                except Exception as e_upd:
                    log_sys.write(f"⚠️ Erro ao atualizar linha FB02 existente: {e_upd}")
            else:
                log_sys.write("⚠️ Campo Rate Amount não encontrado ou não editável na linha FB02.")

        if not fb02_atualizado:
            log_sys.write("⚠️ FB02 não encontrado nas linhas automáticas. Inserindo nova linha de despesa sob a linha 'Sum'...")

            # 1. Seleciona a linha 'Sum' (Row-2 na tabela esquerda)
            try:
                log_sys.write("  🔘 Selecionando a linha 'Sum' na tabela de Charges...")

                # Desmarca qualquer linha que esteja previamente marcada
                try:
                    icones_sel = target_frame.locator(".urSTRowSelIcon, [class*='urSTRowSelIcon']")
                    for idx_m in range(icones_sel.count()):
                        ic = icones_sel.nth(idx_m)
                        ic.click(timeout=5000)
                        time.sleep(0.3)
                except Exception:
                    pass

                clicou_sum = False
                # Tentativa A: Pelo ID da Row-2 gravado no codegen ([id*='-mrss-cont-left-Row-2'])
                try:
                    gridcell_r2 = target_frame.locator("[id*='-mrss-cont-left-Row-2'], [id*='-left-Row-2']").get_by_role("gridcell", name=re.compile(r"To select a row", re.I)).first
                    if gridcell_r2.count() > 0 and gridcell_r2.is_visible():
                        gridcell_r2.click(timeout=5000)
                        clicou_sum = True
                        log_sys.write("  ✅ Linha 'Sum' (Row-2) selecionada via gridcell 'To select a row'!")
                except Exception as e_r2:
                    log_sys.write(f"  ℹ️ Tentativa Row-2 direta: {e_r2}")

                # Tentativa B: Localizar dinamicamente a linha que contém o texto 'Sum'
                if not clicou_sum:
                    try:
                        span_sum = target_frame.locator("span.lsCaption, span").filter(has_text=re.compile(r"^\s*Sum\s*$", re.I)).first
                        if span_sum.count() > 0:
                            tr_sum = span_sum.locator("xpath=ancestor::tr[1]")
                            cell_sum = tr_sum.get_by_role("gridcell", name=re.compile(r"To select a row", re.I)).first
                            if cell_sum.count() == 0:
                                cell_sum = tr_sum.locator(".urSTRowUnSelIcon, .urSTSCOuterDiv, [id*='-ariatutor']").first
                            if cell_sum.count() > 0 and cell_sum.is_visible():
                                cell_sum.click(timeout=5000)
                                clicou_sum = True
                                log_sys.write("  ✅ Linha 'Sum' selecionada dinamicamente via ancestral!")
                    except Exception as e_dyn:
                        log_sys.write(f"  ℹ️ Tentativa dinâmica Sum: {e_dyn}")

                # Tentativa C: Fallback em qualquer Row-2
                if not clicou_sum:
                    target_frame.locator("[id*='Row-2']").get_by_role("gridcell", name=re.compile(r"To select a row", re.I)).first.click(timeout=5000)
                    clicou_sum = True
                    log_sys.write("  ✅ Linha Row-2 selecionada via fallback!")

                aguardar_fim_carregamento_sap(app_iframe, timeout=10000)
                time.sleep(1)
            except Exception as e_sel_sum:
                log_sys.write(f"  ⚠️ Erro ao selecionar linha Sum: {e_sel_sum}")

            # 2. Clica no botão Insert e na opção Charge Line
            log_sys.write("  🔘 Clicando no botão Insert...")
            btn_ins = target_frame.get_by_role("button", name=re.compile(r"^(Insert|Inserir)", re.I), exact=True)
            if btn_ins.count() == 0:
                btn_ins = target_frame.locator("div[title*='Insert'], div[title*='Inserir'], button[title*='Insert']")
            btn_ins.first.click(timeout=5000)
            time.sleep(1)

            log_sys.write("  🔘 Clicando na opção 'Charge Line'...")
            opt_cline = target_frame.get_by_text(re.compile(r"^(Charge Line|Linha de encargo)", re.I), exact=True)
            if opt_cline.count() == 0:
                opt_cline = target_frame.locator("[role='menuitem'], .urMnuTxt, span").filter(has_text=re.compile(r"^(Charge Line|Linha de encargo)", re.I))
            opt_cline.first.click(timeout=5000)
            aguardar_fim_carregamento_sap(app_iframe, timeout=15000)
            time.sleep(1.5)

            # 3. Expand All novamente (o menu encolhe após Insert)
            log_sys.write("⏳ Expandindo linhas de Charges novamente (Expand All)...")
            try:
                expand_btn = target_frame.get_by_role("button", name=re.compile(r"^(Expand All|Expandir tudo)", re.I)).first
                if expand_btn.count() == 0:
                    expand_btn = target_frame.locator("div[title*='Expand All'], div[title*='Expandir tudo'], button:has-text('Expand All')").first
                if expand_btn.count() > 0 and expand_btn.is_visible():
                    expand_btn.click(timeout=5000)
                    aguardar_fim_carregamento_sap(app_iframe, timeout=15000)
                    time.sleep(1.5)
            except Exception as e_exp:
                log_sys.write(f"⚠️ Aviso ao expandir após Insert: {e_exp}")

            # 4. Preenche a linha criada logo abaixo da Sum com Charge Type = FB02
            log_sys.write("  🔘 Preenchendo 'Charge Type' com FB02...")
            campo_ct = target_frame.get_by_role("textbox", name=re.compile(r"^(Charge Type|Tipo de encargo|Tipo de despesa)", re.I)).first
            if campo_ct.count() == 0:
                campo_ct = target_frame.locator("input[title*='Charge Type'], input[title*='Tipo de encargo']").first

            campo_ct.click(timeout=5000)
            time.sleep(0.3)
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.keyboard.insert_text("FB02")
            page.keyboard.press("Enter")
            aguardar_fim_carregamento_sap(app_iframe, timeout=15000)
            time.sleep(1.5)

            # 5. Preenche o valor do frete FB02 (Rate Amount)
            log_sys.write(f"  🔘 Preenchendo valor do frete FB02 ({valor_formatado})...")
            linha_fb02_nova = target_frame.locator("tr, [role='row']").filter(
                has=target_frame.locator("text=/\\bFB02\\b/i").or_(target_frame.locator("input[value='FB02' i]"))
            )

            campo_rate_novo = None
            if linha_fb02_nova.count() > 0:
                campo_rate_novo = linha_fb02_nova.first.get_by_role("textbox", name=re.compile(r"(Rate Amount|Montante da taxa|Montante)", re.IGNORECASE))
                if campo_rate_novo.count() == 0:
                    campo_rate_novo = linha_fb02_nova.first.get_by_role("combobox", name=re.compile(r"(Rate Amount|Montante da taxa|Montante)", re.IGNORECASE))
                if campo_rate_novo.count() == 0:
                    campo_rate_novo = linha_fb02_nova.first.locator("input[title*='Rate Amount'], input[title*='Montante'], input[type='text']")

            if not campo_rate_novo or campo_rate_novo.count() == 0:
                campo_rate_novo = target_frame.locator("[id*='-mrss-cont-none-Row-']").last.get_by_role("textbox", name=re.compile(r"(Rate Amount|Montante da taxa|Montante)", re.I))

            if not campo_rate_novo or campo_rate_novo.count() == 0:
                campo_rate_novo = target_frame.get_by_role("textbox", name=re.compile(r"(Rate Amount|Montante da taxa|Montante)", re.I)).last

            if campo_rate_novo and campo_rate_novo.count() > 0 and campo_rate_novo.first.is_visible():
                campo_rate_novo.first.click(timeout=5000)
                time.sleep(0.5)
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                page.keyboard.insert_text(valor_formatado)
                page.keyboard.press("Enter")
                aguardar_fim_carregamento_sap(app_iframe, timeout=15000)
                log_sys.write(f"✅ Valor do frete {valor_formatado} preenchido com sucesso na linha criada do FB02!")
                fb02_atualizado = True
            else:
                log_sys.write(f"⚠️ Não foi possível localizar o campo Rate Amount para o frete {valor_formatado}")
        try:
            app_iframe.get_by_label("BID Freight Table").click(timeout=5000)
            log_sys.write("✅ Clicou em BID Freight Table para confirmar")
        except Exception:
            pass

        time.sleep(1)

    # 9. Salvar (Ctrl+S)
    log_sys.write("💾 Salvando Ordem de Frete (Ctrl+S)...")
    try:
        page.keyboard.press("Control+s")
        time.sleep(0.5)
        btn_save = app_iframe.get_by_role("button", name=re.compile(r"Save.*Emphasized", re.IGNORECASE))
        if btn_save.count() > 0:
            btn_save.first.click(timeout=10000)
    except Exception as e:
        log_sys.write(f"⚠️ Erro ao salvar inicial: {e}")
        
    log_sys.write("⏳ Aguardando confirmação do SAP com o número da OF...")
    of_regex = re.compile(r"61\d{8}")
    max_tentativas = 15
    of_numero = None
    
    for tentativa in range(max_tentativas):
        time.sleep(2)
        log_sys.write(f"🔍 Buscando número da OF... Tentativa {tentativa + 1}/{max_tentativas}")
        
        if tentativa == 5:
            try:
                page.keyboard.press("Control+s")
                btn_save = app_iframe.get_by_role("button", name=re.compile(r"Save.*Emphasized", re.IGNORECASE))
                if btn_save.count() > 0:
                    btn_save.first.click(timeout=5000)
            except Exception:
                pass
        
        # Cabeçalhos
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
            
        # Corpo da página
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
    log_sys.write(f"📊 Remessas confirmadas: {remessas_confirmadas_early} | Ausentes: {remessas_ausentes_early}")

    return {
        "of_numero": of_numero,
        "remessas_confirmadas": remessas_confirmadas_early,
        "remessas_ausentes": remessas_ausentes_early,
    }


def rodar_criacao_of_playwright(
    remessas: list,
    usuario: str,
    senha: str,
    tipo_ordem: str = "zcro",
    transportadora: str = None,
    valor_frete: float = None,
    veiculo: str = None,
    empresa: str = None,
    headless: bool = True
) -> dict:
    """
    Executa a criação de uma única Ordem de Frete (OF) no SAP Fiori via Playwright.
    Suporta tipo_ordem 'zcro' (Entreposto) ou 'zout' (Cabotagem).
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
    
    try:
        playwright_instance = sync_playwright().start()
        browser = playwright_instance.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()
        page.on("dialog", lambda dialog: dialog.accept())
        
        log_sys.write("🔐 Acessando SAP Fiori - Criar Ordem de Frete...")
        page.goto(SAP_FO_URL, timeout=60000)
        
        return _executar_criacao_of_na_pagina(
            page=page,
            remessas=remessas,
            usuario=usuario,
            senha=senha,
            tipo_ordem=tipo_ordem,
            transportadora=transportadora,
            valor_frete=valor_frete,
            veiculo=veiculo,
            empresa=empresa
        )
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


def rodar_criacao_of_cabotagem_playwright(
    remessas: list, 
    transportadora: str, 
    valor_frete: float, 
    usuario: str, 
    senha: str,
    headless: bool = True
) -> dict:
    """
    Função dedicada para Cabotagem (retrocompatível).
    Invoca o criador universal configurado com tipo 'zout', veículo, empresa e despesas.
    """
    return rodar_criacao_of_playwright(
        remessas=remessas,
        usuario=usuario,
        senha=senha,
        tipo_ordem="zout",
        transportadora=transportadora,
        valor_frete=valor_frete,
        veiculo="CARRETA_CAR_SIDER_LS",
        empresa="vma1",
        headless=headless
    )


def rodar_criacao_of_playwright_multipla(
    grupos: list, 
    usuario: str, 
    senha: str, 
    tipo_ordem: str = "zcro", 
    headless: bool = True
) -> list:
    """
    Executa a criação de múltiplas Ordens de Frete (OF) no SAP Fiori via Playwright.
    Reutiliza a sessão/cookies no mesmo BrowserContext, criando uma aba limpa por grupo
    para isolar falhas entre clientes e evitar vazamento de memória ou travamento de página.
    Retorna uma lista de dicionários: [{'remessas': [...], 'of': '...', 'erro': None}, ...]
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
        browser = playwright_instance.chromium.launch(headless=headless)
        context = browser.new_context()
        
        for idx, remessas in enumerate(grupos):
            remessas_limpas = [str(r).strip() for r in remessas if str(r).strip()]
            if not remessas_limpas:
                continue

            log_sys.write(f"💼 Processando Grupo [{idx + 1}/{len(grupos)}] | Remessas: {', '.join(remessas_limpas)}")
            page = None
            try:
                # Se o browser fechou ou desconectou por algum motivo, restabelece
                if not browser.is_connected():
                    log_sys.write("⚠️ Sessão do navegador desconectada. Reiniciando sessão...")
                    browser = playwright_instance.chromium.launch(headless=headless)
                    context = browser.new_context()

                page = context.new_page()
                page.on("dialog", lambda dialog: dialog.accept())
                
                log_sys.write(f"🔐 Acessando SAP Fiori para Grupo [{idx + 1}/{len(grupos)}]...")
                page.goto(SAP_FO_URL, timeout=60000)
                
                res = _executar_criacao_of_na_pagina(
                    page=page,
                    remessas=remessas_limpas,
                    usuario=usuario,
                    senha=senha,
                    tipo_ordem=tipo_ordem,
                    transportadora=None,
                    valor_frete=None,
                    veiculo=None,
                    empresa=None
                )
                
                of_num = res.get("of_numero")
                resultados.append({
                    "remessas": remessas_limpas,
                    "of": of_num,
                    "erro": None
                })
                log_sys.write(f"✅ Grupo [{idx + 1}/{len(grupos)}] concluído! OF: {of_num}")
                
            except Exception as item_err:
                log_sys.write(f"❌ Erro ao criar OF para o grupo [{idx + 1}/{len(grupos)}] ({', '.join(remessas_limpas)}): {item_err}")
                resultados.append({
                    "remessas": remessas_limpas,
                    "of": None,
                    "erro": str(item_err)
                })
            finally:
                if page:
                    try:
                        page.close()
                    except Exception:
                        pass
                        
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
