import time
from src.utils.common import log_sys
from src.utils.sap_utils import conectar_sap
from src.utils.excel_utils import lerDados, colunaUc

def preencher_multi_selecao_ucs(session, lista_ucs: list):
    """
    Preenche a janela de seleção múltipla de UCs no SAP GUI (wnd[2]).
    """
    for idx, uc in enumerate(lista_ucs):
        uc_str = str(uc).strip()
        if not uc_str:
            continue

        if idx == 0:
            campo_uc = "wnd[2]/usr/tabsTAB_STRIP/tabpSIVA/ssubSCREEN_HEADER:SAPLALDB:3010/tblSAPLALDBSINGLE/ctxtRSCSEL_255-SLOW_I[1,0]"
            session.findById(campo_uc).text = uc_str
            session.findById("wnd[2]").sendVKey(0)
        elif idx == 1:
            campo_uc = "wnd[2]/usr/tabsTAB_STRIP/tabpSIVA/ssubSCREEN_HEADER:SAPLALDB:3010/tblSAPLALDBSINGLE/ctxtRSCSEL_255-SLOW_I[1,1]"
            session.findById(campo_uc).text = uc_str
            session.findById("wnd[2]").sendVKey(0)
        else:
            scroll_pos = idx - 1
            session.findById("wnd[2]/usr/tabsTAB_STRIP/tabpSIVA/ssubSCREEN_HEADER:SAPLALDB:3010/tblSAPLALDBSINGLE").verticalScrollbar.position = scroll_pos
            campo_uc = "wnd[2]/usr/tabsTAB_STRIP/tabpSIVA/ssubSCREEN_HEADER:SAPLALDB:3010/tblSAPLALDBSINGLE/ctxtRSCSEL_255-SLOW_I[1,1]"
            session.findById(campo_uc).text = uc_str
            session.findById("wnd[2]").sendVKey(0)

