import pandas as pd

from src.expedicao.cabotagem_processador import montar_relatorio_cabotagem


def test_montar_relatorio_cabotagem_gera_linhas_por_remessa():
    estado = {
        "containers": [
            {
                "carga": "C-100",
                "container": "CTR-1",
                "remessas": ["R1", "R2"],
                "of_numero": "OF123",
            },
            {
                "carga": "C-100",
                "container": "CTR-2",
                "remessas": ["R3"],
                "of_numero": "",
            },
        ]
    }

    df = montar_relatorio_cabotagem(estado)

    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["Carga", "Container", "Remessa", "OF", "Status"]
    assert len(df) == 3
    assert df.loc[df["Remessa"] == "R1", "OF"].iloc[0] == "OF123"
    assert df.loc[df["Remessa"] == "R3", "Status"].iloc[0] == "Pendente"


def test_montar_relatorio_cabotagem_filtra_selecionados():
    estado = {
        "containers": [
            {
                "carga": "C-100",
                "container": "CTR-1",
                "remessas": ["R1"],
                "of_numero": "610001",
            },
            {
                "carga": "C-200",
                "container": "CTR-2",
                "remessas": ["R2"],
                "of_numero": "610002",
            },
        ],
        "selecionados": ["C-100_CTR-1"]
    }

    df = montar_relatorio_cabotagem(estado)
    assert len(df) == 1
    assert df.iloc[0]["Carga"] == "C-100"
    assert df.iloc[0]["OF"] == "610001"


def test_montar_relatorio_cabotagem_sanitiza_dict_of():
    dict_of = {'of_numero': '6100320038', 'remessas_confirmadas': ['80741343'], 'remessas_ausentes': []}
    str_dict_of = "{'of_numero': '6100320038', 'remessas_confirmadas': ['80741343'], 'remessas_ausentes': []}"

    estado = {
        "containers": [
            {
                "carga": "C-100",
                "container": "CTR-1",
                "remessas": ["R1"],
                "of_numero": dict_of,
            },
            {
                "carga": "C-200",
                "container": "CTR-2",
                "remessas": ["R2"],
                "of_numero": str_dict_of,
            },
        ]
    }

    df = montar_relatorio_cabotagem(estado)
    assert len(df) == 2
    assert df.iloc[0]["OF"] == "6100320038"
    assert df.iloc[1]["OF"] == "6100320038"

