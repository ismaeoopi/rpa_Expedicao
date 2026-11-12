"""
Módulo para automação de Estorno de Ordem de Frete (OF) no SAP Fiori / Web Dynpro via Playwright.

Passos do fluxo:
1. Acessa a Ordem de Frete (FreightOrder-changeRoad com idioma EN).
2. Acessa a aba Fluxo de Documentos (Document Flow).
3. Aciona a busca (Search / Ctrl+F) e pesquisa o Documento de Compras (PO).
4. Localiza o Documento de Liquidação de Frete (iniciado em 81) associado.
5. Clica no link do documento 81 abrindo nova aba/janela (FSD).
6. Na nova aba, verifica se o botão Edit está ativo e clica para habilitar edição.
7. Clica em 'Cancel Document' e confirma no diálogo com 'OK'.
8. Valida mensagem de êxito 'Data saved successfully'.
9. Alterna para Detailed View, acessa a aba Application Log e extrai os logs e severidade (Red LED / stop / errors).
10. Fecha a aba do FSD, volta para a Ordem de Frete, clica em Refresh e valida se a coluna
    'Business Document Life Cycle' está como 'Cancellation Requested'.
11. Atualiza a planilha de controle (aba Estornos) com todos os detalhes do processamento.
"""

import os
import sys
import time
import re
from datetime import datetime
from dotenv import load_dotenv

# Garantir raiz no sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.utils.common import log_sys
from src.expedicao.sap_packlist import _garantir_playwright_instalado

SAP_CHANGE_FO_URL_EN = (
    "https://appprod.sap.valgroupco.com/sap/bc/ui2/flp?sap-client=200&sap-language=EN#FreightOrder-changeRoad?sap-ui-tech-hint=WDA"
)


def log_console(msg: str):
    """Registra mensagem no console com timestamp e no log_sys."""
    log_line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(log_line, flush=True)
    try:
        log_sys.write(msg, echo=False)
    except Exception:
        try:
            log_sys.write(msg)
        except Exception:
            pass


def aguardar_fim_carregamento_sap(app_iframe, timeout: int = 35000) -> None:
    """Aguarda o overlay de carregamento do SAP Dynpro desaparecer."""
    time.sleep(1)
    loading_selectors = ["#ur-loading-box", "#ur-loading-itm2", "div[id*='loading-box']"]
    for selector in loading_selectors:
        try:
            loader = app_iframe.locator(selector)
            if loader.count() > 0 and loader.first.is_visible():
                loader.first.wait_for(state="hidden", timeout=timeout)
        except Exception:
            pass


def obter_app_iframe(target_page):
    """
    Retorna o content_frame da aplicação SAP Web Dynpro de forma resiliente.
    """
    candidatos = [
        'iframe[name="__container1-iframe"]',
        'iframe[title="Application"]',
        'iframe[title="Aplicação"]',
        'iframe[id*="container"]',
        'iframe',
    ]
    for sel in candidatos:
        try:
            el = target_page.locator(sel)
            if el.count() > 0:
                frame = el.first.content_frame
                if frame:
                    return frame
        except Exception:
            pass
    return target_page.main_frame


def fazer_login_sap(page, usuario: str, senha: str) -> None:
    """Realiza login no SAP Fiori caso a tela de autenticação esteja presente."""
    log_console("🔐 Verificando tela de login do SAP Fiori...")
    try:
        user_field = page.get_by_role("textbox", name=re.compile(r"^(User|Usuário)", re.I))
        if user_field.first.is_visible(timeout=5000):
            log_console("🔐 Efetuando Login...")
            if page.get_by_role("textbox", name="User").is_visible():
                page.get_by_role("textbox", name="User").fill(usuario)
                time.sleep(0.5)
                page.get_by_role("textbox", name="Password").fill(senha)
                page.get_by_role("button", name="Log On").click()
            else:
                page.get_by_role("textbox", name="Usuário").fill(usuario)
                time.sleep(0.5)
                page.get_by_role("textbox", name="Senha").fill(senha)
                page.get_by_role("button", name="Logon").click()
            time.sleep(2)
    except Exception:
        pass


