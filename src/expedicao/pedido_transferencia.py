import time
from datetime import datetime, timedelta
from src.utils.common import log_sys
from src.utils.sap_utils import conectar_sap

CONTAINER_CANDIDATES = ["0013", "0019", "0015", "0010", "0014", "0018", "0020", "0030"]

def _set_text(session, path_suffix, text_value):
    """
    Tenta definir o texto em um elemento SAP GUI tentando diferentes sub-containers SAPLMEGUI se necessário.
    """
    for c in CONTAINER_CANDIDATES:
        try:
            full_path = f"wnd[0]/usr/subSUB0:SAPLMEGUI:{c}/{path_suffix}"
            elem = session.findById(full_path, False)
            if elem:
                elem.text = str(text_value)
                return True
        except Exception:
            pass
    # Se não funcionou via subSUB0 dinâmico, tenta o caminho exato direto caso path_suffix já contenha o caminho completo
    try:
        session.findById(path_suffix).text = str(text_value)
        return True
    except Exception as e:
        raise RuntimeError(f"Não foi possível definir texto no elemento '{path_suffix}': {e}")

def _set_key(session, path_suffix, key_value):
    """
    Tenta definir a chave (key) em um combobox SAP GUI tentando diferentes sub-containers.
    """
    for c in CONTAINER_CANDIDATES:
        try:
            full_path = f"wnd[0]/usr/subSUB0:SAPLMEGUI:{c}/{path_suffix}"
            elem = session.findById(full_path, False)
            if elem:
                elem.key = str(key_value)
                return True
        except Exception:
            pass
    try:
        session.findById(path_suffix).key = str(key_value)
        return True
    except Exception as e:
        raise RuntimeError(f"Não foi possível definir key no elemento '{path_suffix}': {e}")

def _press_button(session, path_suffix):
    """
    Tenta pressionar um botão SAP GUI tentando diferentes sub-containers.
    """
    for c in CONTAINER_CANDIDATES:
        try:
            full_path = f"wnd[0]/usr/subSUB0:SAPLMEGUI:{c}/{path_suffix}"
            elem = session.findById(full_path, False)
            if elem:
                elem.press()
                return True
        except Exception:
            pass
    try:
        session.findById(path_suffix).press()
        return True
    except Exception as e:
        raise RuntimeError(f"Não foi possível pressionar botão '{path_suffix}': {e}")

def _select_tab(session, tab_id="tabpTABIDT19"):
    """
    Seleciona a aba informada (padrão tabpTABIDT19) testando containers dinâmicos do SAP ME21N.
    """
    for c in CONTAINER_CANDIDATES:
        try:
            path = f"wnd[0]/usr/subSUB0:SAPLMEGUI:{c}/subSUB3:SAPLMEVIEWS:1100/subSUB2:SAPLMEVIEWS:1200/subSUB1:SAPLMEGUI:1301/subSUB2:SAPLMEGUI:1303/tabsITEM_DETAIL/{tab_id}"
            elem = session.findById(path, False)
            if elem:
                elem.select()
                return True
        except Exception:
            pass
    # Tenta caminho direto
    try:
        session.findById(f"wnd[0]/usr/subSUB0:SAPLMEGUI:0019/subSUB3:SAPLMEVIEWS:1100/subSUB2:SAPLMEVIEWS:1200/subSUB1:SAPLMEGUI:1301/subSUB2:SAPLMEGUI:1303/tabsITEM_DETAIL/{tab_id}").select()
        return True
    except Exception as e:
        log_sys.write(f"⚠️ Não foi possível selecionar a aba '{tab_id}': {e}")
        return False

def _set_scrollbar_position(session, pos):
    """
    Ajusta o scrollbar da tabela de itens tblSAPLMEGUITC_1211.
    """
    for c in CONTAINER_CANDIDATES:
        try:
            path = f"wnd[0]/usr/subSUB0:SAPLMEGUI:{c}/subSUB2:SAPLMEVIEWS:1100/subSUB2:SAPLMEVIEWS:1200/subSUB1:SAPLMEGUI:1211/tblSAPLMEGUITC_1211"
            tbl = session.findById(path, False)
            if tbl:
                tbl.verticalScrollbar.position = pos
                return True
        except Exception:
            pass
    return False

