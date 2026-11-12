"""
Testes automatizados para a funcionalidade de Estorno de Ordem de Frete (OF).
Utiliza dados de teste em memória e unittest.mock para simular chamadas externas ao SAP.
"""

import os
import sys
import io

# Garantir raiz no sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import openpyxl
from unittest.mock import MagicMock, patch

from src.expedicao.sap_estorno_of import (
    carregar_dados_estorno_planilha,
    atualizar_planilha_estorno,
    localizar_documento_81,
    processar_estorno_of_na_pagina,
)
from src.expedicao.estorno_of_processador import (
    obter_dados_estorno,
    montar_relatorio_estorno,
    estorno_of_estado,
)


def planilha_teste_bytes():
    """Gera uma pasta de trabalho Excel em memória simulando as abas Base e Estornos."""
    wb = openpyxl.Workbook()

    # Aba Base
    ws_base = wb.active
    ws_base.title = "Base"
    ws_base.append(["Detalhes", "", "", "", "", "", "", "", "", "", ""])
    ws_base.append([])
    ws_base.append(["Empresa", "Chave", "Status", "Documento de compras", "Item", "Atribuição", "Nº doc", "Divisão", "Tipo", "Ref", "Ordem"])
    ws_base.append([])
    ws_base.append(["VMG", "61003172974500745542", "Provisão Antiga", "4500745542", "10", "20260722", "100325837", "", "AB", "", 6100317297])
    ws_base.append(["VMG", "61003194634500751841", "Provisão Antiga", "4500751841", "10", "20260730", "100336696", "", "AB", "", 6100319463])

    # Aba Estornos
    ws_estornos = wb.create_sheet(title="Estornos ")
    ws_estornos.append(["OF", "Status"])
    ws_estornos.append([6100317297, "True"])
    ws_estornos.append([6100319463, "True"])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


def test_carregar_dados_estorno_planilha(tmp_path, planilha_teste_bytes):
    """Testa se a leitura da planilha mapeia corretamente as OFs aos Documentos de Compras."""
    caminho = tmp_path / "planilha_teste.xlsx"
    caminho.write_bytes(planilha_teste_bytes)

    itens = carregar_dados_estorno_planilha(str(caminho))

    assert len(itens) == 2
    assert itens[0]["of_numero"] == "6100317297"
    assert itens[0]["doc_compras"] == "4500745542"
    assert itens[1]["of_numero"] == "6100319463"
    assert itens[1]["doc_compras"] == "4500751841"