def localizar_documento_81(app_iframe, doc_compras: str) -> str:
    """
    Localiza o número do documento FSD (iniciado com 81, com 10 dígitos)
    associado ao Documento de Compras pesquisado na árvore do Document Flow.
    Geralmente fica 1 ou 2 linhas acima do nó do documento de compras.
    """
    doc_compras = str(doc_compras).strip()
    log_console(f"🔍 Localizando documento de liquidação (81...) para PO: {doc_compras}...")

    # 1. Estratégia DOM: busca na hierarquia da tabela Web Dynpro
    try:
        script = """
        (poNumber) => {
            const regex81 = /\\b(81\\d{8})\\b/;
            
            // Todos os links 81 visíveis
            const allLinks81 = Array.from(document.querySelectorAll('a')).filter(a => {
                const txt = (a.innerText || a.textContent || '').trim();
                return /^81\\d{8}$/.test(txt);
            });
            
            if (allLinks81.length === 1) {
                return allLinks81[0].innerText.trim();
            }
            
            // Localizar elemento contendo o PO
            const elements = Array.from(document.querySelectorAll('*')).filter(el => {
                const t = (el.innerText || el.textContent || '').trim();
                return t === poNumber;
            });
            
            if (elements.length > 0) {
                const targetEl = elements[0];
                let row = targetEl.closest('tr, [id*="-mrss-cont-none-Row-"], [role="row"]');
                if (row) {
                    // Percorre as linhas irmãs anteriores (subindo 1 a 5 níveis)
                    let prev = row.previousElementSibling;
                    let steps = 0;
                    while (prev && steps < 6) {
                        const m = (prev.innerText || prev.textContent || '').match(regex81);
                        if (m) {
                            return m[1];
                        }
                        prev = prev.previousElementSibling;
                        steps++;
                    }
                }
            }
            
            if (allLinks81.length > 0) {
                return allLinks81[0].innerText.trim();
            }
            return null;
        }
        """
        resultado = app_iframe.evaluate(script, doc_compras)
        if resultado:
            log_console(f"  ✅ Documento 81 identificado via DOM: {resultado}")
            return str(resultado).strip()
    except Exception as e:
        log_console(f"  ⚠️ Aviso na busca DOM do documento 81: {e}")

    # 2. Estratégia de Fallback: links na página
    try:
        links = app_iframe.get_by_role("link").all()
        for lnk in links:
            txt = (lnk.inner_text() or "").strip()
            if re.match(r"^81\d{8}$", txt):
                log_console(f"  ✅ Documento 81 encontrado via role link: {txt}")
                return txt
    except Exception:
        pass

    # 3. Estratégia de Fallback: regex no body
    try:
        body_text = app_iframe.locator("body").inner_text()
        matches = re.findall(r"\b81\d{8}\b", body_text)
        if matches:
            log_console(f"  ✅ Documento 81 encontrado via regex no body: {matches[0]}")
            return matches[0]
    except Exception:
        pass

    log_console(f"  ❌ Não foi possível localizar o documento 81 para PO: {doc_compras}")
    return ""


def extrair_logs_aplicacao_fsd(app_iframe1) -> dict:
    """
    Alterna para Detailed View (se necessário), clica na aba Application Log
    e extrai os textos de mensagem e a severidade (Red LED / Stop / Errors, Warning, Success).
    """
    resultado_logs = {
        "logs": [],
        "severidade_geral": "Sem Logs",
        "tem_erro": False,
        "mensagem_resumo": "",
    }

    log_console("📋 Acessando logs da aplicação no FSD...")

    # 1. Tentar alternar para Detailed View
    try:
        detailed_opt = app_iframe1.get_by_role("option", name=re.compile(r"Detailed View|Visão detalhada", re.I))
        if detailed_opt.count() > 0 and detailed_opt.first.is_visible():
            detailed_opt.first.click(timeout=5000)
            aguardar_fim_carregamento_sap(app_iframe1, timeout=15000)
            time.sleep(1)
        else:
            view_switcher = app_iframe1.locator("[title*='Detailed View'], [title*='Visão detalhada'], [title*='View'], div[role='combobox']")
            if view_switcher.count() > 0 and view_switcher.first.is_visible():
                view_switcher.first.click(timeout=3000)
                time.sleep(0.5)
                opt = app_iframe1.get_by_role("option", name=re.compile(r"Detailed View", re.I))
                if opt.count() > 0:
                    opt.first.click(timeout=3000)
                    aguardar_fim_carregamento_sap(app_iframe1, timeout=15000)
                    time.sleep(1)
    except Exception as e_view:
        log_console(f"  ℹ️ Detalhe da troca para Detailed View: {e_view}")

    # 2. Clicar na aba Application Log
    clicou_tab = False
    try:
        tab_app_log = app_iframe1.get_by_role("tab", name=re.compile(r"Application Log|Log de aplicação", re.I))
        if tab_app_log.count() > 0 and tab_app_log.first.is_visible():
            tab_app_log.first.click(timeout=6000)
            clicou_tab = True
        else:
            tab_txt = app_iframe1.get_by_text(re.compile(r"Application Log|Log de aplicação", re.I))
            if tab_txt.count() > 0 and tab_txt.first.is_visible():
                tab_txt.first.click(timeout=6000)
                clicou_tab = True
        if clicou_tab:
            aguardar_fim_carregamento_sap(app_iframe1, timeout=20000)
            time.sleep(2)
    except Exception as e_tab:
        log_console(f"  ⚠️ Aviso ao clicar na aba Application Log: {e_tab}")

    # 3. Extrair linhas da tabela de logs
    logs_coletados = []
    severidade_geral = "OK"
    tem_erro = False

    try:
        # Script via evaluate para extrair diretamente o texto das colunas e alt/title/name de LEDs
        script_extract = """
        () => {
            const rows = Array.from(document.querySelectorAll('tr, [id*="-mrss-cont-none-Row-"], [role="row"]'));
            const data = [];
            for (const r of rows) {
                const text = (r.innerText || r.textContent || '').trim();
                if (!text || text.includes('Message text') || text.includes('Texto da mensagem')) {
                    continue;
                }
                let sev = 'Info';
                const imgs = Array.from(r.querySelectorAll('img'));
                for (const img of imgs) {
                    const desc = (img.getAttribute('name') || img.getAttribute('title') || img.getAttribute('alt') || img.getAttribute('aria-label') || '').toLowerCase();
                    if (desc.includes('red') || desc.includes('error') || desc.includes('stop') || desc.includes('erro')) {
                        sev = 'Error';
                        break;
                    } else if (desc.includes('yellow') || desc.includes('warning') || desc.includes('aviso')) {
                        sev = 'Warning';
                        break;
                    } else if (desc.includes('green') || desc.includes('success') || desc.includes('êxito')) {
                        sev = 'Success';
                        break;
                    }
                }
                data.push({ severity: sev, text: text.replace(/\\s+/g, ' ') });
            }
            return data;
        }
        """
        log_items = app_iframe1.evaluate(script_extract)
        if log_items and isinstance(log_items, list):
            for item in log_items:
                sev = item.get("severity", "Info")
                txt = item.get("text", "")
                if txt:
                    logs_coletados.append(f"[{sev}] {txt}")
                    if sev == "Error":
                        tem_erro = True
                        severidade_geral = "Red LED / Error"
                    elif sev == "Warning" and severidade_geral != "Red LED / Error":
                        severidade_geral = "Yellow LED / Warning"
                    elif sev == "Success" and severidade_geral == "OK":
                        severidade_geral = "Green LED / Success"
    except Exception as e_ext:
        log_console(f"  ⚠️ Aviso na extração de logs: {e_ext}")

    resultado_logs["logs"] = logs_coletados
    resultado_logs["severidade_geral"] = severidade_geral if logs_coletados else "Sem Logs"
    resultado_logs["tem_erro"] = tem_erro
    resultado_logs["mensagem_resumo"] = " | ".join(logs_coletados[:5]) if logs_coletados else ""

    if logs_coletados:
        log_console(f"  📄 Logs extraídos ({len(logs_coletados)} registros): {resultado_logs['mensagem_resumo']}")
    else:
        log_console("  ℹ️ Nenhum registro encontrado na aba Application Log.")

    return resultado_logs


