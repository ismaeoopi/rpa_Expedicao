import time
from src.utils.common import log_sys
from src.utils.sap_utils import conectar_sap
from src.utils.excel_utils import valorFloatexcel

def executar_vl10b(
    session=None,
    pedido: str = "",
    fornecedor: str = "P716",
    itens: list = None
) -> dict:
    """
    Executa a transação VL10B para criar a remessa a partir do Pedido de Transferência.

    Parâmetros:
      - session: Sessão COM ativa do SAP GUI (se None, conecta automaticamente).
      - pedido: Número do Pedido de Transferência (EBELN).
      - fornecedor: Local de expedição / Fornecedor (padrão: "P716").
      - itens: Lista opcional de dicionários com os itens da remessa:
               [{"material": "200142", "peso_liquido": 1250.0}, ...]

    Retorna:
      - dict com status ("success" ou "error"), mensagem e número da remessa gerada.
    """
    if session is None:
        session = conectar_sap()
        if not session:
            return {"status": "error", "mensagem": "Não foi possível conectar ao SAP GUI.", "remessa": None}

    pedido_str = str(pedido).strip()
    if not pedido_str:
        return {"status": "error", "mensagem": "Número do pedido não informado.", "remessa": None}

    log_sys.write(f"🚀 Iniciando criação de remessa na VL10B para o Pedido: {pedido_str} (Fornecedor: {fornecedor})...")

    try:
        session.findById("wnd[0]").maximize()
        session.findById("wnd[0]/tbar[0]/okcd").text = "/nvl10b"
        session.findById("wnd[0]").sendVKey(0)
        time.sleep(0.5)

        # Preencher Local de Expedição e limpar datas de remessa
        session.findById("wnd[0]/usr/ctxtST_VSTEL-LOW").text = fornecedor
        session.findById("wnd[0]/usr/ctxtST_LEDAT-LOW").text = ""
        session.findById("wnd[0]/usr/ctxtST_LEDAT-HIGH").text = ""

        # Selecionar Aba "Documentos de Compras" (tabpS0S_TAB5)
        session.findById("wnd[0]/usr/tabsTABSTRIP_ORDER_CRITERIA/tabpS0S_TAB5").select()
        time.sleep(0.3)

        # Preencher Pedido de Transferência
        session.findById("wnd[0]/usr/tabsTABSTRIP_ORDER_CRITERIA/tabpS0S_TAB5/ssub%_SUBSCREEN_ORDER_CRITERIA:RVV50R10C:1030/ctxtST_EBELN-LOW").text = pedido_str
        session.findById("wnd[0]/usr/tabsTABSTRIP_ORDER_CRITERIA/tabpS0S_TAB5/ssub%_SUBSCREEN_ORDER_CRITERIA:RVV50R10C:1030/ctxtST_EBELN-HIGH").text = pedido_str

        # Executar Busca (F8)
        session.findById("wnd[0]/tbar[1]/btn[8]").press()
        time.sleep(1.0)

        # Selecionar primeira linha da grid e gerar remessa em segundo plano (btn[19])
        grid = session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell")
        grid.currentCellColumn = ""
        grid.selectedRows = "0"
        session.findById("wnd[0]/tbar[1]/btn[19]").press()
        time.sleep(1.0)

        # Exibir log de fornecimento / remessa gerada
        grid.currentCellColumn = "VBELN"
        grid.clickCurrentCell()
        session.findById("wnd[0]/tbar[1]/btn[25]").press()
        time.sleep(1.0)

        # Se houver lista de itens para ajuste de depósito e quantidade de picking inicial
        if itens:
            session.findById(r"wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\02").select()
            time.sleep(0.5)

            for idx, item in enumerate(itens):
                mat = str(item.get("material", "")).strip()
                peso_liq = valorFloatexcel(item.get("peso_liquido", 0))

                # Definir depósito com base no início do código do material
                dep = "MP1" if mat.startswith("2") else "005"

                session.findById(r"wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\02/ssubSUBSCREEN_BODY:SAPMV50A:1104/tblSAPMV50ATC_LIPS_PICK/ctxtLIPS-LGORT[3,0]").text = dep
                session.findById(r"wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\02/ssubSUBSCREEN_BODY:SAPMV50A:1104/tblSAPMV50ATC_LIPS_PICK/txtLIPSD-G_LFIMG[5,0]").text = peso_liq
                session.findById("wnd[0]").sendVKey(0)
                time.sleep(0.3)

                if idx > 0:
                    tbl = session.findById(r"wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\02/ssubSUBSCREEN_BODY:SAPMV50A:1104/tblSAPMV50ATC_LIPS_PICK")
                    tbl.verticalScrollbar.position = idx

        # Salvar (F11 / btn[11])
        session.findById("wnd[0]/tbar[0]/btn[11]").press()
        time.sleep(0.8)

        # Obter número da remessa acessando VL03N
        session.findById("wnd[0]/tbar[0]/okcd").text = "/nvl03n"
        session.findById("wnd[0]").sendVKey(0)
        time.sleep(0.5)

        num_remessa = session.findById("wnd[0]/usr/ctxtLIKP-VBELN").text.strip()
        log_sys.write(f"✅ Remessa gerada com sucesso na VL10B: {num_remessa}")

        return {
            "status": "success",
            "mensagem": f"Remessa {num_remessa} gerada com sucesso.",
            "remessa": num_remessa
        }

    except Exception as e:
        msg_erro = f"Erro na transação VL10B: {e}"
        log_sys.write(f"❌ {msg_erro}")
        return {
            "status": "error",
            "mensagem": msg_erro,
            "remessa": None
        }
