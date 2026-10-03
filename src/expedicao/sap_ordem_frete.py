"""
Módulo legado sap_ordem_frete.py mantido para retrocompatibilidade.
A lógica de criação de Ordem de Frete (OF) foi unificada no motor universal em:
src.expedicao.sap_cabotagem_playwright.py
"""

from src.expedicao.sap_cabotagem_playwright import (
    SAP_FO_URL,
    aguardar_fim_carregamento_sap,
    preencher_campo_por_titulo,
    rodar_criacao_of_playwright,
    rodar_criacao_of_playwright_multipla,
    rodar_criacao_of_cabotagem_playwright,
)

__all__ = [
    "SAP_FO_URL",
    "aguardar_fim_carregamento_sap",
    "preencher_campo_por_titulo",
    "rodar_criacao_of_playwright",
    "rodar_criacao_of_playwright_multipla",
    "rodar_criacao_of_cabotagem_playwright",
]