def estornar_fsd_popup(page1, doc_81: str) -> dict:
    """
    Executa os passos de cancelamento do documento FSD (81...) na janela popup (page1):
    - Verifica/ativa botão Edit
    - Clica em Cancel Document
    - Confirma com OK Emphasized
    - Valida 'Data saved successfully'
    - Extrai Application Log e severidade
    - Fecha a janela popup
    """
    resultado = {
        "doc_81": doc_81,
        "edit_clicado": False,
        "cancel_clicado": False,
        "ok_clicado": False,
        "sucesso_salvar": False,
        "severidade": "Não avaliado",
        "logs_resumo": "",
        "erro_fsd": "",
    }

    log_console(f"🚀 Iniciando processamento do FSD {doc_81} na nova aba...")

    try:
        page1.wait_for_load_state("domcontentloaded", timeout=30000)
    except Exception:
        pass

    time.sleep(2)
    app_iframe1 = obter_app_iframe(page1)
    aguardar_fim_carregamento_sap(app_iframe1, timeout=35000)

    # 1. Verificar botão Edit
    log_console("✏️ Verificando botão Edit no FSD...")
    try:
        btn_edit = app_iframe1.get_by_role("button", name=re.compile(r"^Edit$|^Processar$|^Modificar$", re.I)).first
        if btn_edit.count() > 0 and btn_edit.is_visible():
            aria_dis = (btn_edit.get_attribute("aria-disabled") or "").lower()
            cls_str = (btn_edit.get_attribute("class") or "").lower()
            if aria_dis != "true" and "disabled" not in cls_str and "urbtnstddsbl" not in cls_str:
                log_console("  ✏️ Clicando em 'Edit' para habilitar modificação...")
                btn_edit.click()
                resultado["edit_clicado"] = True
                aguardar_fim_carregamento_sap(app_iframe1, timeout=20000)
                time.sleep(1.5)
            else:
                log_console("  ℹ️ Botão Edit desativado (FSD já está em modo de edição).")
        else:
            log_console("  ℹ️ Botão Edit não visível ou documento já em edição.")
    except Exception as e_edit:
        log_console(f"  ⚠️ Erro ao checar botão Edit: {e_edit}")

    # 2. Clicar em Cancel Document
    log_console("🚫 Clicando em 'Cancel Document'...")
    try:
        btn_cancel = app_iframe1.get_by_role("button", name=re.compile(r"Cancel Document|Cancelar documento", re.I)).first
        if btn_cancel.count() == 0:
            btn_cancel = app_iframe1.locator("[title*='Cancel Document'], [title*='Cancelar documento']").first

        btn_cancel.wait_for(state="visible", timeout=20000)
        btn_cancel.click()
        resultado["cancel_clicado"] = True
        log_console("  ✅ Botão 'Cancel Document' clicado com sucesso.")
        time.sleep(1.5)
    except Exception as e_cancel:
        err_msg = f"Falha ao clicar em 'Cancel Document': {e_cancel}"
        log_console(f"  ❌ {err_msg}")
        resultado["erro_fsd"] = err_msg
        try:
            page1.close()
        except Exception:
            pass
        return resultado

    # 3. Confirmar caixa de diálogo (OK / OK Emphasized)
    log_console("⚠️ Confirmando cancelamento na caixa de diálogo (OK)...")
    try:
        btn_ok = app_iframe1.get_by_role("button", name=re.compile(r"OK.*Emphasized|OK", re.I)).first
        if btn_ok.count() == 0:
            btn_ok = app_iframe1.locator("button:has-text('OK'), div[role='button']:has-text('OK')").first

        btn_ok.wait_for(state="visible", timeout=15000)
        btn_ok.click()
        resultado["ok_clicado"] = True
        log_console("  ✅ Confirmação 'OK' clicada.")
        aguardar_fim_carregamento_sap(app_iframe1, timeout=35000)
        time.sleep(2)
    except Exception as e_ok:
        log_console(f"  ⚠️ Aviso ao confirmar OK: {e_ok}")

    # 4. Validar mensagem de sucesso: Data saved successfully
    try:
        msg_saved = app_iframe1.get_by_text(re.compile(r"Data saved successfully|Dados gravados com êxito|Data saved", re.I))
        if msg_saved.count() > 0 and msg_saved.first.is_visible():
            resultado["sucesso_salvar"] = True
            log_console("  ✅ Mensagem SAP confirmada: Data saved successfully!")
        else:
            # Checar mensagens em listitem
            list_item = app_iframe1.locator('[role="listitem"]').filter(has_text=re.compile(r"Data saved|gravados", re.I))
            if list_item.count() > 0:
                resultado["sucesso_salvar"] = True
                log_console("  ✅ Mensagem SAP confirmada via listitem!")
    except Exception as e_msg:
        log_console(f"  ℹ️ Checagem de mensagem salva: {e_msg}")

    # 5. Extrair Application Log e Severidade
    info_logs = extrair_logs_aplicacao_fsd(app_iframe1)
    resultado["severidade"] = info_logs.get("severidade_geral", "Sem Logs")
    resultado["logs_resumo"] = info_logs.get("mensagem_resumo", "")

    # 6. Fechar aba do FSD
    log_console("🚪 Fechando aba do FSD...")
    try:
        page1.close()
    except Exception:
        pass

    return resultado


