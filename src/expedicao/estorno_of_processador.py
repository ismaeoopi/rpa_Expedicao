"""
Processador e gerenciador de estado para a automação de Estorno de OFs.
Mantém o estado da execução em segundo plano para consumo pela interface Web (Flask)
e exportação de relatórios.
"""

import os
import threading
import pandas as pd
from datetime import datetime
from src.utils.common import log_sys
from src.expedicao.sap_estorno_of import (
    carregar_dados_estorno_planilha,
    executar_estorno_of_lote,
    atualizar_planilha_estorno,
)

# Estado global do Estorno de OFs
estorno_of_estado = {
    "planilha_caminho": "",
    "itens": [],             # Lista de dicts com {of_numero, doc_compras, status_anterior, ...}
    "status_etapas": {},      # {of_numero: {"status": "pending|running|success|error", ...}}
    "selecionados": [],       # Lista de OFs selecionadas para executar
    "em_execucao": False,
    "resumo": {
        "total": 0,
        "processados": 0,
        "sucessos": 0,
        "erros": 0,
        "pendentes": 0,
    },
    "data_inicio": "",
    "data_fim": "",
}


def obter_dados_estorno(caminho_excel: str) -> list:
    """
    Carrega os dados de estorno da planilha informada e inicializa o estado global.
    """
    global estorno_of_estado

    log_sys.write(f"📂 Carregando dados de estorno da planilha: {os.path.basename(caminho_excel)}")
    itens = carregar_dados_estorno_planilha(caminho_excel)

    estorno_of_estado["planilha_caminho"] = caminho_excel
    estorno_of_estado["itens"] = itens
    estorno_of_estado["selecionados"] = [it["of_numero"] for it in itens]
    estorno_of_estado["status_etapas"] = {}

    for it in itens:
        of_num = it["of_numero"]
        estorno_of_estado["status_etapas"][of_num] = {
            "status": "pending",
            "of_numero": of_num,
            "doc_compras": it.get("doc_compras", ""),
            "doc_81": "",
            "life_cycle": "",
            "severidade": "",
            "logs": "",
            "mensagem": "",
        }

    estorno_of_estado["resumo"] = {
        "total": len(itens),
        "processados": 0,
        "sucessos": 0,
        "erros": 0,
        "pendentes": len(itens),
    }

    log_sys.write(f"✅ {len(itens)} Ordem(ns) de Frete identificada(s) para estorno.")
    return itens


def _callback_progresso_estorno(idx, total, of_num, status_tipo, res=None):
    """Atualiza o estado em memória conforme cada item é processado."""
    global estorno_of_estado

    if of_num not in estorno_of_estado["status_etapas"]:
        estorno_of_estado["status_etapas"][of_num] = {
            "status": "pending",
            "of_numero": of_num,
            "doc_compras": "",
            "doc_81": "",
            "life_cycle": "",
            "severidade": "",
            "logs": "",
            "mensagem": "",
        }

    etapa = estorno_of_estado["status_etapas"][of_num]

    if status_tipo == "processando":
        etapa["status"] = "running"
    elif status_tipo in ["sucesso", "erro"]:
        sucesso = res.get("sucesso", False) if res else (status_tipo == "sucesso")
        etapa["status"] = "success" if sucesso else "error"
        if res:
            etapa["doc_81"] = res.get("doc_81", "")
            etapa["life_cycle"] = res.get("life_cycle_status", "")
            etapa["severidade"] = res.get("severidade", "")
            etapa["logs"] = res.get("logs", "")
            etapa["mensagem"] = res.get("mensagem", "")

        # Recalcular resumo
        total_p = 0
        sucs = 0
        errs = 0
        for st in estorno_of_estado["status_etapas"].values():
            s = st.get("status")
            if s in ["success", "error"]:
                total_p += 1
                if s == "success":
                    sucs += 1
                else:
                    errs += 1

        estorno_of_estado["resumo"]["processados"] = total_p
        estorno_of_estado["resumo"]["sucessos"] = sucs
        estorno_of_estado["resumo"]["erros"] = errs
        estorno_of_estado["resumo"]["pendentes"] = estorno_of_estado["resumo"]["total"] - total_p


def rodar_estorno_of_background(selecionados: list = None, headless: bool = True):
    """
    Executa o lote de estornos em uma thread separada para não travar a aplicação web.
    """
    global estorno_of_estado

    if estorno_of_estado["em_execucao"]:
        log_sys.write("⚠️ Já existe um processo de estorno em execução.")
        return False

    def _worker():
        global estorno_of_estado
        estorno_of_estado["em_execucao"] = True
        estorno_of_estado["data_inicio"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        try:
            todos_itens = estorno_of_estado["itens"]
            if selecionados:
                itens_alvo = [it for it in todos_itens if it["of_numero"] in selecionados]
            else:
                itens_alvo = todos_itens

            log_sys.write(f"🚀 Iniciando estorno em background de {len(itens_alvo)} OF(s)...")

            executar_estorno_of_lote(
                itens=itens_alvo,
                headless=headless,
                caminho_planilha=estorno_of_estado["planilha_caminho"],
                callback_progresso=_callback_progresso_estorno,
            )

        except Exception as e:
            log_sys.write(f"❌ Erro fatal na thread de estorno de OFs: {e}")
        finally:
            estorno_of_estado["em_execucao"] = False
            estorno_of_estado["data_fim"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            log_sys.write("🏁 Processamento de estornos finalizado.")

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return True


def montar_relatorio_estorno(estado=None) -> pd.DataFrame:
    """Cria um DataFrame com os resultados do estorno para download ou inspeção."""
    estado = estado or estorno_of_estado
    linhas = []

    status_dict = estado.get("status_etapas", {})
    for of_num, st in status_dict.items():
        linhas.append({
            "Ordem de Frete (OF)": of_num,
            "Documento de Compras": st.get("doc_compras", ""),
            "Documento 81 (FSD)": st.get("doc_81", ""),
            "Status": "Sucesso" if st.get("status") == "success" else "Erro" if st.get("status") == "error" else "Pendente",
            "Life Cycle Status": st.get("life_cycle", ""),
            "Severidade": st.get("severidade", ""),
            "Logs": st.get("logs", ""),
            "Mensagem": st.get("mensagem", ""),
        })

    return pd.DataFrame(linhas)