def bloquear_desbloquear_ucs(
    session=None,
    ucs: list = None,
    categoria_estoque: str = "01",
    caminho_excel: str = None,
    dados_colados: str = None,
    status_etapas: dict = None
) -> dict:
    """
    Realiza a alteração de categoria (desbloquear/bloquear) para uma lista de UCs na transação /n/scwm/mon do SAP.

    Parâmetros:
      - session: Sessão COM do SAP GUI (conecta automaticamente se None).
      - ucs: Lista contendo os códigos das UCs (ex: ["112345678035063262", ...]).
      - categoria_estoque: Código da categoria a aplicar no campo S_ASP_STOCK-TO_CAT (padrão: "01" - Desbloqueio/Livre utiliz.).
      - caminho_excel: Caminho para arquivo Excel contendo UCs (opcional).
      - dados_colados: Texto contendo UCs vindas da área de transferência (opcional).
      - status_etapas: Dicionário opcional para acompanhamento de status na UI do app.

    Retorna:
      - dict com "status" ("success" ou "error"), "mensagem" e detalhes das UCs processadas.
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
        msg = "Nenhuma UC foi fornecida para processamento."
        log_sys.write(f"⚠️ {msg}")
        return {"status": "error", "mensagem": msg, "total_ucs": 0}

    log_sys.write(f"🚀 Iniciando processo de Bloqueio/Desbloqueio para {len(lista_ucs)} UC(s) [Categoria: {categoria_estoque}]...")

    if session is None:
        session = conectar_sap()
        if not session:
            msg = "Não foi possível conectar ao SAP GUI."
            log_sys.write(f"❌ {msg}")
            return {"status": "error", "mensagem": msg, "total_ucs": len(lista_ucs)}

    try:
        session.findById("wnd[0]").maximize()

        # 2. Acessar /n/scwm/mon
        log_sys.write("🔑 Acessando transação /n/scwm/mon...")
        session.findById("wnd[0]/tbar[0]/okcd").text = "/n/scwm/mon"
        session.findById("wnd[0]").sendVKey(0)
        time.sleep(0.5)

        # 3. Pressionar btn[18]
        session.findById("wnd[0]/tbar[1]/btn[18]").press()
        time.sleep(0.5)

        # 4. Selecionar 'Estoque Físico' na árvore
        log_sys.write("🌳 Navegando na árvore para 'Estoque Físico'...")
        try:
            session.findById("wnd[0]/usr/shell/shellcont[0]/shell").expandNode("C000000011")
        except Exception:
            pass

        session.findById("wnd[0]/usr/shell/shellcont[0]/shell").selectedNode = "N000000137"
        session.findById("wnd[0]/usr/shell/shellcont[0]/shell").topNode = "C000000001"
        session.findById("wnd[0]/usr/shell/shellcont[0]/shell").doubleClickNode("N000000137")
        time.sleep(0.5)

        # 5. Abrir flag de seleção múltipla de UCs
        log_sys.write("📋 Abrindo pop-up de seleção múltipla de UCs...")
        session.findById("wnd[1]/usr/btn%_S_HUIDEN_%_APP_%-VALU_PUSH").press()
        time.sleep(0.5)

        # 6. Preencher as UCs na tabela
        log_sys.write(f"✏️ Preenchendo {len(lista_ucs)} UC(s) na seleção múltipla...")
        preencher_multi_selecao_ucs(session, lista_ucs)

        # 7. Confirmar pop-ups de seleção
        session.findById("wnd[2]/tbar[0]/btn[8]").press()
        time.sleep(0.5)
        session.findById("wnd[1]/tbar[0]/btn[8]").press()
        time.sleep(1.0)

        # 8. Obter a grid e validar contagem de linhas
        grid = session.findById("wnd[0]/usr/shell/shellcont[1]/shell/shellcont[0]/shell")
        
        # Seleciona o nó e aplica ordenação na coluna HUIDENT
        session.findById("wnd[0]/usr/shell/shellcont[0]/shell").selectedNode = "N000000137"
        grid.setCurrentCell(-1, "HUIDENT")
        grid.selectColumn("HUIDENT")
        grid.selectedRows = ""
        grid.pressToolbarButton("&SORT_ASC")
        time.sleep(0.5)

        qtd_linhas_sap = grid.RowCount
        log_sys.write(f"📊 Linhas retornadas no SAP: {qtd_linhas_sap} | UCs esperadas: {len(lista_ucs)}")

        if qtd_linhas_sap == 0:
            msg = f"Nenhum registro encontrado no SAP para as UCs informadas."
            log_sys.write(f"❌ {msg}")
            return {"status": "error", "mensagem": msg, "total_ucs": len(lista_ucs), "linhas_sap": 0}

        if qtd_linhas_sap != len(lista_ucs):
            log_sys.write(f"⚠️ DIVERGÊNCIA DETECTADA: O número de linhas no SAP ({qtd_linhas_sap}) não coincide com o total de UCs ({len(lista_ucs)}).")

        # 9. Selecionar todas as linhas e executar alteração de método
        log_sys.write("⚙️ Selecionando todas as linhas e acionando 'Modificar Categoria de Estoque' (METHODS)...")
        grid.setCurrentCell(-1, "")
        grid.selectAll()
        grid.pressToolbarContextButton("METHODS")
        grid.selectContextMenuItem("@M00006")
        time.sleep(0.5)

        # 10. Preencher a nova categoria e executar
        log_sys.write(f"📝 Aplicando categoria de estoque '{categoria_estoque}'...")
        session.findById("wnd[1]/usr/subSUBSCR_PC:/SCWM/SAPLSTOCK_OV_MON_METHODS:0220/ctxt/SCWM/S_ASP_STOCK-TO_CAT").text = str(categoria_estoque)
        session.findById("wnd[1]/tbar[0]/btn[8]").press()
        time.sleep(0.5)
        session.findById("wnd[1]/tbar[0]/btn[0]").press()
        time.sleep(0.5)

        msg_sucesso = f"Processo concluído com sucesso para {qtd_linhas_sap} linha(s) de UC(s) [Categoria: {categoria_estoque}]."
        log_sys.write(f"✅ {msg_sucesso}")

        return {
            "status": "success",
            "mensagem": msg_sucesso,
            "total_ucs": len(lista_ucs),
            "linhas_sap": qtd_linhas_sap
        }

    except Exception as e:
        msg_erro = f"Erro durante o processo de bloqueio/desbloqueio no SAP: {e}"
        log_sys.write(f"❌ {msg_erro}")
        return {
            "status": "error",
            "mensagem": msg_erro,
            "total_ucs": len(lista_ucs)
        }