def processar_estorno_of_na_pagina(
    page,
    of_numero: str,
    doc_compras: str,
) -> dict:
    """
    Executa o estorno completo de uma Ordem de Frete (OF) em uma página já aberta.
    Retorna dicionário estruturado com o resultado.
    """
    of_numero = str(of_numero).strip()
    doc_compras = str(doc_compras).strip()

    resultado = {
        "of_numero": of_numero,
        "doc_compras": doc_compras,
        "doc_81": "",
        "status_estorno": "Pendente",
        "life_cycle_status": "",
        "severidade": "",
        "logs": "",
        "sucesso": False,
        "mensagem": "",
    }

    log_console(f"\n{'='*60}")
    log_console(f"🎯 Iniciando Estorno da OF: {of_numero} | PO: {doc_compras}")
    log_console(f"{'='*60}")

    app_iframe = obter_app_iframe(page)
    aguardar_fim_carregamento_sap(app_iframe, timeout=30000)

    # 1. Preencher campo Ordem de Frete (Freight Order Required)
    log_console(f"📝 Localizando campo de entrada da Ordem de Frete...")
    input_of = None
    candidatos_of = [
        lambda: app_iframe.get_by_role("textbox", name=re.compile(r"Freight Order Required|Ordem de frete", re.I)).first,
        lambda: app_iframe.get_by_role("textbox", name=re.compile(r"Freight Order", re.I)).first,
        lambda: app_iframe.locator("input[title*='Freight Order'], input[title*='Ordem de frete']").first,
    ]

    for cand in candidatos_of:
        try:
            loc = cand()
            if loc.count() > 0 and loc.is_visible():
                input_of = loc
                break
        except Exception:
            pass

    if not input_of:
        # Se já estivermos dentro de uma OF anterior, fechar para voltar à tela inicial
        try:
            btn_close_exist = app_iframe.get_by_role("button", name=re.compile(r"^Close$|^Fechar$", re.I)).first
            if btn_close_exist.count() > 0 and btn_close_exist.is_visible():
                log_console("ℹ️ OF anterior aberta. Clicando em Close para retornar...")
                btn_close_exist.click()
                time.sleep(2)
                aguardar_fim_carregamento_sap(app_iframe, timeout=15000)
        except Exception:
            pass

        # Tentar recarregar a URL se ainda não encontrou o campo
        try:
            page.goto(SAP_CHANGE_FO_URL_EN, timeout=45000)
            time.sleep(3)
            app_iframe = obter_app_iframe(page)
            aguardar_fim_carregamento_sap(app_iframe, timeout=30000)
            input_of = app_iframe.get_by_role("textbox", name=re.compile(r"Freight Order", re.I)).first
        except Exception:
            pass

    if not input_of or input_of.count() == 0:
        err = f"Campo 'Freight Order' não encontrado para carregar a OF {of_numero}."
        log_console(f"❌ {err}")
        resultado["status_estorno"] = "Erro"
        resultado["mensagem"] = err
        return resultado

    input_of.click()
    input_of.fill(of_numero)
    time.sleep(0.5)

    # Clicar em Continue Emphasized ou pressionar Enter
    try:
        btn_continue = app_iframe.get_by_role("button", name=re.compile(r"Continue.*Emphasized|Continue|Continuar", re.I)).first
        if btn_continue.count() > 0 and btn_continue.is_visible():
            btn_continue.click()
        else:
            input_of.press("Enter")
    except Exception:
        input_of.press("Enter")

    log_console(f"⏳ Aguardando carregamento da OF {of_numero}...")
    aguardar_fim_carregamento_sap(app_iframe, timeout=40000)
    time.sleep(3)

    # 2. Acessar aba Document Flow (Fluxo de Documentos)
    log_console("📂 Navegando para a aba 'Document Flow'...")
    try:
        tab_doc_flow = app_iframe.get_by_role("tab", name=re.compile(r"Document Flow|Fluxo de documentos", re.I)).first
        if tab_doc_flow.count() > 0:
            tab_doc_flow.click(timeout=10000)
        else:
            app_iframe.get_by_text(re.compile(r"Document Flow|Fluxo de documentos", re.I)).first.click(timeout=8000)
        aguardar_fim_carregamento_sap(app_iframe, timeout=20000)
        time.sleep(2)
        log_console("  ✅ Aba 'Document Flow' selecionada.")
    except Exception as e_tab:
        log_console(f"  ⚠️ Aviso ao selecionar aba Document Flow: {e_tab}")

    # 3. Pesquisar o Documento de Compras (PO) na lupa
    log_console(f"🔎 Pesquisando Documento de Compras: {doc_compras}...")
    try:
        btn_search = app_iframe.get_by_role("button", name=re.compile(r"Search \(Ctrl\+F\)|Procurar|Pesquisar", re.I)).first
        if btn_search.count() == 0:
            btn_search = app_iframe.locator("[title*='Search (Ctrl+F)'], [title*='Procurar']").first

        if btn_search.count() > 0 and btn_search.is_visible():
            btn_search.click(timeout=5000)
        else:
            page.keyboard.press("Control+f")
        time.sleep(1)

        # Preencher campo Search for
        search_box = app_iframe.get_by_role("textbox", name=re.compile(r"Search for|Pesquisar por", re.I)).first
        if search_box.count() == 0:
            search_box = app_iframe.locator("input[title*='Search for'], input[title*='Pesquisar por']").first

        search_box.wait_for(state="visible", timeout=10000)
        search_box.click()
        search_box.fill(doc_compras)
        time.sleep(0.5)

        # Clicar no botão de busca da caixa ou dar Enter
        btn_exec_search = app_iframe.locator("#WD0334-btn")
        if btn_exec_search.count() > 0 and btn_exec_search.first.is_visible():
            btn_exec_search.first.click()
        else:
            search_box.press("Enter")

        aguardar_fim_carregamento_sap(app_iframe, timeout=15000)
        time.sleep(2)
        log_console(f"  ✅ Pesquisa por '{doc_compras}' executada.")
    except Exception as e_search:
        log_console(f"  ⚠️ Aviso na pesquisa de PO: {e_search}")

    # 4. Localizar Documento 81...
    doc_81 = localizar_documento_81(app_iframe, doc_compras)
    resultado["doc_81"] = doc_81

    if not doc_81:
        err = f"Documento de liquidação (81...) não encontrado para PO {doc_compras} na OF {of_numero}."
        log_console(f"❌ {err}")
        resultado["status_estorno"] = "Erro"
        resultado["mensagem"] = err

        # Fechar a OF para a próxima
        try:
            btn_close = app_iframe.get_by_role("button", name=re.compile(r"^Close$|^Fechar$", re.I)).first
            if btn_close.count() > 0 and btn_close.is_visible():
                btn_close.click()
                time.sleep(2)
        except Exception:
            pass
        return resultado

    # 5. Clicar no documento 81 abrindo popup
    log_console(f"🌐 Clicando no link do documento {doc_81} para abrir o FSD...")
    page1 = None
    try:
        with page.expect_popup(timeout=25000) as page1_info:
            link_81 = app_iframe.get_by_role("link", name=doc_81).first
            if link_81.count() == 0:
                link_81 = app_iframe.locator(f"a:has-text('{doc_81}')").first
            link_81.click()
        page1 = page1_info.value
    except Exception as e_pop:
        log_console(f"  ⚠️ Timeout no expect_popup. Verificando páginas do contexto: {e_pop}")
        for p in page.context.pages:
            if p != page and not p.is_closed():
                page1 = p
                break

    if not page1:
        err = f"A aba do documento {doc_81} não foi aberta."
        log_console(f"❌ {err}")
        resultado["status_estorno"] = "Erro"
        resultado["mensagem"] = err
        return resultado

    # 6. Processar estorno no FSD (page1)
    res_fsd = estornar_fsd_popup(page1, doc_81)
    resultado["severidade"] = res_fsd.get("severidade", "")
    resultado["logs"] = res_fsd.get("logs_resumo", "")

    # 7. Voltar para a Ordem de Frete (page), clicar em Refresh e validar status
    log_console("🔄 Atualizando tela da Ordem de Frete (Refresh)...")
    app_iframe = obter_app_iframe(page)
    try:
        btn_refresh = app_iframe.get_by_role("button", name=re.compile(r"^Refresh$|^Atualizar$", re.I)).first
        if btn_refresh.count() > 0 and btn_refresh.is_visible():
            btn_refresh.click()
            aguardar_fim_carregamento_sap(app_iframe, timeout=25000)
            time.sleep(3)
            log_console("  ✅ Ordem de Frete atualizada.")
    except Exception as e_ref:
        log_console(f"  ⚠️ Aviso ao clicar em Refresh: {e_ref}")

    # Verificar se o status agora é 'Cancellation Requested'
    log_console("🔎 Verificando se status é 'Cancellation Requested'...")
    status_encontrado = ""
    try:
        cand_status = app_iframe.get_by_text(re.compile(r"Cancellation Requested|Cancelamento solicitado", re.I))
        if cand_status.count() > 0 and cand_status.first.is_visible():
            status_encontrado = "Cancellation Requested"
            log_console("  ✅ Status confirmado: Cancellation Requested!")
        else:
            # Checar body text
            b_txt = app_iframe.locator("body").inner_text()
            if "Cancellation Requested" in b_txt or "Cancelamento solicitado" in b_txt:
                status_encontrado = "Cancellation Requested"
                log_console("  ✅ Status confirmado no body da OF: Cancellation Requested!")
    except Exception as e_stat:
        log_console(f"  ℹ️ Checagem de status Life Cycle: {e_stat}")

    resultado["life_cycle_status"] = status_encontrado or "Não confirmado"

    # Avaliar sucesso
    if status_encontrado == "Cancellation Requested" or res_fsd.get("sucesso_salvar"):
        resultado["sucesso"] = True
        resultado["status_estorno"] = "Sucesso"
        resultado["mensagem"] = f"Estorno solicitado com sucesso para FSD {doc_81}."
        log_console(f"🎉 OF {of_numero} ESTORNADA COM SUCESSO! Status: Cancellation Requested.")
    else:
        resultado["sucesso"] = False
        resultado["status_estorno"] = "Atenção / Verificar"
        resultado["mensagem"] = res_fsd.get("erro_fsd") or "Status Cancellation Requested não pôde ser confirmado."
        log_console(f"⚠️ OF {of_numero} processada com pendência. Mensagem: {resultado['mensagem']}")

    # 8. Fechar a Ordem de Frete para liberar sessão para a próxima
    try:
        btn_close = app_iframe.get_by_role("button", name=re.compile(r"^Close$|^Fechar$", re.I)).first
        if btn_close.count() == 0:
            btn_close = page.get_by_role("button", name="Close").first
        if btn_close.count() > 0 and btn_close.is_visible():
            btn_close.click()
            time.sleep(2)
            aguardar_fim_carregamento_sap(app_iframe, timeout=15000)
    except Exception:
        pass

    return resultado


