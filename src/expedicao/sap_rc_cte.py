"""
sap_rc_cte.py
=============
Automação SAP GUI para criação de Requisição de Compra (RC) de fretes CTE
via transação ME51N.

Lógica principal:
  1. Abre ME51N e define tipo de documento
  2. Preenche o cabeçalho (texto com lista de CTEs)
  3. Preenche a PRIMEIRA linha (material, fornecedor, material, data, CC, flag GR, fornecedor preferencial)
  4. Faz N-1 cópias da linha 0 via toolbar &MEREQCOPY (loop dinâmico)
  5. Para cada linha copiada, navega até ela (scroll) e atualiza o PREIS individualmente
  6. Desmarca o flag WEPOS (entrada de mercadoria) em cada item via loop
  7. Adiciona o arquivo de anexo (uma vez, no cabeçalho)
  8. Salva e retorna o número da RC

Uso standalone:
    python sap_rc_cte.py

Uso como módulo:
    from src.expedicao.sap_rc_cte import criar_rc_cte

    rc = criar_rc_cte(
        session=session,
        ctes=[
            {"numero": "562847", "valor": "2.664,78"},
            {"numero": "573186", "valor": "5.782,15"},
            ...
        ],
        centro_custo="AQ203",
        fornecedor="9190617",
        material="CTE.16.04",
        planta="p716",
        data_hoje="25082026",          # formato DDMMYYYY
        caminho_anexo=r"C:\\Users\\ismael.nascimento\\Downloads\\",
        arquivo_anexo="Tabela_Cabotagem_2026.xlsx",
        tipo_imputacao="K",            # K = Centro de Custo  /  F = Ordem de Investimento
        salvar=True,
    )
    print("RC criada:", rc)
"""

import time
import re
import os
import sys
import datetime

# ---------------------------------------------------------------------------
# Helpers de log
# ---------------------------------------------------------------------------

def _log(msg: str) -> None:
    """Imprime mensagem com timestamp no console."""
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Constantes – sufixo fixo da grid (a parte que muda é o subSUB0)
# ---------------------------------------------------------------------------

_GRID_SUFFIX = (
    "/subSUB2:SAPLMEVIEWS:1100"
    "/subSUB2:SAPLMEVIEWS:1200"
    "/subSUB1:SAPLMEGUI:3212"
    "/cntlGRIDCONTROL/shellcont/shell"
)

# IDs do subSUB0 que o SAP usa conforme o estado da tela ME51N.
# O SAP alterna entre eles à medida que o usuário preenche campos.
_GRID_SUB_IDS = ["0013", "0010", "0019", "0015", "0016", "0017", "0018"]

# ---------------------------------------------------------------------------
# Funções auxiliares SAP
# ---------------------------------------------------------------------------

def _grid(session) -> object:
    """
    Retorna o objeto shell da grid de itens da ME51N.

    O SAP muda o ID do subSUB0 (ex: 0013 → 0010 → 0019) conforme
    o estado da tela. Esta função tenta todos os IDs conhecidos e
    retorna o primeiro que responder sem erro.

    Raises RuntimeError se nenhum ID funcionar.
    """
    for sub_id in _GRID_SUB_IDS:
        path = f"wnd[0]/usr/subSUB0:SAPLMEGUI:{sub_id}{_GRID_SUFFIX}"
        try:
            obj = session.findById(path)
            # Testa se o objeto responde (provoca exceção se inválido)
            _ = obj.type
            return obj
        except Exception:
            continue
    raise RuntimeError(
        "Grid de itens da ME51N não encontrada. "
        f"IDs tentados: {_GRID_SUB_IDS}. "
        "Verifique se a tela ME51N está aberta e na aba de itens."
    )


def _wait(segundos: float = 0.5) -> None:
    time.sleep(segundos)


def _send_enter(session) -> None:
    session.findById("wnd[0]").sendVKey(0)


# ---------------------------------------------------------------------------
# Passo 1 – Abrir ME51N e definir tipo de documento
# ---------------------------------------------------------------------------

