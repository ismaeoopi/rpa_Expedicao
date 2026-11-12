import io
import os
import unittest
from unittest.mock import patch

import pandas as pd
from openpyxl import Workbook

import Entreposto


class TestNormalizacaoCargas(unittest.TestCase):
    def test_preserva_ids_alfanumericos(self):
        serie = pd.Series([" IT21/10-26 ", "IT03/10-26", None, ""])

        resultado = Entreposto.normalizar_cargas(serie).tolist()

        self.assertEqual(resultado, ["IT21/10-26", "IT03/10-26", "", ""])

    def test_mantem_regra_para_prefixo_numerico(self):
        serie = pd.Series(["380787/10", " 380788 / 20 ", "380789"])

        resultado = Entreposto.normalizar_cargas(serie).tolist()

        self.assertEqual(resultado, ["380787", "380788", "380789"])


class TestCachePlanilhas(unittest.TestCase):
    def setUp(self):
        Entreposto.limpar_cache_planilhas()
        self.downloads = []

    def tearDown(self):
        Entreposto.limpar_cache_planilhas()

    def baixar_arquivo(self, caminho):
        self.downloads.append(caminho)
        return caminho.encode("utf-8")

    @staticmethod
    def ler_planilha(
        conteudo,
        _descricao,
        _entreposto,
        aba_configurada=None,
    ):
        origem = conteudo.decode("utf-8")
        return pd.DataFrame({"origem": [origem]}), "Dados"

    def test_reutiliza_copias_independentes(self):
        ambiente = {
            "PLANILHA_ITAJAI_1": "cargas.xlsx",
            "PLANILHA_ITAJAI_2": "estoque.xlsx",
        }
        with (
            patch.dict(os.environ, ambiente),
            patch.object(
                Entreposto.SharePointClient,
                "baixar_arquivo",
                self.baixar_arquivo,
            ),
            patch.object(
                Entreposto,
                "_ler_planilha_excel_limitada",
                self.ler_planilha,
            ),
        ):
            primeiro = Entreposto.carregar_planilhas_em_memoria("ITAJAI")
            segundo = Entreposto.carregar_planilhas_em_memoria(
                "ITAJAI", usar_cache=True
            )
            segundo["Planilha de Cargas"].loc[0, "origem"] = "alterado"
            terceiro = Entreposto.carregar_planilhas_em_memoria(
                "ITAJAI", usar_cache=True
            )

        self.assertEqual(self.downloads, ["cargas.xlsx", "estoque.xlsx"])
        self.assertEqual(
            primeiro["Planilha de Cargas"].loc[0, "origem"], "cargas.xlsx"
        )
        self.assertEqual(
            terceiro["Planilha de Cargas"].loc[0, "origem"], "cargas.xlsx"
        )

    def test_cache_vencido_volta_ao_sharepoint(self):
        ambiente = {
            "PLANILHA_ITAJAI_1": "cargas.xlsx",
            "PLANILHA_ITAJAI_2": "estoque.xlsx",
        }
        relogio = iter(
            [100.0, 100.0 + Entreposto._CACHE_TTL_SEGUNDOS + 1, 701.0]
        )
        with (
            patch.dict(os.environ, ambiente),
            patch.object(
                Entreposto.SharePointClient,
                "baixar_arquivo",
                self.baixar_arquivo,
            ),
            patch.object(
                Entreposto,
                "_ler_planilha_excel_limitada",
                self.ler_planilha,
            ),
            patch.object(Entreposto.time, "monotonic", lambda: next(relogio)),
        ):
            Entreposto.carregar_planilhas_em_memoria("ITAJAI")
            Entreposto.carregar_planilhas_em_memoria("ITAJAI", usar_cache=True)

        self.assertEqual(
            self.downloads,
            ["cargas.xlsx", "estoque.xlsx", "cargas.xlsx", "estoque.xlsx"],
        )


class TestCruzamentoCargas(unittest.TestCase):
    def test_soma_cargas_ausentes_sem_alterar_identificadores(self):
        cargas = pd.DataFrame(
            {
                "N° da Carga": [
                    "IT21/10-26",
                    "IT21/10-26",
                    "380787/10",
                    "380787/10",
                ],
                "Remessa": [None, "", None, ""],
                "Peso Liq": ["100,5", "49,5", "20", "30"],
                "Pllt": ["2", "1", "1", "2"],
            }
        )
        estoque = pd.DataFrame(
            {
                "Carga": ["OUTRA"],
                "Peso Líq": ["1"],
                "Peso Br": ["1"],
            }
        )

        with patch.object(
            Entreposto,
            "carregar_planilhas_em_memoria",
            return_value={
                "Planilha de Cargas": cargas,
                "Planilha de Estoque": estoque,
            },
        ):
            self.assertTrue(Entreposto.executar_automacao_entreposto("ITAJAI"))

        por_carga = {
            item["carga"]: item for item in Entreposto.ultimo_resultado["cargas"]
        }
        self.assertEqual(set(por_carga), {"IT21/10-26", "380787"})
        self.assertEqual(por_carga["IT21/10-26"]["peso_liquido"], 150.0)
        self.assertEqual(por_carga["IT21/10-26"]["qtd_paletes"], 3)
        self.assertEqual(por_carga["380787"]["peso_liquido"], 50.0)
        self.assertEqual(por_carga["380787"]["qtd_paletes"], 3)


class TestLeituraExcelLimitada(unittest.TestCase):
    def test_ignora_dimensao_artificial_ate_xfd(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Dados da carga"
        worksheet.append(["N° da Carga", "Peso Liq"])
        worksheet.append(["IT21/10-26", 123.5])
        worksheet["XFD2"] = "formatação excedente"
        conteudo = io.BytesIO()
        workbook.save(conteudo)
        workbook.close()

        dataframe, aba = Entreposto._ler_planilha_excel_limitada(
            conteudo.getvalue(), "Planilha de Cargas", "ITAJAI"
        )

        self.assertEqual(aba, "Dados da carga")
        self.assertEqual(list(dataframe.columns), ["N° da Carga", "Peso Liq"])
        self.assertEqual(dataframe.loc[0, "N° da Carga"], "IT21/10-26")
        self.assertEqual(dataframe.loc[0, "Peso Liq"], "123.5")


if __name__ == "__main__":
    unittest.main()