def carregar_dados_estorno_planilha(caminho_excel: str) -> list:
    """
    Carrega os dados de estorno a partir de uma planilha Excel.
    Se a aba 'Estornos ' (ou 'Estornos') existir, lê as OFs dela e busca o
    'Documento de compras' correspondente na aba 'Base'.
    Se a aba 'Base' existir diretamente, pode também ler os pares (Ordem, Documento de compras).
    Retorna lista de dicionários: [{'of_numero': '...', 'doc_compras': '...', ...}, ...]
    """
    if not os.path.isfile(caminho_excel):
        raise FileNotFoundError(f"Arquivo Excel não encontrado: {caminho_excel}")

    import openpyxl

    wb = openpyxl.load_workbook(caminho_excel, data_only=True)
    itens = []

    # 1. Mapear Documento de Compras da aba Base: {OF: doc_compras}
    doc_compras_map = {}
    if "Base" in wb.sheetnames:
        ws_base = wb["Base"]
        # Procurar linha de cabeçalho (normalmente linha 3)
        header_row_idx = None
        ordem_idx = None
        doc_comp_idx = None

        for r_idx in range(1, 10):
            row_vals = [c.value for c in ws_base[r_idx]]
            vals_str = [str(v).strip().lower() if v is not None else "" for v in row_vals]
            if any("ordem" in v or "of" in v for v in vals_str) and any("compras" in v for v in vals_str):
                header_row_idx = r_idx
                for col_idx, v in enumerate(vals_str):
                    if v == "ordem" or (("ordem" in v or "of" in v) and "chave" not in v):
                        if ordem_idx is None:
                            ordem_idx = col_idx
                    if "compras" in v or "documento de compras" in v:
                        if doc_comp_idx is None:
                            doc_comp_idx = col_idx
                break

        if header_row_idx and ordem_idx is not None and doc_comp_idx is not None:
            for row in ws_base.iter_rows(min_row=header_row_idx + 1, values_only=True):
                if len(row) > max(ordem_idx, doc_comp_idx):
                    of_v = row[ordem_idx]
                    doc_v = row[doc_comp_idx]
                    if of_v and doc_v:
                        of_str = str(of_v).strip().replace(".0", "")
                        doc_str = str(doc_v).strip().replace(".0", "")
                        if of_str and doc_str and of_str not in doc_compras_map:
                            doc_compras_map[of_str] = doc_str

    # 2. Localizar aba de estornos (ex: 'Estornos ', 'Estornos', 'Estorno')
    estorno_sheet_name = None
    for name in wb.sheetnames:
        if "estorno" in name.strip().lower():
            estorno_sheet_name = name
            break

    if estorno_sheet_name:
        ws_est = wb[estorno_sheet_name]
        # Ler linhas a partir da 2ª linha
        for row in ws_est.iter_rows(min_row=2, values_only=True):
            if not row or not row[0]:
                continue
            of_val = str(row[0]).strip().replace(".0", "")
            if not of_val or of_val.lower() in ["of", "ordem", "none"]:
                continue

            # Verificar se já veio doc_compras na coluna 2 ou se pegamos do mapa da Base
            doc_comp = ""
            if len(row) > 2 and row[2] and str(row[2]).strip().isdigit():
                doc_comp = str(row[2]).strip().replace(".0", "")
            if not doc_comp:
                doc_comp = doc_compras_map.get(of_val, "")

            itens.append({
                "of_numero": of_val,
                "doc_compras": doc_comp,
                "status_anterior": str(row[1]) if len(row) > 1 and row[1] is not None else "",
                "origem": estorno_sheet_name,
            })

    # 3. Fallback: Se não havia aba de Estornos com itens, extrair da Base
    if not itens and doc_compras_map:
        for of_val, doc_val in doc_compras_map.items():
            itens.append({
                "of_numero": of_val,
                "doc_compras": doc_val,
                "status_anterior": "",
                "origem": "Base",
            })

    return itens