def _abrir_me51n(session, tipo_doc: str = "NB") -> None:
    _log("📂 Abrindo ME51N...")
    session.findById("wnd[0]").maximize()
    session.findById("wnd[0]/tbar[0]/okcd").text = "/nme51n"
    _send_enter(session)
    _wait(1)

    # Define o tipo de documento (ex: NB = compra normal, ZSUB = subcontratação)
    combo = (
        "wnd[0]/usr/subSUB0:SAPLMEGUI:0013"
        "/subSUB0:SAPLMEGUI:0030"
        "/subSUB1:SAPLMEGUI:3327"
        "/cmbMEREQ_TOPLINE-BSART"
    )
    session.findById(combo).key = tipo_doc
    _wait(0.5)
    _log(f"  ✅ Tipo de documento definido: {tipo_doc}")


# ---------------------------------------------------------------------------
# Passo 2 – Preencher texto de cabeçalho com números dos CTEs
# ---------------------------------------------------------------------------

def _preencher_cabecalho(session, ctes: list[dict], prefixo: str = "Fretes GELOG") -> None:
    _log("📝 Preenchendo cabeçalho com números dos CTEs...")

    numeros = ", ".join(c["numero"] for c in ctes)
    texto = f"{prefixo} - {numeros}\r"

    shell_cabecalho = (
        "wnd[0]/usr/subSUB0:SAPLMEGUI:0013"
        "/subSUB1:SAPLMEVIEWS:1100"
        "/subSUB2:SAPLMEVIEWS:1200"
        "/subSUB1:SAPLMEGUI:3102"
        "/tabsREQ_HEADER_DETAIL/tabpTABREQHDT1"
        "/ssubTABSTRIPCONTROL3SUB:SAPLMEGUI:1230"
        "/subTEXTS:SAPLMMTE:0100"
        "/subEDITOR:SAPLMMTE:0101"
        "/cntlTEXT_EDITOR_0101/shellcont/shell"
    )
    editor = session.findById(shell_cabecalho)
    editor.text = texto
    editor.setSelectionIndexes(len(texto) - 1, len(texto) - 1)
    editor.firstVisibleLine = "1"
    _log(f"  ✅ Cabeçalho: {texto.strip()}")


# ---------------------------------------------------------------------------
# Passo 3 – Preencher a primeira linha (item 0)
# ---------------------------------------------------------------------------

def _preencher_linha_0(
    session,
    cte: dict,
    planta: str,
    material: str,
    tipo_imputacao: str,
    data_hoje: str,
    centro_custo: str,
    fornecedor: str,
) -> None:
    """Preenche todos os campos da primeira linha do item."""
    _log(f"🖊️  Preenchendo linha 0 – CTE {cte['numero']} / valor {cte['valor']}...")

    grid = _grid(session)

    # -- Tipo de imputação (K = Centro de Custo, F = Ordem)
    grid.modifyCell(0, "KNTTP", tipo_imputacao.lower())
    grid.currentCellColumn = "KNTTP"
    grid.pressEnter()
    _wait(0.5)

    # Após pressEnter o subSUB pode mudar para 0010; continua pelo GRID_BASE
    # que o SAP mantém apontado para a grid correta.

    # -- Planta / Centro
    _grid(session).modifyCell(0, "NAME1", planta)
    _grid(session).pressEnter()
    _wait(0.5)

    # -- Quantidade
    _grid(session).modifyCell(0, "MENGE", "1")
    _grid(session).pressEnter()
    _wait(0.5)

    # -- Material
    _grid(session).modifyCell(0, "MATNR", material)
    _grid(session).currentCellColumn = "MATNR"
    _grid(session).pressEnter()
    _wait(1)

    # -- Preço (PREIS) da linha 0
    _grid(session).modifyCell(0, "PREIS", cte["valor"])
    _grid(session).currentCellRow = 0
    _grid(session).firstVisibleRow = 0
    _grid(session).pressEnter()
    _wait(0.5)

    # -- Data de necessidade (aba Entrega/Datas)
    _preencher_datas(session, 0, data_hoje)

    # -- Centro de Custo (aba Imputação)
    _preencher_centro_custo(session, centro_custo)

    # -- Desmarca flag "Entrada de Mercadoria" (aba Remessa)
    _desmarcar_wepos(session)

    # -- Habilita campo de fornecedor preferencial (toggle)
    _habilitar_fornecedor(session)

    # -- Fornecedor preferencial
    _preencher_fornecedor(session, fornecedor)

    _log("  ✅ Linha 0 preenchida.")


