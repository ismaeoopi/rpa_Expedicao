import os
import sys
import time
import re
from dotenv import load_dotenv

# Garantindo que a raiz do projeto esteja no sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.utils.common import log_sys
from src.expedicao.sap_packlist import _garantir_playwright_instalado

SAP_CHANGE_FO_URL = "https://appprod.sap.valgroupco.com/sap/bc/ui2/flp?sap-client=200&sap-language=PT#FreightOrder-changeRoad?sap-ui-tech-hint=WDA"

def log_console(msg: str):
    """Imprime com flush direto no console para acompanhamento real-time."""
    log_line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(log_line, flush=True)
    # log_sys.write já encaminha para o sistema de logging; não duplicar no console
    try:
        log_sys.write(msg, echo=False)
    except Exception:
        try:
            log_sys.write(msg)
        except Exception:
            pass


def consultar_e_editar_custos_of(
    of_numero: str,
    novo_valor_teste: str = "999,99",
    texto_linha: str = "",
    linha_editar: int = 1,
    salvar: bool = False,
    headless: bool = False,
    tempo_espera_visual: int = 30,
    edicoes: list = None,
) -> dict:
    """
    Acessa a transação FreightOrder-changeRoad no SAP Fiori,
    carrega a OF informada, expande a árvore de custos e preenche o(s) valor(es).

    Args:
        of_numero: Número da Ordem de Frete (ex: '6100325111')
        novo_valor_teste: Valor a ser preenchido (usado quando 'edicoes' não é fornecido).
        texto_linha: Texto para buscar a linha (ex: 'CAMIL'). Usado sem 'edicoes'.
        linha_editar: Índice 1-based da linha. Fallback quando texto_linha não acha.
        salvar: Se True, salva a OF no SAP (Ctrl+S) ao final. Padrão: False.
        headless: Se True, executa sem abrir o navegador.
        tempo_espera_visual: Segundos para manter o browser aberto após a última edição.
        edicoes: Lista de dicts para editar múltiplas linhas na MESMA sessão.
                 Formato: [{"texto_linha": "CAMIL", "linha_editar": 1, "valor": "1.817,27"}, ...]
                 Quando fornecido, ignora novo_valor_teste/texto_linha/linha_editar.

    Por padrão (salvar=False), a alteração NÃO é gravada no SAP.
    """
    load_dotenv()
    usuario = os.getenv("SAP_WEB_USER")
    senha = os.getenv("SAP_WEB_PASSWORD")

    if not usuario or not senha:
        raise ValueError("Credenciais SAP_WEB_USER e SAP_WEB_PASSWORD não encontradas no .env")

    localappdata = os.environ.get("LOCALAPPDATA", "")
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(localappdata, "ms-playwright")

    if not _garantir_playwright_instalado():
        raise RuntimeError("Playwright/Chromium não está disponível.")

    from playwright.sync_api import sync_playwright

    # Normalizar: se 'edicoes' não for passado, cria lista com a edição única
    if not edicoes:
        edicoes = [{
            "texto_linha": texto_linha,
            "linha_editar": linha_editar,
            "valor": novo_valor_teste,
        }]

    playwright_instance = None
    browser = None
    resultado = {
        "of_numero": of_numero,
        "linhas_extraidas": [],
        "edicoes_resultado": [],
        "edicao_sucesso": False,
        "valor_editado": edicoes[0]["valor"] if edicoes else novo_valor_teste,
    }

    try:
        log_console(f"🚀 [SAP Custos OF] Iniciando automação para OF: {of_numero}")
        playwright_instance = sync_playwright().start()
        browser = playwright_instance.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        log_console("🔐 Acessando SAP Fiori - Modificar Ordem de Frete...")
        page.goto(SAP_CHANGE_FO_URL, timeout=60000)

        # 1. Login no SAP Fiori
        log_console("🔐 Efetuando Login...")
        try:
            page.get_by_role("textbox", name=re.compile(r"(User|Usuário)", re.I)).first.wait_for(state="visible", timeout=30000)
        except Exception:
            pass

        if page.get_by_role("textbox", name="User").is_visible():
            page.get_by_role("textbox", name="User").fill(usuario)
            page.get_by_role("textbox", name="Password").fill(senha)
            page.get_by_role("button", name="Log On").click()
        elif page.get_by_role("textbox", name="Usuário").is_visible():
            page.get_by_role("textbox", name="Usuário").fill(usuario)
            page.get_by_role("textbox", name="Usuário").press("Tab")
            page.get_by_role("textbox", name="Senha").fill(senha)
            page.get_by_role("textbox", name="Senha").press("Enter")
            try:
                page.get_by_role("button", name="Logon").click(timeout=3000)
            except Exception:
                pass

        time.sleep(3)
        log_console("⏳ Conectando ao iframe da aplicação...")

        # 2. Conectar ao iframe Aplicação (usando content_frame conforme codegen)
        app_iframe = None
        iframe_locator = None
        for iframe_sel in ['iframe[title="Aplicação"]', 'iframe[title="Application"]']:
            try:
                iframe_el = page.locator(iframe_sel)
                if iframe_el.count() > 0:
                    app_iframe = iframe_el.content_frame
                    iframe_locator = iframe_sel
                    log_console(f"  ✅ Iframe conectado via content_frame de '{iframe_sel}'")
                    break
            except Exception:
                pass

        if not app_iframe:
            # Fallback: tenta qualquer iframe
            app_iframe = page.locator("iframe").first.content_frame
            log_console("  ⚠️ Iframe conectado via fallback genérico")

        # 3. Preencher OF (conforme codegen: name="Ordem de frete Existem" / "Ordem de frete  Necessário")
        log_console(f"📝 Preenchendo Ordem de Frete: {of_numero}...")
        try:
            # Codegen usa "Ordem de frete Existem" para click e "Ordem de frete  Necessário" para fill
            input_of = app_iframe.get_by_role("textbox", name=re.compile(r"Ordem de frete", re.I)).first
            input_of.wait_for(state="visible", timeout=30000)
            input_of.click()
            input_of.fill(of_numero)
            input_of.press("Enter")
            log_console(f"  ✅ OF {of_numero} preenchida!")
        except Exception as e_of:
            log_console(f"  ⚠️ Fallback para preenchimento de OF: {e_of}")
            input_of = app_iframe.locator("input[title*='frete'], input[name='WD51']").first
            input_of.click()
            input_of.fill(of_numero)
            input_of.press("Enter")

        log_console("⏳ Aguardando a Ordem de Frete carregar...")
        time.sleep(5)
        # Aguardar loading overlay sumir
        for sel in ["#ur-loading-box", "#ur-loading-itm2"]:
            try:
                loader = app_iframe.locator(sel)
                if loader.count() > 0:
                    loader.first.wait_for(state="hidden", timeout=45000)
            except Exception:
                pass
        time.sleep(2)

        # 3.5. Garantir Modo de Edição ('Processar' / Ctrl+E)
        log_console("✏️ Garantindo Modo de EDIÇÃO na tela ('Processar' / Ctrl+E)...")
        try:
            btn_proc = app_iframe.locator("[title*='Ctrl+E'], [title*='Processar'], div:has-text('Processar')").first
            if btn_proc.count() > 0 and btn_proc.is_visible():
                aria_dis = (btn_proc.get_attribute("aria-disabled") or "").lower()
                cls_str = (btn_proc.get_attribute("class") or "").lower()

                if aria_dis != "true" and "disabled" not in cls_str:
                    btn_proc.click()
                    log_console("  ✅ Botão 'Processar' (Ctrl+E) CLICADO COM SUCESSO! Tela alternada para Modo de EDIÇÃO.")
                    time.sleep(2)
                    for sel in ["#ur-loading-box", "#ur-loading-itm2"]:
                        try:
                            loader = app_iframe.locator(sel)
                            if loader.count() > 0:
                                loader.first.wait_for(state="hidden", timeout=45000)
                        except Exception:
                            pass
                    time.sleep(3)
                else:
                    log_console("  ℹ️ Botão 'Processar' desativado (OF já está em Modo de Edição).")
            else:
                page.keyboard.press("Control+e")
                log_console("  ℹ️ Atalho Ctrl+E pressionado via teclado para garantir edição.")
                time.sleep(2)
        except Exception as e_proc:
            log_console(f"  ⚠️ Erro ao verificar botão Processar: {e_proc}")

        time.sleep(1)

        # 4. Clicar na aba "Custos  Bloco de atribuição" (passo CRÍTICO que faltava)
        log_console("📂 Clicando na aba 'Custos' (Bloco de atribuição)...")
        try:
            tab_custos = app_iframe.get_by_role("tab", name=re.compile(r"(Custos|Charges).*Bloco de atribuição|Assignment Block", re.I))
            if tab_custos.count() > 0:
                tab_custos.first.click()
                log_console("  ✅ Aba 'Custos' clicada!")
            else:
                # Fallback: procurar por texto
                app_iframe.get_by_text(re.compile(r"Custos|Charges", re.I)).first.click()
                log_console("  ✅ Aba 'Custos' clicada via texto!")
        except Exception as e_tab:
            log_console(f"  ⚠️ Erro ao clicar na aba Custos: {e_tab}")
        
        time.sleep(2)
        # Aguardar loading
        for sel in ["#ur-loading-box", "#ur-loading-itm2"]:
            try:
                loader = app_iframe.locator(sel)
                if loader.count() > 0:
                    loader.first.wait_for(state="hidden", timeout=30000)
            except Exception:
                pass

        # 5. Garantir que a árvore mostre os nós dos clientes (Nível 1)
        log_console("⏳ Expandindo o nó raiz para visualizar os clientes...")
        try:
            # Se a árvore estiver colapsada na raiz, expandir a raiz clicando no seu botão 'Nível'
            gridcells_iniciais = app_iframe.get_by_role("gridcell").all()
            if len(gridcells_iniciais) <= 2:
                root_toggle = app_iframe.get_by_role("gridcell").first.get_by_label("Nível")
                if root_toggle.count() > 0:
                    root_toggle.click()
                    log_console("  ✅ Nó raiz expandido")
                    time.sleep(2)
        except Exception as e_root:
            log_console(f"  ℹ️ Expansão do nó raiz: {e_root}")

        # 6. Loop de edições – todas na mesma sessão do browser
        edicao_sucesso_geral = False

        for num_ed, ed in enumerate(edicoes, 1):
            ed_texto  = ed.get("texto_linha", "")
            ed_linha  = ed.get("linha_editar", num_ed)
            ed_valor  = ed.get("valor", novo_valor_teste)
            desc_alvo = ed_texto or f"linha {ed_linha}"

            log_console(f"\n{'─'*50}")
            log_console(f"✏️  Edição {num_ed}/{len(edicoes)}: {desc_alvo}  →  {ed_valor}")
            log_console(f"{'─'*50}")

            gridcell_target = None
            edicao_sucesso  = False

            log_console(f"🎯 Localizando nó do cliente para: {desc_alvo}...")

            if ed_texto:
                try:
                    # Buscar pela N-ésima ocorrência do texto (para clientes repetidos como CAMIL)
                    cell_loc = app_iframe.get_by_role("gridcell", name=re.compile(r".*" + re.escape(ed_texto) + r".*", re.I))
                    total_ocorrencias = cell_loc.count()
                    log_console(f"  📊 Ocorrências de '{ed_texto}' encontradas: {total_ocorrencias}")
                    if total_ocorrencias > 0:
                        # Usar o índice de linha como desempate entre ocorrências iguais
                        ocorrencia_idx = min(ed_linha - 1, total_ocorrencias - 1)
                        gridcell_target = cell_loc.nth(ocorrencia_idx)
                        log_console(f"  ✅ Usando ocorrência [{ocorrencia_idx + 1}] de '{ed_texto}'")
                    else:
                        # Fallback: buscar por texto diretamente
                        text_loc = app_iframe.get_by_text(re.compile(re.escape(ed_texto), re.I))
                        if text_loc.count() > 0:
                            gridcell_target = text_loc.nth(min(ed_linha - 1, text_loc.count() - 1)).locator(
                                "xpath=ancestor::*[contains(@role, 'gridcell') or contains(@class, 'lsControlCell') or self::td]"
                            ).first
                            log_console(f"  ✅ Gridcell ancestral encontrado via texto '{ed_texto}'!")
                except Exception as e_cell:
                    log_console(f"  ⚠️ Busca por texto do cliente: {e_cell}")

            if not gridcell_target:
                try:
                    cells = app_iframe.get_by_role("gridcell", name=re.compile(r"Nível 1", re.I)).all()
                    log_console(f"  📊 Total de gridcells Nível 1 encontrados: {len(cells)}")
                    idx_cel = max(0, ed_linha - 1)
                    if idx_cel < len(cells):
                        gridcell_target = cells[idx_cel]
                        log_console(f"  ✅ Gridcell no índice {idx_cel} (linha {ed_linha}) selecionado!")
                    else:
                        log_console(f"  ⚠️ Índice {idx_cel} fora do alcance (encontrados {len(cells)})")
                except Exception as e_idx:
                    log_console(f"  ⚠️ Busca por índice de cliente: {e_idx}")

            # 7. Expandir, preencher e RECOLAPSAR o nó
            if gridcell_target:
                try:
                    gridcell_target.scroll_into_view_if_needed()
                    time.sleep(0.5)

                    row_id = ""
                    try:
                        row_id = gridcell_target.evaluate("el => { let p = el; while(p) { if(p.id && p.id.includes('Row-')) return p.id; p = p.parentElement; } return ''; }")
                        log_console(f"  📌 Row ID do cliente: '{row_id}'")
                    except Exception:
                        pass

                    # Guardar referência ao toggle para recolapsar depois
                    toggle = gridcell_target.get_by_label("Nível")
                    toggle_usou = False
                    if toggle.count() > 0:
                        toggle.first.click()
                        toggle_usou = True
                        log_console(f"  ✅ Nó do cliente {desc_alvo} expandido via 'Nível'!")
                    else:
                        gridcell_target.click()
                        log_console(f"  ✅ Gridcell do cliente {desc_alvo} clicado!")

                    time.sleep(1)
                    for sel in ["#ur-loading-box", "#ur-loading-itm2"]:
                        try:
                            loader = app_iframe.locator(sel)
                            if loader.count() > 0:
                                loader.first.wait_for(state="hidden", timeout=15000)
                        except Exception:
                            pass
                    time.sleep(2)

                    candidate_locators = []
                    if row_id and "Row-" in row_id:
                        try:
                            prefix, num_str = row_id.rsplit("Row-", 1)
                            r_num = int(num_str)
                            right_prefix = prefix.replace("-left-", "-none-")
                            for offset in [1, 0, 2, 3, -1]:
                                candidate_locators.append(app_iframe.locator(f"#{right_prefix}Row-{r_num + offset}"))
                            for offset in [1, 0, 2]:
                                candidate_locators.append(app_iframe.locator(f"#{prefix}Row-{r_num + offset}"))
                        except Exception as e_prefix:
                            log_console(f"  ℹ️ Erro ao converter ID de painel: {e_prefix}")

                    if not candidate_locators:
                        parent_row = gridcell_target.locator("xpath=ancestor::tr[1]")
                        candidate_locators = [
                            parent_row.locator("xpath=following-sibling::tr[1]"),
                            parent_row,
                            parent_row.locator("xpath=following-sibling::tr[2]"),
                        ]

                    target_element = None
                    log_console(f"🔍 Procurando campo de frete para '{desc_alvo}'...")

                    for idx_sub, sub_r in enumerate(candidate_locators):
                        try:
                            if sub_r.count() > 0 and sub_r.is_visible():
                                cbs = sub_r.get_by_role("combobox", name=re.compile(r"Montante do preço de tarifa|Rate Amount", re.I)).all()
                                for cb in cbs:
                                    if cb.is_visible():
                                        target_element = cb
                                        log_console(f"  ✅ Combobox localizado na sub-linha [{idx_sub+1}]!")
                                        break
                                if not target_element:
                                    inps = sub_r.locator("input[role='combobox'], input[title*='Montante'], input[title*='tarifa']").all()
                                    for inp in inps:
                                        if inp.is_visible():
                                            target_element = inp
                                            log_console(f"  ✅ Input por seletor na sub-linha [{idx_sub+1}]!")
                                            break
                                if not target_element:
                                    spans = sub_r.locator("span[title*='Montante'], span[title*='calculado'], span[title*='tarifa'], span.lsTextView--usedInTable").all()
                                    for sp in spans:
                                        if sp.is_visible():
                                            txt = sp.inner_text().strip()
                                            if not txt:
                                                log_console(f"  ⚠️ Span vazio ignorado na sub-linha [{idx_sub+1}]")
                                                continue
                                            log_console(f"  ✅ Span ('{txt}') na sub-linha [{idx_sub+1}]!")
                                            target_element = sp
                                            break
                                if target_element:
                                    break
                        except Exception as ex_sub:
                            log_console(f"  ℹ️ Sub-linha [{idx_sub+1}]: {ex_sub}")

                    if target_element:
                        target_element.scroll_into_view_if_needed()
                        time.sleep(0.5)
                        target_element.click()
                        time.sleep(0.3)
                        try:
                            target_element.click()
                        except Exception:
                            pass
                        log_console("  ✅ Campo de frete ativado!")
                        time.sleep(0.8)

                        cell_input = target_element.locator("xpath=ancestor::td[1]//input | ancestor::tr[1]//input").first
                        try:
                            if cell_input.count() > 0 and cell_input.is_visible():
                                cell_input.fill(ed_valor)
                                cell_input.press("Enter")
                                edicao_sucesso = True
                                log_console(f"🎉 Valor '{ed_valor}' preenchido no input da célula para {desc_alvo}!")
                            else:
                                target_element.fill(ed_valor)
                                target_element.press("Enter")
                                edicao_sucesso = True
                                log_console(f"🎉 Valor '{ed_valor}' preenchido no elemento para {desc_alvo}!")
                        except Exception as ex_fill:
                            log_console(f"  ℹ️ Fallback de preenchimento: {ex_fill}")
                            try:
                                target_element.type(ed_valor, delay=50)
                                target_element.press("Enter")
                                edicao_sucesso = True
                                log_console(f"🎉 Valor '{ed_valor}' preenchido via type para {desc_alvo}!")
                            except Exception:
                                page.keyboard.press("Control+a")
                                page.keyboard.press("Backspace")
                                page.keyboard.type(ed_valor, delay=80)
                                page.keyboard.press("Enter")
                                edicao_sucesso = True
                                log_console(f"🎉 Valor '{ed_valor}' preenchido via keyboard para {desc_alvo}!")

                        # ── RECOLAPSAR o nó após edição bem-sucedida ──────────
                        if edicao_sucesso:
                            log_console(f"  🔒 Recolapsando nó '{desc_alvo}'...")
                            time.sleep(1)
                            for sel in ["#ur-loading-box", "#ur-loading-itm2"]:
                                try:
                                    loader = app_iframe.locator(sel)
                                    if loader.count() > 0:
                                        loader.first.wait_for(state="hidden", timeout=10000)
                                except Exception:
                                    pass
                            try:
                                # Reclicar no toggle Nível da mesma gridcell para fechar
                                if toggle_usou and toggle.count() > 0 and toggle.first.is_visible():
                                    toggle.first.click()
                                    log_console(f"  ✅ Nó '{desc_alvo}' recolapsado via toggle!")
                                else:
                                    # Fallback: clicar na gridcell do cliente novamente
                                    gridcell_target.click()
                                    log_console(f"  ✅ Nó '{desc_alvo}' recolapsado via clique!")
                                time.sleep(1)
                                for sel in ["#ur-loading-box", "#ur-loading-itm2"]:
                                    try:
                                        loader = app_iframe.locator(sel)
                                        if loader.count() > 0:
                                            loader.first.wait_for(state="hidden", timeout=10000)
                                    except Exception:
                                        pass
                            except Exception as e_colapso:
                                log_console(f"  ⚠️ Erro ao recolapsar: {e_colapso}")
                    else:
                        log_console(f"⚠️ Campo de montante não encontrado para {desc_alvo}.")

                except Exception as ex_op:
                    log_console(f"❌ Erro ao expandir/editar {desc_alvo}: {ex_op}")
            else:
                log_console(f"⚠️ Não foi possível localizar o nó do cliente para {desc_alvo}.")

            resultado["edicoes_resultado"].append({
                "texto_linha": ed_texto,
                "linha_editar": ed_linha,
                "valor": ed_valor,
                "sucesso": edicao_sucesso,
            })
            if edicao_sucesso:
                edicao_sucesso_geral = True

            # Pausa entre edições para o SAP estabilizar
            if num_ed < len(edicoes):
                log_console("  ⏳ Aguardando SAP estabilizar (3s)...")
                time.sleep(3)
                for sel in ["#ur-loading-box", "#ur-loading-itm2"]:
                    try:
                        loader = app_iframe.locator(sel)
                        if loader.count() > 0:
                            loader.first.wait_for(state="hidden", timeout=15000)
                    except Exception:
                        pass
                log_console("  ✅ Pronto para a próxima edição.")

        # 8. Extrair resumo final das linhas visíveis
        try:
            body_text = app_iframe.locator("body").inner_text(timeout=10000)
            keywords = ["FB", "BRL", "USD", "EUR", "Montante", "Rate", "Amount", "Taxa", "Charge", "Item", "Frete"]
            for line in body_text.splitlines():
                stripped = line.strip()
                if stripped and any(kw in stripped for kw in keywords):
                    resultado["linhas_extraidas"].append([stripped])
        except Exception:
            pass

        resultado["edicao_sucesso"] = edicao_sucesso_geral
        resultado["linha_editada"] = ", ".join(
            ed.get("texto_linha") or str(ed.get("linha_editar", "?")) for ed in edicoes
        )

        # 9. Verificar total do SAP vs soma esperada dos CT-es
        log_console("\n🔢 Verificando total SAP vs soma esperada dos CT-es...")
        try:
            # Soma esperada: total de todos os valores das edições
            soma_esperada = sum(
                float(ed.get("valor", "0").replace(".", "").replace(",", "."))
                for ed in edicoes
            )

            # Buscar linha de total na árvore (geralmente a linha raiz / nó pai)
            # O SAP exibe o total na linha de nível 0 ou em um rodapé da tabela
            total_sap_float = None
            total_sap_str = ""

            # Tenta 0: Input específico pelo title "Montante total arredondado em moeda do documento"
            try:
                total_input = app_iframe.locator("input[title*='Montante total'], input[title*='Total amount']").first
                if total_input.count() > 0 and total_input.is_visible():
                    val_attr = total_input.input_value() or total_input.get_attribute("value") or ""
                    val_attr = val_attr.strip()
                    nums = re.findall(r"[\d\.]+,[\d]{2}", val_attr)
                    if nums:
                        total_sap_str = nums[-1]
                        total_sap_float = float(total_sap_str.replace(".", "").replace(",", "."))
                        log_console(f"  📌 Total capturado no campo oficial: {total_sap_str}")
            except Exception as e_tot_input:
                log_console(f"  ℹ️ Erro ao ler input de total por title: {e_tot_input}")

            # Tenta 1: gridcell de Nível 0 (raiz da árvore de custos)
            if total_sap_float is None:
                try:
                    root_cells = app_iframe.get_by_role("gridcell", name=re.compile(r"N.vel 0|Total|Totals", re.I)).all()
                    for rc in root_cells:
                        if rc.is_visible():
                            txt_rc = rc.inner_text().strip()
                            # Procurar valor numérico no texto da gridcell pai
                            nums = re.findall(r"[\d\.]+,[\d]{2}", txt_rc)
                            if nums:
                                total_sap_str = nums[-1]
                                total_sap_float = float(total_sap_str.replace(".", "").replace(",", "."))
                                break
                except Exception:
                    pass

            # Tenta 2: span de total no rodapé da tabela de custos
            if total_sap_float is None:
                try:
                    footer_spans = app_iframe.locator(
                        "span[title*='Total'], tfoot span, tr.lsTableFooter span, "
                        "span.lsDataTable__totalRow"
                    ).all()
                    for sp in footer_spans:
                        if sp.is_visible():
                            txt_sp = sp.inner_text().strip()
                            nums = re.findall(r"[\d\.]+,[\d]{2}", txt_sp)
                            if nums:
                                total_sap_str = nums[-1]
                                total_sap_float = float(total_sap_str.replace(".", "").replace(",", "."))
                                break
                except Exception:
                    pass

            # Tenta 3: varrer o body em busca de um valor igual à soma esperada
            if total_sap_float is None:
                try:
                    esperado_fmt = f"{soma_esperada:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    if esperado_fmt in (body_text or ""):
                        total_sap_float = soma_esperada
                        total_sap_str = esperado_fmt
                        log_console(f"  ℹ️ Total esperado '{esperado_fmt}' encontrado no corpo da página.")
                except Exception:
                    pass

            # Montar resultado da verificação
            esperado_fmt = f"{soma_esperada:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            if total_sap_float is not None:
                diferenca = abs(total_sap_float - soma_esperada)
                if diferenca < 0.02:  # tolerância de 2 centavos para arredondamento
                    log_console(f"  ✅ TOTAL OK: SAP={total_sap_str} | Esperado={esperado_fmt}")
                    resultado["verificacao_total"] = {
                        "ok": True,
                        "sap": total_sap_str,
                        "esperado": esperado_fmt,
                        "diferenca": round(diferenca, 2),
                    }
                else:
                    log_console(f"  ❌ DIVERGÊNCIA: SAP={total_sap_str} | Esperado={esperado_fmt} | Diferença={diferenca:.2f}")
                    resultado["verificacao_total"] = {
                        "ok": False,
                        "sap": total_sap_str,
                        "esperado": esperado_fmt,
                        "diferenca": round(diferenca, 2),
                    }
            else:
                log_console(f"  ⚠️ Não foi possível ler o total do SAP. Esperado: {esperado_fmt}")
                resultado["verificacao_total"] = {
                    "ok": None,
                    "sap": None,
                    "esperado": esperado_fmt,
                    "diferenca": None,
                }
        except Exception as e_verif:
            log_console(f"  ⚠️ Erro na verificação do total: {e_verif}")

        # Screenshot de confirmação
        try:
            page.screenshot(path="custo_of_editado.png")
            log_console("📸 Captura de tela salva como 'custo_of_editado.png'.")
        except Exception:
            pass

        if salvar:
            log_console("💾 Salvando Ordem de Frete no SAP (Ctrl+S)...")
            try:
                page.keyboard.press("Control+s")
                time.sleep(2)
            except Exception:
                pass
        else:
            log_console("⚠️ MODO DE TESTE (SEM SALVAR) - Alteração feita apenas na sessão visual do navegador.")

        if not headless and tempo_espera_visual > 0:
            log_console(f"👀 MANTENDO O NAVEGADOR ABERTO por {tempo_espera_visual}s para você conferir na tela...")
            time.sleep(tempo_espera_visual)

        return resultado

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

if __name__ == "__main__":
    of = sys.argv[1] if len(sys.argv) > 1 else "6100325111"
    val = sys.argv[2] if len(sys.argv) > 2 else "999,99"
    # 3º arg: texto para buscar a linha (ex: "CAMIL") ou número da linha
    arg3 = sys.argv[3] if len(sys.argv) > 3 else "1"
    texto = ""
    linha = 1
    try:
        linha = int(arg3)
    except ValueError:
        texto = arg3

    res = consultar_e_editar_custos_of(
        of_numero=of, novo_valor_teste=val, texto_linha=texto,
        linha_editar=linha, salvar=False, headless=False, tempo_espera_visual=30
    )
    print("\n" + "="*60, flush=True)
    print("RESULTADO DO TESTE:", flush=True)
    print(f"OF: {res['of_numero']}", flush=True)
    print(f"Linha editada: {res.get('linha_editada', '?')}", flush=True)
    print(f"Edição efetuada: {res['edicao_sucesso']}", flush=True)
    print(f"Valor preenchido: {res['valor_editado']}", flush=True)
    print(f"Linhas lidas: {len(res['linhas_extraidas'])}", flush=True)
    print("="*60, flush=True)
