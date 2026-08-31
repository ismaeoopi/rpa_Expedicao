import os
import sys
import time
import re
from dotenv import load_dotenv

# Adiciona o diretório raiz do projeto ao path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.utils.common import log_sys
from src.expedicao.sap_packlist import _garantir_playwright_instalado
from src.expedicao.sap_cabotagem_playwright import aguardar_fim_carregamento_sap

SAP_CHANGE_FO_URL = "https://appprod.sap.valgroupco.com/sap/bc/ui2/flp?sap-client=200&sap-language=PT#FreightOrder-changeRoad?sap-ui-tech-hint=WDA"

def encontrar_frame_com_elemento(page, selector, timeout=30000):
    """
    Procura por um seletor na página principal e em todos os iframes ativos.
    Retorna a tuple (target_context, locator) quando encontrado.
    """
    inicio = time.time()
    while time.time() - inicio < (timeout / 1000):
        # 1. Procura na página principal
        try:
            loc = page.locator(selector).first
            if loc.is_visible():
                return page, loc
        except Exception:
            pass

        # 2. Procura em cada iframe
        for f in page.frames:
            try:
                loc = f.locator(selector).first
                if loc.is_visible():
                    return f, loc
            except Exception:
                pass
        
        time.sleep(1)
    return None, None