def test_atualizar_planilha_estorno(tmp_path, planilha_teste_bytes):
    """Testa se os resultados de estorno são salvos na aba Estornos com formatação e colunas adicionais."""
    caminho = tmp_path / "planilha_teste.xlsx"
    caminho.write_bytes(planilha_teste_bytes)

    resultados_mock = [
        {
            "of_numero": "6100317297",
            "doc_compras": "4500745542",
            "doc_81": "8100331000",
            "sucesso": True,
            "status_estorno": "Sucesso",
            "life_cycle_status": "Cancellation Requested",
            "severidade": "Green LED / Success",
            "logs": "Documento cancelado com êxito",
        },
        {
            "of_numero": "6100319463",
            "doc_compras": "4500751841",
            "doc_81": "8100331744",
            "sucesso": False,
            "status_estorno": "Erro",
            "life_cycle_status": "Posted",
            "severidade": "Red LED / Error",
            "logs": "[Error] Vendor BPP716 has not been...",
        }
    ]

    atualizar_planilha_estorno(str(caminho), resultados_mock)

    wb = openpyxl.load_workbook(str(caminho), data_only=True)
    assert "Estornos " in wb.sheetnames
    ws = wb["Estornos "]

    # Verificar cabeçalho
    header = [c for c in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
    assert "OF" in header
    assert "Status Estorno" in header
    assert "Doc 81 (FSD)" in header

    # Verificar dados das linhas
    rows = list(ws.iter_rows(min_row=2, max_row=3, values_only=True))
    assert str(rows[0][0]) == "6100317297"
    assert rows[0][1] == "Sucesso"
    assert str(rows[0][3]) == "8100331000"

    assert str(rows[1][0]) == "6100319463"
    assert rows[1][1] == "Erro"
    assert str(rows[1][3]) == "8100331744"


def test_localizar_documento_81_com_evaluate():
    """Testa a função de localização do documento 81 quando o script evaluate do DOM retorna o número."""
    app_iframe_mock = MagicMock()
    app_iframe_mock.evaluate.return_value = "8100331744"

    doc_81 = localizar_documento_81(app_iframe_mock, "4500751841")
    assert doc_81 == "8100331744"


def test_localizar_documento_81_fallback_regex():
    """Testa a busca do documento 81 via fallback no texto da página caso o evaluate falhe."""
    app_iframe_mock = MagicMock()
    app_iframe_mock.evaluate.side_effect = Exception("Erro DOM")
    app_iframe_mock.get_by_role.return_value.all.return_value = []

    body_mock = MagicMock()
    body_mock.inner_text.return_value = "Texto RF Freight Settlement Type 8100339999 Posted..."
    app_iframe_mock.locator.return_value = body_mock

    doc_81 = localizar_documento_81(app_iframe_mock, "4500751841")
    assert doc_81 == "8100339999"


def test_montar_relatorio_estorno():
    """Testa a geração do DataFrame do relatório de estornos."""
    estado_mock = {
        "status_etapas": {
            "6100319463": {
                "doc_compras": "4500751841",
                "doc_81": "8100331744",
                "status": "success",
                "life_cycle": "Cancellation Requested",
                "severidade": "Green LED",
                "logs": "OK",
                "mensagem": "Sucesso",
            }
        }
    }
    df = montar_relatorio_estorno(estado_mock)
    assert not df.empty
    assert len(df) == 1
    assert df.iloc[0]["Ordem de Frete (OF)"] == "6100319463"
    assert df.iloc[0]["Status"] == "Sucesso"
    assert df.iloc[0]["Documento 81 (FSD)"] == "8100331744"


@patch("src.expedicao.sap_estorno_of.aguardar_fim_carregamento_sap")
@patch("src.expedicao.sap_estorno_of.localizar_documento_81")
@patch("src.expedicao.sap_estorno_of.estornar_fsd_popup")
@patch("src.expedicao.sap_estorno_of.obter_app_iframe")
def test_processar_estorno_of_fluxo_sucesso(mock_obter_iframe, mock_fsd, mock_loc_81, mock_loading):
    """Testa o fluxo de processamento de estorno na página com mocks."""
    mock_loc_81.return_value = "8100331744"
    mock_fsd.return_value = {
        "doc_81": "8100331744",
        "sucesso_salvar": True,
        "severidade": "Green LED / Success",
        "logs_resumo": "[Success] Document reversed",
        "erro_fsd": "",
    }

    page_mock = MagicMock()
    iframe_mock = MagicMock()
    mock_obter_iframe.return_value = iframe_mock

    # Simular campo Freight Order
    input_mock = MagicMock()
    input_mock.count.return_value = 1
    input_mock.is_visible.return_value = True
    iframe_mock.get_by_role.return_value = input_mock

    # Simular status Cancellation Requested encontrado
    status_locator_mock = MagicMock()
    status_locator_mock.count.return_value = 1
    status_locator_mock.first.is_visible.return_value = True
    iframe_mock.get_by_text.return_value = status_locator_mock

    # Simular expect_popup retornando nova página
    page1_mock = MagicMock()
    popup_context_mock = MagicMock()
    popup_context_mock.value = page1_mock
    page_mock.expect_popup.return_value.__enter__.return_value = popup_context_mock

    resultado = processar_estorno_of_na_pagina(page_mock, "6100319463", "4500751841")

    assert resultado["sucesso"] is True
    assert resultado["status_estorno"] == "Sucesso"
    assert resultado["doc_81"] == "8100331744"
    assert resultado["life_cycle_status"] == "Cancellation Requested"


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    print("Executando testes de Estorno de OF...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        bytes_data = planilha_teste_bytes()
        test_carregar_dados_estorno_planilha(tmp_path, bytes_data)
        print("✅ test_carregar_dados_estorno_planilha passou!")

        test_atualizar_planilha_estorno(tmp_path, bytes_data)
        print("✅ test_atualizar_planilha_estorno passou!")

    test_localizar_documento_81_com_evaluate()
    print("✅ test_localizar_documento_81_com_evaluate passou!")

    test_localizar_documento_81_fallback_regex()
    print("✅ test_localizar_documento_81_fallback_regex passou!")

    test_montar_relatorio_estorno()
    print("✅ test_montar_relatorio_estorno passou!")

    test_processar_estorno_of_fluxo_sucesso()
    print("✅ test_processar_estorno_of_fluxo_sucesso passou!")

    print("\n🎉 TODOS OS TESTES PASSARAM COM SUCESSO!")