def atualizar_planilha_estorno(caminho_excel: str, resultados: list) -> str:
    """
    Grava os resultados do estorno na aba 'Estornos ' do arquivo Excel.
    Se a aba não existir, ela é criada com formatação limpa e profissional.
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    if not os.path.isfile(caminho_excel):
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_excel}")

    wb = openpyxl.load_workbook(caminho_excel)

    # Localizar ou criar aba 'Estornos '
    sheet_name = "Estornos "
    for name in wb.sheetnames:
        if "estorno" in name.strip().lower():
            sheet_name = name
            break

    if sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
    else:
        ws = wb.create_sheet(title="Estornos ")

    # Cabeçalhos detalhados e profissionais
    headers = [
        "OF",
        "Status Estorno",
        "Documento de compras",
        "Doc 81 (FSD)",
        "Life Cycle Status",
        "Severidade",
        "Mensagens do Log",
        "Data/Hora Processamento",
    ]

    header_fill = PatternFill(start_color="1A7733", end_color="1A7733", fill_type="solid")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")

    thin_border = Border(
        left=Side(style='thin', color='DDDDDD'),
        right=Side(style='thin', color='DDDDDD'),
        top=Side(style='thin', color='DDDDDD'),
        bottom=Side(style='thin', color='DDDDDD')
    )

    # Aplicar cabeçalhos na linha 1 se vazia ou desatualizada
    primeira_linha = [cell.value for cell in ws[1]]
    if not primeira_linha or not primeira_linha[0] or len(primeira_linha) < len(headers):
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = align_center

    # Indexar linhas existentes pelo número da OF
    linhas_of_map = {}
    for r_idx in range(2, ws.max_row + 1):
        v = ws.cell(row=r_idx, column=1).value
        if v:
            of_str = str(v).strip().replace(".0", "")
            linhas_of_map[of_str] = r_idx

    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    # Cores de status
    sucesso_fill = PatternFill(start_color="D4EDDA", end_color="D4EDDA", fill_type="solid")
    erro_fill = PatternFill(start_color="F8D7DA", end_color="F8D7DA", fill_type="solid")
    aviso_fill = PatternFill(start_color="FFF3CD", end_color="FFF3CD", fill_type="solid")

    for res in resultados:
        of_num = str(res.get("of_numero", "")).strip()
        if not of_num:
            continue

        if of_num in linhas_of_map:
            row_idx = linhas_of_map[of_num]
        else:
            row_idx = ws.max_row + 1
            linhas_of_map[of_num] = row_idx
            ws.cell(row=row_idx, column=1, value=of_num)

        status_txt = "Sucesso" if res.get("sucesso") else res.get("status_estorno", "Erro")
        doc_comp = res.get("doc_compras", "")
        doc_81 = res.get("doc_81", "")
        life_cycle = res.get("life_cycle_status", "")
        sev = res.get("severidade", "")
        logs_txt = res.get("logs", "") or res.get("mensagem", "")

        ws.cell(row=row_idx, column=1, value=of_num).alignment = align_center
        ws.cell(row=row_idx, column=2, value=status_txt).alignment = align_center
        ws.cell(row=row_idx, column=3, value=doc_comp).alignment = align_center
        ws.cell(row=row_idx, column=4, value=doc_81).alignment = align_center
        ws.cell(row=row_idx, column=5, value=life_cycle).alignment = align_center
        ws.cell(row=row_idx, column=6, value=sev).alignment = align_center
        ws.cell(row=row_idx, column=7, value=logs_txt).alignment = align_left
        ws.cell(row=row_idx, column=8, value=agora).alignment = align_center

        # Aplicar estilo de destaque na coluna de status
        cell_status = ws.cell(row=row_idx, column=2)
        if status_txt == "Sucesso":
            cell_status.fill = sucesso_fill
            cell_status.font = Font(name="Segoe UI", bold=True, color="155724")
        elif "Atenção" in status_txt or "Alerta" in status_txt:
            cell_status.fill = aviso_fill
            cell_status.font = Font(name="Segoe UI", bold=True, color="856404")
        else:
            cell_status.fill = erro_fill
            cell_status.font = Font(name="Segoe UI", bold=True, color="721C24")

        # Bordas
        for c in range(1, 9):
            ws.cell(row=row_idx, column=c).border = thin_border

    # Ajuste automático das larguras de coluna
    for col in ws.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            v_str = str(cell.value or "")
            if len(v_str) > max_len:
                max_len = len(v_str)
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 45)

    wb.save(caminho_excel)
    log_console(f"💾 Planilha atualizada com sucesso: {caminho_excel}")
    return caminho_excel


def executar_estorno_of_lote(
    itens: list,
    headless: bool = True,
    caminho_planilha: str = None,
    callback_progresso = None,
) -> list:
    """
    Executa o estorno de uma lista de OFs no SAP em lote,
    reutilizando a mesma sessão do navegador.
    """
    load_dotenv()
    usuario = os.getenv("SAP_WEB_USER")
    senha = os.getenv("SAP_WEB_PASSWORD")

    if not usuario or not senha:
        raise ValueError("Credenciais SAP_WEB_USER e SAP_WEB_PASSWORD não encontradas no arquivo .env")

    localappdata = os.environ.get("LOCALAPPDATA", "")
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(localappdata, "ms-playwright")

    if not _garantir_playwright_instalado():
        raise RuntimeError("Playwright/Chromium não está disponível.")

    from playwright.sync_api import sync_playwright

    resultados = []
    playwright_instance = None
    browser = None

    try:
        log_console(f"🚀 Iniciando automação de Estorno de OFs ({len(itens)} itens)...")
        playwright_instance = sync_playwright().start()
        browser = playwright_instance.chromium.launch(
            headless=headless,
            args=["--start-maximized"]
        )
        context = browser.new_context(no_viewport=True)
        page = context.new_page()

        log_console(f"🔐 Acessando SAP Fiori ({SAP_CHANGE_FO_URL_EN})...")
        page.goto(SAP_CHANGE_FO_URL_EN, timeout=60000)

        # Login único
        fazer_login_sap(page, usuario, senha)

        total = len(itens)
        for idx, item in enumerate(itens, 1):
            of_num = str(item.get("of_numero", "")).strip()
            doc_comp = str(item.get("doc_compras", "")).strip()

            log_console(f"\n[{idx}/{total}] Processando OF {of_num}...")

            if callback_progresso:
                try:
                    callback_progresso(idx, total, of_num, "processando")
                except Exception:
                    pass

            try:
                res = processar_estorno_of_na_pagina(page, of_num, doc_comp)
            except Exception as e_proc:
                err_msg = f"Exceção inesperada ao estornar OF {of_num}: {e_proc}"
                log_console(f"❌ {err_msg}")
                res = {
                    "of_numero": of_num,
                    "doc_compras": doc_comp,
                    "doc_81": "",
                    "status_estorno": "Erro",
                    "life_cycle_status": "Erro",
                    "severidade": "Error",
                    "logs": err_msg,
                    "sucesso": False,
                    "mensagem": err_msg,
                }
                # Tentar fechar abas filhas residuais
                for p in context.pages:
                    if p != page and not p.is_closed():
                        try:
                            p.close()
                        except Exception:
                            pass

            resultados.append(res)

            # Salvar progresso na planilha imediatamente a cada item
            if caminho_planilha and os.path.isfile(caminho_planilha):
                try:
                    atualizar_planilha_estorno(caminho_planilha, [res])
                except Exception as e_save:
                    log_console(f"⚠️ Erro ao salvar parcial na planilha: {e_save}")

            if callback_progresso:
                try:
                    st = "sucesso" if res.get("sucesso") else "erro"
                    callback_progresso(idx, total, of_num, st, res)
                except Exception:
                    pass

    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass
        if playwright_instance:
            try:
                playwright_instance.stop()
            except Exception:
                pass

    log_console(f"\n🏁 Processamento em lote concluído! {len(resultados)} OF(s) processada(s).")
    return resultados


def estornar_of_individual(
    of_numero: str,
    doc_compras: str,
    headless: bool = False,
    caminho_planilha: str = None,
) -> dict:
    """Executa o estorno de uma única Ordem de Frete."""
    item = [{"of_numero": of_numero, "doc_compras": doc_compras}]
    res_lista = executar_estorno_of_lote(item, headless=headless, caminho_planilha=caminho_planilha)
    return res_lista[0] if res_lista else {}