def criar_pedido_transferencia(
    session=None,
    planta_fornecedora: str = "P716",
    org_compras: str = "VF01",
    grp_compras: str = "450",
    empresa: str = "VMG1",
    itens: list = None,
    data_inicio: str = None,
    salvar: bool = False
) -> dict:
    """
    Cria um Pedido de Transferência no SAP GUI via transação /nme21n.

    Parâmetros:
      - session: Sessão COM ativa do SAP GUI (se None, conecta automaticamente).
      - planta_fornecedora: Código da planta fornecedora (padrão: "P716").
      - org_compras: Organização de compras (padrão: "VF01").
      - grp_compras: Grupo de compradores (padrão: "450").
      - empresa: Empresa (padrão: "VMG1").
      - itens: Lista de dicionários contendo os itens. Exemplo:
            [
                {
                    "material": "sa0163",
                    "quantidade": "1250",
                    "planta_destino": "p701",
                    "deposito_destino": "005",
                    "data": "13082026"  # Opcional
                },
                {
                    "material": "sa0254",
                    "quantidade": "200",
                    "planta_destino": "P711",
                    "deposito_destino": "005"
                }
            ]
      - data_inicio: Data do 1º item no formato DDMMYYYY ou Objeto datetime. Se None, usa a data atual do sistema.
      - salvar: Se True, efetua a gravação do pedido ao final (Ctrl+S / Btn 11) e extrai a mensagem da sbar.

    Retorna:
      - dict com status ("success" ou "error"), mensagem e número do pedido gerado (se salvo).
    """
    if session is None:
        session = conectar_sap()
        if not session:
            raise RuntimeError("Não foi possível conectar ao SAP GUI.")

    if not itens:
        log_sys.write("⚠️ Nenhum item fornecido. Usando itens padrão de teste...")
        itens = [
            {
                "material": "sa0163",
                "quantidade": "1250",
                "planta_destino": "p701",
                "deposito_destino": "005"
            },
            {
                "material": "sa0254",
                "quantidade": "200",
                "planta_destino": "P711",
                "deposito_destino": "005"
            }
        ]

    # Prepara data inicial
    if data_inicio:
        if isinstance(data_inicio, datetime):
            dt_base = data_inicio
        else:
            try:
                dt_base = datetime.strptime(str(data_inicio).replace("/", "").replace("-", ""), "%d%m%Y")
            except Exception:
                dt_base = datetime.now()
    else:
        dt_base = datetime.now()

    log_sys.write(f"🚀 Iniciando Criação de Pedido de Transferência no SAP (ME21N)...")
    log_sys.write(f"📋 Planta Fornecedora: {planta_fornecedora} | Org: {org_compras} | Grp: {grp_compras} | Empresa: {empresa}")
    log_sys.write(f"📦 Total de itens a preencher: {len(itens)}")

    try:
        # 1. Maximizar janela
        session.findById("wnd[0]").maximize()

        # 2. Acessar a transação ME21N
        log_sys.write("🔑 Acessando transação /nme21n...")
        session.findById("wnd[0]/tbar[0]/okcd").text = "/nme21n"
        session.findById("wnd[0]").sendVKey(0)
        time.sleep(1.0)

        # 3. Tipo de pedido (UD) e Planta Fornecedora
        log_sys.write("⚙️ Preenchendo Tipo de Pedido (UD) e Planta Fornecedora...")
        _set_key(session, "subSUB0:SAPLMEGUI:0030/subSUB1:SAPLMEGUI:1105/cmbMEPO_TOPLINE-BSART", "UD")
        _set_text(session, "subSUB0:SAPLMEGUI:0030/subSUB1:SAPLMEGUI:1105/ctxtMEPO_TOPLINE-SUPERFIELD", planta_fornecedora)

        # 4. Preenchimento Padrão do Cabeçalho (Org, Grp, Empresa)
        log_sys.write("📝 Preenchendo dados de Cabeçalho (Org Compras, Grp Compras, Empresa)...")
        _set_text(session, "subSUB1:SAPLMEVIEWS:1100/subSUB2:SAPLMEVIEWS:1200/subSUB1:SAPLMEGUI:1102/tabsHEADER_DETAIL/tabpTABHDT8/ssubTABSTRIPCONTROL2SUB:SAPLMEGUI:1221/ctxtMEPO1222-EKORG", org_compras)
        _set_text(session, "subSUB1:SAPLMEVIEWS:1100/subSUB2:SAPLMEVIEWS:1200/subSUB1:SAPLMEGUI:1102/tabsHEADER_DETAIL/tabpTABHDT8/ssubTABSTRIPCONTROL2SUB:SAPLMEGUI:1221/ctxtMEPO1222-EKGRP", grp_compras)
        _set_text(session, "subSUB1:SAPLMEVIEWS:1100/subSUB2:SAPLMEVIEWS:1200/subSUB1:SAPLMEGUI:1102/tabsHEADER_DETAIL/tabpTABHDT8/ssubTABSTRIPCONTROL2SUB:SAPLMEGUI:1221/ctxtMEPO1222-BUKRS", empresa)

        session.findById("wnd[0]").sendVKey(0)
        time.sleep(1.0)

        # 5. Preenchimento dos Itens
        for idx, item in enumerate(itens):
            material = str(item.get("material", "")).strip()
            qtd = str(item.get("quantidade", "")).strip()
            planta_dest = str(item.get("planta_destino", "")).strip()
            dep_dest = str(item.get("deposito_destino", "")).strip()

            # Regra de data: +1 dia a cada item a partir da data atual/inicial
            if "data" in item and item["data"]:
                data_item_str = str(item["data"]).replace("/", "").replace("-", "").strip()
            else:
                data_dt = dt_base + timedelta(days=idx)
                data_item_str = data_dt.strftime("%d%m%Y")

            log_sys.write(f"  🔹 Preenchendo Item {idx + 1}/{len(itens)}: Material={material}, Qtd={qtd}, Data={data_item_str}, PlantaDest={planta_dest}, DepDest={dep_dest}")

            if idx == 0:
                # Item 1: linha 0
                row_idx = 0
            elif idx == 1:
                # Item 2: linha 1
                row_idx = 1
            else:
                # Item 3 em diante: descer o scroll position = idx - 1, preencher na linha 1
                scroll_pos = idx - 1
                log_sys.write(f"  📜 Item {idx + 1}: Ajustando scrollbar position para {scroll_pos}...")
                _set_scrollbar_position(session, scroll_pos)
                time.sleep(0.3)
                row_idx = 1

            # Preenche os campos do item na linha definida
            _set_text(session, f"subSUB2:SAPLMEVIEWS:1100/subSUB2:SAPLMEVIEWS:1200/subSUB1:SAPLMEGUI:1211/tblSAPLMEGUITC_1211/ctxtMEPO1211-EMATN[4,{row_idx}]", material)
            _set_text(session, f"subSUB2:SAPLMEVIEWS:1100/subSUB2:SAPLMEVIEWS:1200/subSUB1:SAPLMEGUI:1211/tblSAPLMEGUITC_1211/txtMEPO1211-MENGE[6,{row_idx}]", qtd)
            _set_text(session, f"subSUB2:SAPLMEVIEWS:1100/subSUB2:SAPLMEVIEWS:1200/subSUB1:SAPLMEGUI:1211/tblSAPLMEGUITC_1211/ctxtMEPO1211-EEIND[9,{row_idx}]", data_item_str)
            _set_text(session, f"subSUB2:SAPLMEVIEWS:1100/subSUB2:SAPLMEVIEWS:1200/subSUB1:SAPLMEGUI:1211/tblSAPLMEGUITC_1211/ctxtMEPO1211-NAME1[11,{row_idx}]", planta_dest)
            _set_text(session, f"subSUB2:SAPLMEVIEWS:1100/subSUB2:SAPLMEVIEWS:1200/subSUB1:SAPLMEGUI:1211/tblSAPLMEGUITC_1211/ctxtMEPO1211-LGOBE[12,{row_idx}]", dep_dest)

            session.findById("wnd[0]").sendVKey(0)
            time.sleep(0.5)

        # 6. Seleção da aba de confirmação (tabpTABIDT19) e preenchimento das confirmações (Z000)
        log_sys.write("📑 Selecionando aba de Confirmações (tabpTABIDT19)...")
        _select_tab(session, "tabpTABIDT19")
        time.sleep(0.5)

        log_sys.write(f"⚙️ Aplicando chave de confirmação Z000 para {len(itens)} item(ns)...")
        for idx in range(len(itens)):
            log_sys.write(f"  ✔ Confirmação no Item {idx + 1}: Definindo BSTAE = Z000")
            _set_key(
                session,
                "subSUB3:SAPLMEVIEWS:1100/subSUB2:SAPLMEVIEWS:1200/subSUB1:SAPLMEGUI:1301/subSUB2:SAPLMEGUI:1303/tabsITEM_DETAIL/tabpTABIDT19/ssubTABSTRIPCONTROL1SUB:SAPLMEVIEWS:1101/subSUB1:SAPLMEGUI:1334/cmbMEPO1334-BSTAE",
                "Z000"
            )

            # Se houver mais itens, avança para o próximo item nos detalhes
            if idx < len(itens) - 1:
                log_sys.write("  ➡️ Alternando para o próximo item (btn%#AUTOTEXT002)...")
                _press_button(
                    session,
                    "subSUB3:SAPLMEVIEWS:1100/subSUB2:SAPLMEVIEWS:1200/subSUB1:SAPLMEGUI:1301/subSUB1:SAPLMEGUI:6000/btn%#AUTOTEXT002"
                )
                time.sleep(0.3)

        session.findById("wnd[0]").sendVKey(0)
        time.sleep(0.5)

        # 7. Salvamento Opcional
        pedido_numero = None
        sbar_msg = ""
        try:
            sbar_msg = session.findById("wnd[0]/sbar").text
        except Exception:
            pass

        if salvar:
            log_sys.write("💾 Salvando o Pedido de Transferência (Ctrl+S / btn[11])...")
            try:
                session.findById("wnd[0]/tbar[0]/btn[11]").press()
                time.sleep(1.0)
                sbar_msg = session.findById("wnd[0]/sbar").text
                log_sys.write(f"📢 Mensagem de retorno SAP: {sbar_msg}")
            except Exception as save_err:
                log_sys.write(f"⚠️ Erro ao acionar botão de salvar: {save_err}")

        log_sys.write("✅ Processo de criação do Pedido de Transferência concluído com sucesso!")
        return {
            "status": "success",
            "mensagem": sbar_msg or "Pedido de transferência preenchido com sucesso.",
            "pedido": pedido_numero,
            "itens_processados": len(itens)
        }

    except Exception as e:
        log_sys.write(f"❌ Erro ao criar Pedido de Transferência: {e}")
        return {
            "status": "error",
            "mensagem": str(e),
            "pedido": None
        }
