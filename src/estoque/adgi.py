import time
from src.utils.common import log_sys
from src.utils.sap_utils import conectar_sap
from src.utils.excel_utils import lerDados, colunaUc


def preencher_multi_selecao_ucs(session, lista_ucs: list):
    """
    Preenche a janela de seleção múltipla de UCs no SAP GUI (wnd[1]).
    """
    for idx, uc in enumerate(lista_ucs):
        uc_str = str(uc).strip()
        if not uc_str:
            continue

        if idx == 0:
            campo_uc = "wnd[1]/usr/tabsTAB_STRIP/tabpSIVA/ssubSCREEN_HEADER:SAPLALDB:3010/tblSAPLALDBSINGLE/ctxtRSCSEL_255-SLOW_I[1,0]"
            session.findById(campo_uc).text = uc_str
            session.findById("wnd[1]").sendVKey(0)
        elif idx == 1:
            campo_uc = "wnd[1]/usr/tabsTAB_STRIP/tabpSIVA/ssubSCREEN_HEADER:SAPLALDB:3010/tblSAPLALDBSINGLE/ctxtRSCSEL_255-SLOW_I[1,1]"
            session.findById(campo_uc).text = uc_str
            session.findById("wnd[1]").sendVKey(0)
        else:
            scroll_pos = idx - 1
            session.findById("wnd[1]/usr/tabsTAB_STRIP/tabpSIVA/ssubSCREEN_HEADER:SAPLALDB:3010/tblSAPLALDBSINGLE").verticalScrollbar.position = scroll_pos
            campo_uc = "wnd[1]/usr/tabsTAB_STRIP/tabpSIVA/ssubSCREEN_HEADER:SAPLALDB:3010/tblSAPLALDBSINGLE/ctxtRSCSEL_255-SLOW_I[1,1]"
            session.findById(campo_uc).text = uc_str
            session.findById("wnd[1]").sendVKey(0)