def _preencher_datas(session, idx: int, data_hoje: str) -> None:
    """Preenche data início e fim na aba de Entrega (tabpTABREQDT5)."""
    base = (
        "wnd[0]/usr/subSUB0:SAPLMEGUI:0015"
        "/subSUB3:SAPLMEVIEWS:1100"
        "/subSUB2:SAPLMEVIEWS:1200"
        "/subSUB1:SAPLMEGUI:1301"
        "/subSUB2:SAPLMEGUI:3303"
        "/tabsREQ_ITEM_DETAIL/tabpTABREQDT5"
        "/ssubTABSTRIPCONTROL1SUB:SAPLMEGUI:3321"
    )
    session.findById(f"{base}/ctxtMEREQ3321-STARTDATE").text = data_hoje
    session.findById(f"{base}/ctxtMEREQ3321-ENDDATE").text = data_hoje
    end_date = session.findById(f"{base}/ctxtMEREQ3321-ENDDATE")
    end_date.setFocus()
    end_date.caretPosition = 8
    _send_enter(session)
    _wait(0.5)


def _preencher_centro_custo(session, centro_custo: str) -> None:
    """Preenche o centro de custo na aba Imputação (tabpTABREQDT7)."""
    base_cc = (
        "wnd[0]/usr/subSUB0:SAPLMEGUI:0019"
        "/subSUB3:SAPLMEVIEWS:1100"
        "/subSUB2:SAPLMEVIEWS:1200"
        "/subSUB1:SAPLMEGUI:1301"
        "/subSUB2:SAPLMEGUI:3303"
        "/tabsREQ_ITEM_DETAIL/tabpTABREQDT7"
        "/ssubTABSTRIPCONTROL1SUB:SAPLMEVIEWS:1101"
        "/subSUB2:SAPLMEACCTVI:0100"
        "/subSUB1:SAPLMEACCTVI:1100"
        "/subKONTBLOCK:SAPLKACB:2100"
        "/ctxtCOBL-KOSTL"
    )
    cc_field = session.findById(base_cc)
    cc_field.text = centro_custo
    cc_field.caretPosition = len(centro_custo)

    ## Seleciona aba de Remessa para avançar (tabpTABREQDT6)
    session.findById(r"wnd[0]/usr/subSUB0:SAPLMEGUI:0019/subSUB3:SAPLMEVIEWS:1100/subSUB2:SAPLMEVIEWS:1200/subSUB1:SAPLMEGUI:1301/subSUB2:SAPLMEGUI:3303/tabsREQ_ITEM_DETAIL/tabpTABREQDT6").select()
    session.findById(r"wnd[0]/usr/subSUB0:SAPLMEGUI:0015/subSUB3:SAPLMEVIEWS:1100/subSUB2:SAPLMEVIEWS:1200/subSUB1:SAPLMEGUI:1301/subSUB2:SAPLMEGUI:3303/tabsREQ_ITEM_DETAIL/tabpTABREQDT6").select()


def _desmarcar_wepos(session) -> None:
    """Desmarca o flag de entrada de mercadoria (WEPOS) na aba Remessa."""
    base_rem = (
        "wnd[0]/usr/subSUB0:SAPLMEGUI:0015"
        "/subSUB3:SAPLMEVIEWS:1100"
        "/subSUB2:SAPLMEVIEWS:1200"
        "/subSUB1:SAPLMEGUI:1301"
        "/subSUB2:SAPLMEGUI:3303"
        "/tabsREQ_ITEM_DETAIL/tabpTABREQDT6"
        "/ssubTABSTRIPCONTROL1SUB:SAPLMEGUI:3320"
        "/chkMEREQ3320-WEPOS"
    )
    chk = session.findById(base_rem)
    chk.selected = False
    chk.setFocus()


