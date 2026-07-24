"""
Módulo para download de Packlist do SAP Web via Playwright.
Acessa https://appprod.sap.valgroupco.com/sap/bc/ui2/flp?sap-client=200&sap-language=PT#zui5packinglist-display
e baixa PDFs para cada remessa informada.
"""

import os
import sys
import time
import subprocess
from src.utils.common import log_sys


SAP_WEB_URL_NORMAL = "https://appprod.sap.valgroupco.com/sap/bc/ui2/flp?sap-client=200&sap-language=PT#zui5packinglist-display"
SAP_WEB_URL_JBS = "https://appprod.sap.valgroupco.com/sap/bc/ui2/flp?sap-client=200&sap-language=PT#ZUI5_PL_DELIVER-display"


def _garantir_playwright_instalado():
    """
    Garante que o Playwright e o browser Chromium estão instalados.
    Retorna True se está tudo pronto, False caso contrário.
    """
    # Tenta importar o playwright (deve vir embutido no EXE)
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except Exception as e:
        import traceback
        erro_detalhado = traceback.format_exc()
        log_sys.write(f"❌ Erro ao carregar Playwright: {e}")
        log_sys.write(f"📋 Traceback detalhado:\n{erro_detalhado}")
        return False

    # Detecta o caminho padrão dos browsers do Playwright
    localappdata = os.environ.get("LOCALAPPDATA", "")
    browsers_path = os.path.join(localappdata, "ms-playwright")

    chromium_found = False
    if os.path.isdir(browsers_path):
        for folder in os.listdir(browsers_path):
            if folder.startswith("chromium"):
                chromium_exe = os.path.join(browsers_path, folder, "chrome-win", "chrome.exe")
                if os.path.isfile(chromium_exe):
                    chromium_found = True
                    break

    if not chromium_found:
        log_sys.write("⏳ Browser Chromium não encontrado. Instalando automaticamente (pode demorar alguns minutos)...")
        log_sys.write("   Por favor, aguarde...")
        try:
            python_exec = sys.executable
            env = os.environ.copy()
            # Quando rodando como EXE compilado, sys.executable é o próprio EXE.
            # Mas o Playwright precisa rodar através do driver python ou via cli do playwright.
            # No PyInstaller, o módulo playwright.cli pode ser chamado diretamente.
            # Vamos tentar rodar o instalador do playwright usando o python do ambiente se disponível,
            # ou chamando diretamente pelo driver embutido.
            
            # Tenta rodar via sys.executable se estiver em dev, ou procura o python no ambiente.
            import subprocess
            cmd = [python_exec, "-m", "playwright", "install", "chromium"]
            if getattr(sys, 'frozen', False):
                # No executável compilado, podemos invocar o playwright.cli diretamente via python do venv se ele existir,
                # ou usar o executável do driver do playwright embutido no pacote.
                # A forma mais garantida é chamar usando o script do python do ambiente local se existir.
                venv_python = os.path.join(os.getcwd(), ".venv", "Scripts", "python.exe")
                if os.path.isfile(venv_python):
                    cmd = [venv_python, "-m", "playwright", "install", "chromium"]
                else:
                    # Se não achar o python do venv, tenta com 'python' global
                    cmd = ["python", "-m", "playwright", "install", "chromium"]

            result = subprocess.run(
                cmd,
                capture_output=True, text=True, env=env
            )
            if result.returncode == 0:
                log_sys.write("✅ Chromium instalado com sucesso!")
            else:
                # Tenta alternativa: usar o próprio executável do driver do playwright
                log_sys.write("⏳ Tentando método alternativo de instalação do Chromium...")
                try:
                    from playwright._impl._driver import compute_driver_executable
                    driver_executable, driver_cli = compute_driver_executable()
                    # O driver_executable é o node.exe e o driver_cli é o cli.js do playwright.
                    # Devemos passar o cli.js como argumento para o node executá-lo.
                    result_alt = subprocess.run(
                        [driver_executable, driver_cli, "install", "chromium"],
                        capture_output=True, text=True, env=env
                    )
                    if result_alt.returncode == 0:
                        log_sys.write("✅ Chromium instalado com sucesso (método alternativo)!")
                    else:
                        log_sys.write(f"❌ Falha ao instalar Chromium: {result_alt.stderr[:500] if result_alt.stderr else 'Erro desconhecido'}")
                        return False
                except Exception as ex:
                    log_sys.write(f"❌ Falha na instalação alternativa: {ex}")
                    return False
        except Exception as e:
            log_sys.write(f"❌ Erro ao instalar Chromium automaticamente: {e}")
            log_sys.write("   Execute manualmente: playwright install chromium")
            return False

    return True