def consultar_custos_of(of_numero: str, usuario: str = None, senha: str = None, headless: bool = False) -> list:
    """
    Acessa a transação FreightOrder-changeRoad no SAP Fiori Web Dynpro,
    preenche a Ordem de Frete (OF), avança, acessa a aba de Despesas/Custos (Charges)
    e extrai todas as linhas de custos encontradas.
    """
    load_dotenv()
    usuario = usuario or os.getenv("SAP_WEB_USER")
    senha = senha or os.getenv("SAP_WEB_PASSWORD")

    if not usuario or not senha:
        raise ValueError("Credenciais SAP_WEB_USER e SAP_WEB_PASSWORD não configuradas no .env")

    localappdata = os.environ.get("LOCALAPPDATA", "")
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(localappdata, "ms-playwright")

    if not _garantir_playwright_instalado():
        raise RuntimeError("Playwright/Chromium não instalado.")

    from playwright.sync_api import sync_playwright

    playwright_instance = None
    browser = None
    custos_extraidos = []

    try:
        log_sys.write(f"🚀 Iniciando navegação para consultar custos da OF: {of_numero}")
        playwright_instance = sync_playwright().start()
        browser = playwright_instance.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        log_sys.write("🔐 Acessando SAP Fiori - Modificar Ordem de Frete...")
        page.goto(SAP_CHANGE_FO_URL, timeout=60000)

        # Login no SAP Fiori
        log_sys.write("🔐 Efetuando Login...")
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
            page.get_by_role("textbox", name="Senha").fill(senha)
            page.get_by_role("button", name="Logon").click()

        time.sleep(3)
        log_sys.write(f"⏳ Aguardando a tela da transação carregar (procurando o campo 'Ordem de frete')...")

        # Procura o campo de entrada em qualquer contexto (page ou iframes)
        selectors_of = [
            "input[title*='frete']",
            "input[title*='Frete']",
            "input[title*='Freight']",
            "#WD51",
            "input[name='WD51']",
            "input.lsField__input"
        ]

        target_context = None
        input_of = None

        for sel in selectors_of:
            log_sys.write(f"🔍 Testando seletor '{sel}' nos frames...")
            ctx, loc = encontrar_frame_com_elemento(page, sel, timeout=5000)
            if loc:
                target_context = ctx
                input_of = loc
                log_sys.write(f"  ✅ Campo OF encontrado usando seletor '{sel}' em {ctx}!")
                break

        if not input_of:
            # Varredura em todos os frames para encontrar inputs visíveis
            log_sys.write("⚠️ Buscando qualquer input visível em todos os frames...")
            for idx, frame in enumerate([page] + page.frames):
                try:
                    inputs = frame.locator("input").all()
                    for i, ipt in enumerate(inputs):
                        if ipt.is_visible():
                            title = ipt.get_attribute("title") or ""
                            id_attr = ipt.get_attribute("id") or ""
                            name_attr = ipt.get_attribute("name") or ""
                            log_sys.write(f"   [Frame {idx}] Input [{i}]: id='{id_attr}', name='{name_attr}', title='{title}'")
                            if not input_of:
                                input_of = ipt
                                target_context = frame
                except Exception:
                    pass

        if not input_of:
            page.screenshot(path="erro_iframe_of.png")
            raise RuntimeError("Não foi possível localizar o campo da Ordem de Frete na aplicação SAP.")

        log_sys.write(f"📝 Preenchendo a Ordem de Frete '{of_numero}'...")
        input_of.click()
        input_of.fill(of_numero)
        time.sleep(1)

        # Procura o botão Avançar no mesmo contexto do campo de entrada
        log_sys.write("➡️ Procurando e clicando no botão 'Avançar'...")
        btn_avancar = None
        selectors_btn = [
            "#WD5C",
            "#WD5C-caption",
            "span:has-text('Avançar')",
            "div[title='Avançar']",
            "span:has-text('Continue')"
        ]

        for sel in selectors_btn:
            try:
                loc = target_context.locator(sel).first
                if loc.is_visible():
                    btn_avancar = loc
                    log_sys.write(f"  ✅ Botão Avançar encontrado via '{sel}'")
                    break
            except Exception:
                pass

        if btn_avancar:
            btn_avancar.click()
        else:
            log_sys.write("⚠️ Pressionando Enter no campo da OF...")
            input_of.press("Enter")

        log_sys.write("⏳ Aguardando a Ordem de Frete carregar na tela...")
        time.sleep(5)
        aguardar_fim_carregamento_sap(target_context, timeout=45000)

        # Procura a aba Charges / Despesas / Custos
        log_sys.write("⏳ Procurando a aba de Charges / Despesas / Custos...")
        tab_clicked = False

        for option in ["Charges", "Despesas", "Custos"]:
            try:
                loc = target_context.locator(f"span:has-text('{option}'), div[title*='{option}']").first
                if loc.is_visible(timeout=3000):
                    loc.click()
                    tab_clicked = True
                    log_sys.write(f"  ✅ Clicou na aba '{option}'!")
                    break
            except Exception:
                pass

        if not tab_clicked:
            try:
                tabs = target_context.get_by_role("tab").all()
                for t in tabs:
                    txt = t.text_content() or ""
                    log_sys.write(f"   Aba encontrada: {txt.strip()}")
                    if re.search(r"(Charges|Despesas|Custos)", txt, re.IGNORECASE):
                        t.click()
                        tab_clicked = True
                        log_sys.write(f"  ✅ Clicou na aba por role: '{txt.strip()}'")
                        break
            except Exception as e_tab:
                log_sys.write(f"⚠️ Erro ao procurar abas por role: {e_tab}")

        time.sleep(3)
        aguardar_fim_carregamento_sap(target_context, timeout=30000)

        # Clicar em Expand All para ver todas as linhas
        log_sys.write("⏳ Clicando em Expand All...")
        try:
            expand_btn = target_context.locator("div[title='Expand All'], button:has-text('Expand All')").first
            if expand_btn.is_visible(timeout=3000):
                expand_btn.click()
                log_sys.write("  ✅ Expand All clicado")
        except Exception:
            log_sys.write("ℹ️ Expand All não encontrado ou não necessário.")

        time.sleep(2)
        aguardar_fim_carregamento_sap(target_context, timeout=30000)

        # Extrair todas as linhas de custos
        log_sys.write("🔍 Extraindo dados da tabela de Custos/Charges...")
        tables = target_context.locator("table").all()
        log_sys.write(f"📊 Total de tabelas encontradas: {len(tables)}")

        todas_linhas = []
        for t_idx, table in enumerate(tables):
            try:
                rows = table.locator("tr").all()
                for r_idx, row in enumerate(rows):
                    cells = row.locator("td, th").all()
                    row_vals = []
                    for c in cells:
                        try:
                            txt = c.inner_text().strip().replace("\n", " ")
                            if txt:
                                row_vals.append(txt)
                        except Exception:
                            pass
                    if row_vals:
                        log_sys.write(f"  Tabela [{t_idx+1}] Linha [{r_idx+1}]: {' | '.join(row_vals)}")
                        todas_linhas.append(row_vals)
            except Exception as ex_t:
                log_sys.write(f"⚠️ Erro ao ler tabela [{t_idx}]: {ex_t}")

        if not todas_linhas:
            log_sys.write("🔎 Extraindo linhas do corpo da página...")
            body_text = target_context.locator("body").inner_text()
            for line in body_text.splitlines():
                if any(k in line for k in ["FB", "BRL", "USD", "Rate", "Amount", "Montante", "Taxa", "Charge", "Item"]):
                    log_sys.write(f"  > {line.strip()}")
                    todas_linhas.append([line.strip()])

        page.screenshot(path="custos_of_capturados.png")
        log_sys.write("📸 Captura final salva como 'custos_of_capturados.png'.")

        return todas_linhas

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
    from src.expedicao.sap_custos_of import consultar_e_editar_custos_of

    print("=" * 60)
    print("🛠️ SCRIPT DE DEBUG / TESTE DE CUSTOS DE OF NO SAP")
    print("=" * 60)

    # Obter parâmetros via terminal ou prompt interativo
    of_test = sys.argv[1] if len(sys.argv) > 1 else input("1. Informe o número da OF [Padrão: 6100325111]: ").strip() or "6100325111"
    valor_test = sys.argv[2] if len(sys.argv) > 2 else input("2. Informe o valor do frete [Padrão: 999,99]: ").strip() or "999,99"
    alvo_test = sys.argv[3] if len(sys.argv) > 3 else input("3. Cliente ou Número da linha (ex: CAMIL, BOMPRECO, 4) [Padrão: CAMIL]: ").strip() or "CAMIL"

    texto_linha = ""
    linha_editar = 1
    try:
        linha_editar = int(alvo_test)
    except ValueError:
        texto_linha = alvo_test

    print(f"\n🚀 Iniciando automação para a OF {of_test} (Linha/Alvo: {alvo_test})...\n")

    res = consultar_e_editar_custos_of(
        of_numero=of_test,
        novo_valor_teste=valor_test,
        texto_linha=texto_linha,
        linha_editar=linha_editar,
        salvar=False,  # False = apenas simula no navegador visual sem gravar
        headless=False,  # Exibe o navegador visualmente
        tempo_espera_visual=30  # Mantém o navegador aberto por 30 segundos
    )

    print("\n" + "=" * 60)
    print("📊 RESULTADO DO TESTE:")
    print(f"  • OF: {res['of_numero']}")
    print(f"  • Linha/Alvo Solicitado: {res.get('linha_editada', '?')}")
    print(f"  • Sucesso no Preenchimento: {'✅ SIM' if res['edicao_sucesso'] else '❌ NÃO'}")
    print(f"  • Valor Preenchido: {res['valor_editado']}")
    print("=" * 60)