def _habilitar_fornecedor(session) -> None:
    """Pressiona o botão toggle para habilitar o campo de fornecedor (aba Fontes)."""
    
    session.findById(r"wnd[0]/usr/subSUB0:SAPLMEGUI:0015/subSUB3:SAPLMEVIEWS:1100/subSUB2:SAPLMEVIEWS:1200/subSUB1:SAPLMEGUI:1301/subSUB2:SAPLMEGUI:3303/tabsREQ_ITEM_DETAIL/tabpTABREQDT8").select()

    session.findById(
        "wnd[0]/usr/subSUB0:SAPLMEGUI:0019"
        "/subSUB3:SAPLMEVIEWS:1100"
        "/subSUB2:SAPLMEVIEWS:1200"
        "/subSUB1:SAPLMEGUI:1301"
        "/subSUB2:SAPLMEGUI:3303"
        "/tabsREQ_ITEM_DETAIL/tabpTABREQDT8"
        "/ssubTABSTRIPCONTROL1SUB:SAPLMEGUI:3323"
        "/subSUB1:SAPLMEGUI:3325"
        "/btnMEREQ3325-BUTTON_TOGG"
    ).press()


def _preencher_fornecedor(session, fornecedor: str) -> None:
    """Preenche o código do fornecedor preferencial."""
    base_forn = (
        "wnd[0]/usr/subSUB0:SAPLMEGUI:0019"
        "/subSUB3:SAPLMEVIEWS:1100"
        "/subSUB2:SAPLMEVIEWS:1200"
        "/subSUB1:SAPLMEGUI:1301"
        "/subSUB2:SAPLMEGUI:3303"
        "/tabsREQ_ITEM_DETAIL/tabpTABREQDT8"
        "/ssubTABSTRIPCONTROL1SUB:SAPLMEGUI:3323"
        "/subSUB0:SAPLMEGUI:3324"
        "/subSUB0:SAPLMEGUI:3322"
        "/ctxtMEREQ3322-FLIEF"
    )
    forn_field = session.findById(base_forn)
    forn_field.text = fornecedor
    forn_field.setFocus()
    forn_field.caretPosition = len(fornecedor)
    _send_enter(session)
    _wait(0.5)


# ---------------------------------------------------------------------------
# Passo 4 – Copiar a linha 0 N-1 vezes (loop dinâmico)
# ---------------------------------------------------------------------------

def _copiar_linhas(session, quantidade: int) -> None:
    """
    Copia a linha 0 repetidamente até ter `quantidade` linhas no total.
    A cada iteração seleciona a última linha criada e pressiona &MEREQCOPY,
    o que insere sempre uma nova linha ao final.
    """
    _log(f"📋 Copiando linha base {quantidade - 1} vez(es) para criar {quantidade} itens no total...")

    for i in range(quantidade - 1):
        linha_origem = i          # sempre copia a última linha inserida (equivale ao índice atual)
        grid = _grid(session)
        grid.currentCellColumn = ""
        grid.selectedRows = str(linha_origem)
        grid.pressToolbarButton("&MEREQCOPY")
        _wait(0.3)
        _log(f"  ✅ Cópia {i + 1}/{quantidade - 1} – linha {linha_origem} → linha {i + 1}")


# ---------------------------------------------------------------------------
# Passo 5 – Atualizar o PREIS de cada linha copiada (linhas 1 a N-1)
# ---------------------------------------------------------------------------

def _atualizar_precos(session, ctes: list[dict]) -> None:
    """
    Percorre as linhas copiadas (índice 1 em diante) e atualiza o PREIS
    individualmente. O scroll é feito via firstVisibleRow + currentCellRow.
    """
    _log("💰 Atualizando preços individualmente...")

    for idx, cte in enumerate(ctes):
        grid = _grid(session)
        grid.currentCellRow = idx
        grid.firstVisibleRow = idx
        grid.modifyCell(idx, "PREIS", cte["valor"])
        _wait(0.2)
        _log(f"  💲 Linha {idx} – CTE {cte['numero']} – PREIS={cte['valor']}")

    # Confirma a última edição
    _grid(session).pressEnter()
    _wait(0.5)