def executar_adgi(
    session=None,
    ucs: list = None,
    lgnum: str = "sp10",
    process_key: str = "NWLO",
    nwmloc: str = "INT",
    caminho_excel: str = None,
    dados_colados: str = None,
    status_etapas: dict = None
) -> dict:
    """
    Realiza o lançamento de baixa de estoque (POST_GI) na transação /n/scwm/adgi do SAP.

    Parâmetros:
      - session: Sessão COM do SAP GUI (conecta automaticamente se None).
      - ucs: Lista contendo os códigos das UCs.
      - lgnum: Número do depósito (padrão: "sp10").
      - process_key: Chave de processo (padrão: "NWLO").
      - nwmloc: Destino/Local (padrão: "INT").
      - caminho_excel: Caminho para arquivo Excel contendo UCs (opcional).
      - dados_colados: Texto contendo UCs vindas da área de transferência (opcional).
      - status_etapas: Dicionário opcional para acompanhamento de status na UI do app.

    Retorna:
      - dict com "status" ("success" ou "error"), "mensagem", total_ucs e linhas_sap.
    """
    lista_ucs = []

    # 1. Carregar lista de UCs a partir dos parâmetros fornecidos
    if ucs:
        if isinstance(ucs, list):
            lista_ucs = [str(u).strip() for u in ucs if str(u).strip()]
        else:
            lista_ucs = [str(ucs).strip()]
    elif caminho_excel or dados_colados:
        df = lerDados(caminho_excel, dados_colados)
        if df is not None and colunaUc in df.columns:
            lista_ucs = df[colunaUc].dropna().astype(str).str.strip().tolist()

    if not lista_ucs:
        msg = "Nenhuma UC foi fornecida para processamento em ADGI."
        log_sys.write(f"⚠️ {msg}")
        return {"status": "error", "mensagem": msg, "total_ucs": 0, "linhas_sap": 0}

    log_sys.write(f"🚀 Iniciando processo ADGI (/n/scwm/adgi) para {len(lista_ucs)} UC(s)...")

    if session is None:
        session = conectar_sap()
        if not session:
            msg = "Não foi possível conectar ao SAP GUI."
            log_sys.write(f"❌ {msg}")
            return {"status": "error", "mensagem": msg, "total_ucs": len(lista_ucs), "linhas_sap": 0}

    try:
        session.findById("wnd[0]").maximize()

        # 2. Acessar /n/scwm/adgi
        log_sys.write("🔑 Acessando transação /n/scwm/adgi...")
        session.findById("wnd[0]/tbar[0]/okcd").text = "/n/scwm/adgi"
        session.findById("wnd[0]").sendVKey(0)
        time.sleep(0.5)

        # 3. Preencher parâmetros iniciais
        log_sys.write(f"📝 Preenchendo parâmetros iniciais (LGNUM: {lgnum}, Processo: {process_key}, Local: {nwmloc})...")
        session.findById("wnd[0]/usr/ctxtP_LGNUM").text = str(lgnum)
        session.findById("wnd[0]/usr/cmbP_PROCES").key = str(process_key)
        session.findById("wnd[0]").sendVKey(0)
        time.sleep(0.3)

        session.findById("wnd[0]/usr/ctxtP_NWMLOC").text = str(nwmloc)
        session.findById("wnd[0]").sendVKey(0)
        time.sleep(0.3)
        session.findById("wnd[0]").sendVKey(0)
        time.sleep(0.3)

        # 4. Abrir janela de seleção múltipla de UCs
        log_sys.write("📋 Abrindo janela de seleção múltipla de UCs...")
        session.findById("wnd[0]/usr/txt%_SO_HU_%_APP_%-TEXT").setFocus()
        session.findById("wnd[0]/usr/txt%_SO_HU_%_APP_%-TEXT").caretPosition = 17
        session.findById("wnd[0]/usr/btn%_SO_HU_%_APP_%-VALU_PUSH").press()
        time.sleep(0.5)

        # 5. Preencher as UCs na tabela
        log_sys.write(f"✏️ Preenchendo {len(lista_ucs)} UC(s) na seleção múltipla...")
        preencher_multi_selecao_ucs(session, lista_ucs)

        # 6. Confirmar pop-up de seleção (F8) e executar pesquisa na tela principal (F8)
        session.findById("wnd[1]/tbar[0]/btn[8]").press()
        time.sleep(0.5)
        session.findById("wnd[0]/tbar[1]/btn[8]").press()
        time.sleep(1.0)

        # 7. Obter a grid ALV e aplicar ordenação crescente na coluna HUIDENT
        grid = session.findById("wnd[0]/usr/shellcont/shell/shellcont[0]/shell")
        grid.setCurrentCell(-1, "HUIDENT")
        grid.selectColumn("HUIDENT")
        grid.pressToolbarButton("&SORT_ASC")
        time.sleep(0.5)

        # 8. Contar linhas e validar se é igual ao número de UCs fornecidas
        qtd_linhas_sap = grid.RowCount
        log_sys.write(f"📊 Linhas retornadas no SAP: {qtd_linhas_sap} | UCs esperadas: {len(lista_ucs)}")

        if qtd_linhas_sap == 0:
            msg = "Nenhum registro encontrado no SAP para as UCs informadas."
            log_sys.write(f"❌ {msg}")
            return {"status": "error", "mensagem": msg, "total_ucs": len(lista_ucs), "linhas_sap": 0}

        if qtd_linhas_sap != len(lista_ucs):
            msg = f"Divergência detectada: número de linhas no SAP ({qtd_linhas_sap}) é diferente do número de UCs informadas ({len(lista_ucs)}). O processo POST_GI não foi executado."
            log_sys.write(f"❌ {msg}")
            return {
                "status": "error",
                "mensagem": msg,
                "total_ucs": len(lista_ucs),
                "linhas_sap": qtd_linhas_sap
            }

        # 9. Se o número de linhas coincidir, selecionar todas e executar POST_GI
        log_sys.write("⚙️ Linhas conferidas. Selecionando todas as linhas e executando 'POST_GI'...")
        grid.setCurrentCell(-1, "")
        grid.selectAll()
        grid.pressToolbarButton("POST_GI")
        time.sleep(0.5)

        # Confirmar mensagem de confirmação
        session.findById("wnd[1]/usr/btnBUTTON_1").press()
        time.sleep(0.5)

        msg_sucesso = f"Baixa de estoque (POST_GI) concluída com sucesso para {qtd_linhas_sap} UC(s)."
        log_sys.write(f"✅ {msg_sucesso}")

        return {
            "status": "success",
            "mensagem": msg_sucesso,
            "total_ucs": len(lista_ucs),
            "linhas_sap": qtd_linhas_sap
        }

    except Exception as e:
        msg_erro = f"Erro durante o processo ADGI no SAP: {e}"
        log_sys.write(f"❌ {msg_erro}")
        return {
            "status": "error",
            "mensagem": msg_erro,
            "total_ucs": len(lista_ucs),
            "linhas_sap": 0
        }