def baixar_packlist_sap(remessas: list, pasta_destino: str, usuario: str, senha: str, tipo: str = 'normal'):
    """
    Baixa os PDFs de Packlist do SAP Web para cada remessa informada.
    
    Args:
        remessas: Lista de números de remessa (strings).
        pasta_destino: Caminho da pasta onde salvar os PDFs.
        usuario: Usuário SAP Web.
        senha: Senha SAP Web.
        tipo: Tipo de packlist ('normal' ou 'jbs').
    """
    if not remessas:
        log_sys.write("❌ Nenhuma remessa informada para baixar Packlist.")
        return
    
    if pasta_destino:
        pasta_destino = os.path.normpath(pasta_destino)
        os.makedirs(pasta_destino, exist_ok=True)

    if not pasta_destino or not os.path.isdir(pasta_destino):
        log_sys.write("❌ Pasta de destino inválida ou não selecionada.")
        return
    
    if not usuario or not senha:
        log_sys.write("❌ Credenciais SAP Web não configuradas. Vá em 'Configurar Credenciais SAP' e salve seu usuário e senha.")
        return

    # Força o Playwright (especialmente em ambientes empacotados por PyInstaller)
    # a buscar o browser no diretório padrão do usuário do sistema Windows.
    localappdata = os.environ.get("LOCALAPPDATA", "")
    ms_playwright_dir = os.path.join(localappdata, "ms-playwright")
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = ms_playwright_dir

    # Garante que Playwright e Chromium estão prontos
    if not _garantir_playwright_instalado():
        return

    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError  # noqa: F401

    log_sys.write(f"🌐 Iniciando download de Packlist para {len(remessas)} remessa(s)...")
    log_sys.write(f"📁 Pasta de destino: {pasta_destino}")

    browser = None
    playwright_instance = None

    url = SAP_WEB_URL_JBS if tipo == 'jbs' else SAP_WEB_URL_NORMAL

    try:
        playwright_instance = sync_playwright().start()
        # Inicializa o chromium forçando a leitura da pasta correta
        browser = playwright_instance.chromium.launch(headless=False)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # ===== LOGIN =====
        log_sys.write("🔐 Acessando SAP Web e fazendo login...")
        try:
            page.goto(url, timeout=60000)
        except Exception:
            log_sys.write("❌ Não foi possível acessar o SAP Web. Verifique sua conexão de rede e VPN.")
            return

        # Aguarda o campo de usuário aparecer
        try:
            page.get_by_role("textbox", name="Usuário").wait_for(state="visible", timeout=30000)
        except Exception:
            log_sys.write("❌ Página de login do SAP não carregou. Verifique sua conexão de rede e VPN.")
            return

        # Preenche credenciais
        page.get_by_role("textbox", name="Usuário").click()
        page.get_by_role("textbox", name="Usuário").fill(usuario)
        page.get_by_role("textbox", name="Usuário").press("Tab")
        page.get_by_role("textbox", name="Senha").fill(senha)
        page.get_by_role("textbox", name="Senha").press("Enter")

        # Clica no botão Logon
        try:
            page.get_by_role("button", name="Logon").click(timeout=5000)
        except Exception:
            pass  # Pode não ter botão Logon se o Enter já submeteu

        # Verifica se o login foi bem-sucedido (aguarda o campo Remessa)
        try:
            page.get_by_role("textbox", name="Remessa").wait_for(state="visible", timeout=30000)
        except Exception:
            # Verifica se há mensagem de erro de senha
            try:
                page_content = page.content()
                if "senha" in page_content.lower() or "password" in page_content.lower() or "incorret" in page_content.lower() or "inválid" in page_content.lower():
                    log_sys.write("❌ Usuário ou senha incorretos. Verifique suas credenciais SAP Web nas configurações.")
                else:
                    log_sys.write("❌ Falha no login do SAP Web. Verifique suas credenciais e tente novamente.")
            except Exception:
                log_sys.write("❌ Falha no login do SAP Web. Verifique suas credenciais e conexão de rede/VPN.")
            return

        log_sys.write("✅ Login realizado com sucesso!")

        # ===== PROCESSAR CADA REMESSA =====
        for i, remessa in enumerate(remessas):
            remessa = remessa.strip()
            if not remessa:
                continue

            log_sys.write(f"📋 [{i + 1}/{len(remessas)}] Processando remessa {remessa}...")

            try:
                # Se não é a primeira remessa, limpa o token da remessa anterior
                if i > 0:
                    try:
                        # Tenta clicar no ícone do token para removê-lo
                        token_icon = page.locator("[id*='token'][id*='icon']").first
                        if token_icon.is_visible(timeout=2000):
                            token_icon.click()
                            time.sleep(0.5)
                    except Exception:
                        # Se não achar token, tenta limpar o campo diretamente
                        try:
                            campo_remessa = page.get_by_role("textbox", name="Remessa")
                            campo_remessa.click()
                            campo_remessa.fill("")
                        except Exception:
                            pass

                # Preenche a remessa
                campo_remessa = page.get_by_role("textbox", name="Remessa")
                campo_remessa.click()
                campo_remessa.fill(remessa)

                if tipo == 'jbs':
                    campo_remessa.press("Enter")
                    # Aguarda e clica no checkbox "Linha de cabeçalho para"
                    try:
                        time.sleep(2)
                        page.get_by_role("checkbox", name="Linha de cabeçalho para").wait_for(state="visible", timeout=30000)
                        page.get_by_role("checkbox", name="Linha de cabeçalho para").click()
                    except Exception as e:
                        log_sys.write(f"⚠️ Remessa {remessa}: checkbox 'Linha de cabeçalho para' não apareceu. {e}")
                        continue
                else:
                    # Fluxo normal: Clica em Início
                    page.get_by_role("button", name="Início").click()

                # Aguarda o botão "Gerar PDF" ficar disponível
                try:
                    page.get_by_role("button", name="Gerar PDF").wait_for(state="visible", timeout=30000)
                except Exception:
                    log_sys.write(f"⚠️ Remessa {remessa}: botão 'Gerar PDF' não apareceu.")
                    continue

                # Pequena espera para a página estabilizar
                time.sleep(2)

                # Clica em Gerar PDF e captura o download (com tentativa de retry)
                try:
                    with page.expect_download(timeout=15000) as download_info:
                        page.get_by_role("button", name="Gerar PDF").click()
                    download = download_info.value
                except Exception as e:
                    log_sys.write(f"⚠️ Falha no download da remessa {remessa}. Tentando clicar na checkbox e baixar novamente... (Erro: {e})")
                    if tipo == 'jbs':
                        try:
                            # Clica de novo no checkbox
                            page.get_by_role("checkbox", name="Linha de cabeçalho para").click()
                            time.sleep(1.5)
                        except Exception:
                            pass
                    with page.expect_download(timeout=30000) as download_info:
                        page.get_by_role("button", name="Gerar PDF").click()
                    download = download_info.value

                # Salva o PDF com o nome da remessa
                nome_arquivo = f"PackingList_{remessa}.pdf"
                caminho_destino = os.path.join(pasta_destino, nome_arquivo)
                download.save_as(caminho_destino)

                log_sys.write(f"✅ Remessa {remessa}: PDF salvo como {nome_arquivo}")

            except Exception as e:
                erro_str = str(e).lower()
                if "timeout" in erro_str:
                    log_sys.write(f"❌ Remessa {remessa}: timeout ao aguardar download. Verifique a conexão de rede/VPN.")
                elif "net::" in erro_str or "connection" in erro_str:
                    log_sys.write(f"❌ Remessa {remessa}: erro de conexão. Verifique sua rede e VPN.")
                else:
                    log_sys.write(f"❌ Remessa {remessa}: erro inesperado - {e}")

        log_sys.write(f"🎉 Processo de download de Packlist finalizado! {len(remessas)} remessa(s) processada(s).")

    except Exception as e:
        erro_str = str(e).lower()
        if "executable" in erro_str or "browser" in erro_str:
            log_sys.write(f"❌ Navegador Chromium não encontrado: {e}")
            log_sys.write("   Certifique-se de que a instalação automática foi concluída com sucesso.")
        elif "net::" in erro_str or "err_" in erro_str:
            log_sys.write(f"❌ Erro de conexão com o SAP Web: {e}")
        else:
            log_sys.write(f"❌ Erro fatal no processo de Packlist: {e}")
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