# ---------------------------------------------------------------------------
# Passo 6 – Desmarcar WEPOS em todas as linhas copiadas (loop)
# ---------------------------------------------------------------------------

def _desmarcar_wepos_todos(session, quantidade: int) -> None:
    """
    Para cada linha de 1 a N-1 (as copiadas), navega até ela e desmarca o flag
    WEPOS, depois pressiona o botão de navegação para ir ao próximo item.
    """
    _log(f"🚫 Desmarcando flag WEPOS em {quantidade} linhas...")

    btn_nav = (
        "wnd[0]/usr/subSUB0:SAPLMEGUI:0015"
        "/subSUB3:SAPLMEVIEWS:1100"
        "/subSUB2:SAPLMEVIEWS:1200"
        "/subSUB1:SAPLMEGUI:1301"
        "/subSUB1:SAPLMEGUI:6000"
        "/btn%#AUTOTEXT002"
    )
    chk_path = (
        "wnd[0]/usr/subSUB0:SAPLMEGUI:0015"
        "/subSUB3:SAPLMEVIEWS:1100"
        "/subSUB2:SAPLMEVIEWS:1200"
        "/subSUB1:SAPLMEGUI:1301"
        "/subSUB2:SAPLMEGUI:3303"
        "/tabsREQ_ITEM_DETAIL/tabpTABREQDT6"
        "/ssubTABSTRIPCONTROL1SUB:SAPLMEGUI:3320"
        "/chkMEREQ3320-WEPOS"
    )
    tab_rem = (
        "wnd[0]/usr/subSUB0:SAPLMEGUI:0015"
        "/subSUB3:SAPLMEVIEWS:1100"
        "/subSUB2:SAPLMEVIEWS:1200"
        "/subSUB1:SAPLMEGUI:1301"
        "/subSUB2:SAPLMEGUI:3303"
        "/tabsREQ_ITEM_DETAIL/tabpTABREQDT6"
    )

    for i in range(quantidade):
        # Garante que a aba de Remessa está selecionada
        try:
            session.findById(tab_rem).select()
        except Exception:
            pass

        chk = session.findById(chk_path)
        if chk.selected:
            chk.selected = False
            chk.setFocus()
            _log(f"  ✅ Linha {i}: WEPOS desmarcado")
        else:
            _log(f"  ℹ️  Linha {i}: WEPOS já desmarcado")

        # Navega para o próximo item (exceto na última linha)
        if i < quantidade - 1:
            session.findById(btn_nav).press()
            _wait(0.3)


# ---------------------------------------------------------------------------
# Passo 7 – Adicionar anexo
# ---------------------------------------------------------------------------

