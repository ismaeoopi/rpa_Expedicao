"""
Testes automatizados para o processo SAP de estoque (com e sem planilha)
e utilitários de conexão SAP.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Garantir raiz no sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.sap_utils import conectar_sap
from src.estoque.processo_sap import processo_estoque_sem_planilha, executar_processo_sap_direto


class TestProcessoSap(unittest.TestCase):

    @patch("win32com.client.GetObject")
    def test_conectar_sap_erro_sintaxe_com(self, mock_get_object):
        """Valida que o erro COM -2147221020 (Invalid syntax) é tratado e retorna None."""
        class MockComError(Exception):
            def __init__(self):
                self.args = (-2147221020, "Invalid syntax", None, None)

        mock_get_object.side_effect = MockComError()

        with patch("src.utils.sap_utils._garantir_desktop_interativo"):
            resultado = conectar_sap()
            self.assertIsNone(resultado)

    @patch("src.estoque.processo_sap.conectar_sap")
    @patch("src.utils.db.criar_novo_lote")
    @patch("src.utils.db.inserir_item")
    @patch("src.utils.db.atualizar_item")
    @patch("src.utils.db.buscar_itens_por_lote")
    @patch("src.utils.db.concluir_lote")
    def test_processo_sem_planilha_sem_conexao_sap_nao_lanca_unbound_local(
        self,
        mock_concluir,
        mock_buscar,
        mock_atualizar,
        mock_inserir,
        mock_criar,
        mock_conectar,
    ):
        """
        Valida que a ausência de conexão SAP não causa UnboundLocalError
        com 'caminho_temp_excel' e o processo trata o erro por item.
        """
        mock_conectar.return_value = None
        mock_criar.return_value = 1
        mock_inserir.return_value = 101
        mock_buscar.return_value = [
            {"id": 101, "status_etapa": "ERRO_GERAL"}
        ]

        # Não deve lançar UnboundLocalError
        try:
            processo_estoque_sem_planilha(
                vl32_list=["181299189"],
                ponto_partida=1,
                op_global="12345",
                migo_global="",
                lote_id=None,
            )
        except UnboundLocalError as e:
            self.fail(f"processo_estoque_sem_planilha lançou UnboundLocalError: {e}")

        # Deve ter atualizado o status do item para erro geral
        mock_atualizar.assert_any_call(101, status_etapa="ERRO_GERAL")

    @patch("src.estoque.processo_sap.conectar_sap")
    def test_executar_processo_sap_direto_sem_conexao(self, mock_conectar):
        """Valida que executar_processo_sap_direto retorna False graciosamente sem conexão."""
        mock_conectar.return_value = None
        sucesso = executar_processo_sap_direto("181299189")
        self.assertFalse(sucesso)


if __name__ == "__main__":
    unittest.main()