def _adicionar_anexo(session, caminho: str, arquivo: str) -> None:
    """
    Abre o gerenciador de anexos SAP e faz upload do arquivo informado.
    Assume que o diálogo de seleção de arquivo chega em wnd[3] (caminho + arquivo).
    """
    _log(f"📎 Adicionando anexo: {arquivo}...")

    try:
        # Abre os Serviços de Objeto
        session.findById("wnd[0]/mbar/menu[3]/menu[5]").select()
        _wait(0.5)

        shell_sv = session.findById("wnd[0]/shellcont/shell")
        shell_sv.pressContextButton("CREATE_ATTA")
        shell_sv.pressContextButton("CREATE_ATTA")
        shell_sv.selectContextMenuItem("PCATTA_CREA")
        _wait(0.5)

        # Navega até o diálogo de arquivo (F4 duas vezes para ir de wnd[1] para wnd[3])
        """session.findById("wnd[1]").sendVKey(4)   # F4 → abre wnd[2]
        _wait(0.3)
        session.findById("wnd[2]").sendVKey(4)   # F4 → abre wnd[3]
        _wait(0.3)"""

        # Preenche caminho e nome do arquivo
        session.findById("wnd[1]/usr/ctxtDY_PATH").text = caminho
        session.findById("wnd[1]/usr/ctxtDY_FILENAME").text = arquivo
        session.findById("wnd[1]/usr/ctxtDY_FILENAME").caretPosition = len(arquivo)

        # ── Loop de confirmação ──────────────────────────────────────────────
        # O SAP pode abrir janelas intermediárias (wnd[4], wnd[5]) antes de
        # confirmar. Pressionamos OK em cada janela ativa até a sbar mostrar
        # "Documento criado" ou até atingir o limite de tentativas.
        MAX_TENTATIVAS = 10
        confirmado = False

        for tentativa in range(1, MAX_TENTATIVAS + 1):
            _wait(0.4)

            # Verifica se o SAP já confirmou na barra de status
            try:
                sbar_text = session.findById("wnd[0]/sbar").text or ""
                if "documento criado" in sbar_text.lower() or "document created" in sbar_text.lower():
                    _log(f"  ✅ Confirmação SAP: '{sbar_text}' (tentativa {tentativa})")
                    confirmado = True
                    break
            except Exception:
                pass

            # Descobre qual é a janela mais alta ainda aberta e pressiona OK/Enter
            for wnd_idx in range(5, 2, -1):   # tenta wnd[5] → wnd[4] → wnd[3]
                try:
                    session.findById("wnd[1]/tbar[0]/btn[0]").press()
                    # Tenta botão OK (btn[0]) primeiro; se não existir, manda Enter
                    try:
                        wnd.findById("tbar[0]/btn[0]").press()
                        _log(f"  🔄 Tentativa {tentativa}: OK em wnd[{wnd_idx}]")
                    except Exception:
                        wnd.sendVKey(0)
                        _log(f"  🔄 Tentativa {tentativa}: Enter em wnd[{wnd_idx}]")
                    break   # processa só a janela mais alta por vez
                except Exception:
                    continue  # janela não existe, tenta a de baixo

        if not confirmado:
            _log(f"  ⚠️ Anexo: confirmação 'Documento criado' não detectada após {MAX_TENTATIVAS} tentativas.")

    except Exception as e:
        _log(f"  ❌ Erro ao adicionar anexo: {e}")

    finally:
        # Fecha o painel de Serviços de Objeto se ainda estiver aberto
        try:
            session.findById("wnd[0]/shellcont").close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Passo 8 – Salvar e capturar número da RC
# ---------------------------------------------------------------------------

def _salvar_rc(session) -> str:
    """Salva a RC (Ctrl+S / btn[11]) e retorna o número gerado pelo SAP."""
    _log("💾 Salvando RC...")
    session.findById("wnd[0]/tbar[0]/btn[11]").press()
    _wait(1)

    try:
        numero_rc = session.findById("wnd[0]/sbar").text
        _log(f"  ✅ RC salva! Mensagem SAP: {numero_rc}")
        return numero_rc
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Função pública principal
# ---------------------------------------------------------------------------

def criar_rc_cte(
    session,
    ctes: list[dict],
    centro_custo: str,
    fornecedor: str,
    material: str = "CTE.16.04",
    planta: str = "p716",
    data_hoje: str | None = None,
    caminho_anexo: str = "",
    arquivo_anexo: str = "",
    tipo_imputacao: str = "K",
    tipo_doc: str = "NB",
    prefixo_cabecalho: str = "Fretes GELOG",
    salvar: bool = True,
) -> str:
    """
    Cria uma RC no SAP ME51N para os CTEs informados.

    Parâmetros
    ----------
    session          : objeto SAP GUI (win32com)
    ctes             : lista de dicts com chaves 'numero' e 'valor'
                       ex: [{"numero": "562847", "valor": "2.664,78"}, ...]
    centro_custo     : código do centro de custo (ex: "AQ203")
    fornecedor       : código do fornecedor preferencial (ex: "9190617")
    material         : código do material (padrão "CTE.16.04")
    planta           : código da planta/centro (padrão "p716")
    data_hoje        : data no formato DDMMYYYY; se None usa data atual
    caminho_anexo    : caminho do diretório do arquivo de anexo
    arquivo_anexo    : nome do arquivo de anexo
    tipo_imputacao   : "K" para Centro de Custo, "F" para Ordem de Investimento
    tipo_doc         : tipo de documento SAP (padrão "NB")
    prefixo_cabecalho: texto que precede a lista de CTEs no cabeçalho
    salvar           : se True executa o save; se False apenas preenche (modo teste)

    Retorna
    -------
    str : mensagem da barra de status SAP com o número da RC (ou "" em caso de erro)
    """
    if not ctes:
        raise ValueError("Lista de CTEs não pode ser vazia.")

    # Data padrão = hoje
    if not data_hoje:
        data_hoje = datetime.date.today().strftime("%d%m%Y")

    quantidade = len(ctes)
    _log(f"🚀 Iniciando criação de RC para {quantidade} CTE(s): {[c['numero'] for c in ctes]}")

    # ----- Passo 1: Abrir ME51N -----
    _abrir_me51n(session, tipo_doc)

    # ----- Passo 2: Cabeçalho -----
    _preencher_cabecalho(session, ctes, prefixo_cabecalho)

    # ----- Passo 3: Linha 0 (primeira, completa) -----
    _preencher_linha_0(
        session,
        cte=ctes[0],
        planta=planta,
        material=material,
        tipo_imputacao=tipo_imputacao,
        data_hoje=data_hoje,
        centro_custo=centro_custo,
        fornecedor=fornecedor,
    )

    # ----- Passo 4: Copiar linha base N-1 vezes -----
    if quantidade > 1:
        _copiar_linhas(session, quantidade)

    # ----- Passo 5: Atualizar preços em todas as linhas -----
    _atualizar_precos(session, ctes)

    # ----- Passo 6: Desmarcar WEPOS em todas as linhas copiadas -----
    """if quantidade > 1:
        _desmarcar_wepos_todos(session, quantidade)"""

    # ----- Passo 7: Anexo (opcional) -----
    if caminho_anexo and arquivo_anexo:
        _adicionar_anexo(session, caminho_anexo, arquivo_anexo)

    # ----- Passo 8: Salvar -----
    numero_rc = ""
    if salvar:
        numero_rc = _salvar_rc(session)
    else:
        _log("⚠️  MODO TESTE – RC NÃO salva (salvar=False).")

    _log(f"✅ Processo finalizado. RC: {numero_rc}")
    return numero_rc


# ---------------------------------------------------------------------------
# Execução standalone (para testes rápidos)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import win32com.client

    SapGuiAuto = win32com.client.GetObject("SAPGUI")
    application = SapGuiAuto.GetScriptingEngine
    connection = application.Children(0)
    session = connection.Children(0)

    # ------------------------------------------------------------------
    # Edite esta lista com os CTEs e seus valores reais antes de executar
    # ------------------------------------------------------------------
    CTES = [
        {"numero": "562847", "valor": "2.664,78"},
        {"numero": "573186", "valor": "5.782,15"},
        {"numero": "573187", "valor": "5.782,15"},
        {"numero": "573188", "valor": "5.782,15"},
        {"numero": "573190", "valor": "5.782,15"},
        {"numero": "573191", "valor": "5.782,15"},
        {"numero": "573192", "valor": "5.782,15"},
        {"numero": "573194", "valor": "5.782,15"},
        {"numero": "573195", "valor": "5.782,15"},
    ]

    rc = criar_rc_cte(
        session=session,
        ctes=CTES,
        centro_custo="AQ203",
        fornecedor="9190617",
        material="CTE.16.04",
        planta="p716",
        # data_hoje=None,  # None = usa data de hoje automaticamente
        caminho_anexo=r"C:\Users\ismael.nascimento\Downloads\ "[:-1],  # barra simples no final
        arquivo_anexo="Tabela_Cabotagem_2026.xlsx",
        tipo_imputacao="K",
        salvar=True,
    )

    print(f"\nRC gerada: {rc}")
