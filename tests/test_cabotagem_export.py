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
    assert list(df.columns) == ["Carga", "Container", "Remessa", "Data Ag. Recebimento Cliente", "OF", "Status"]
    assert len(df) == 3
    assert df.loc[df["Remessa"] == "R1", "OF"].iloc[0] == "OF123"
    assert df.loc[df["Remessa"] == "R3", "Status"].iloc[0] == "Pendente"


def test_montar_relatorio_cabotagem_inclui_data_agendamento_cliente():
    estado = {
        "containers": [
            {
                "carga": "C-100",
                "container": "CTR-1",
                "remessas": ["R1"],
                "of_numero": "610001",
                "data_agendamento": "28/09/2026",
            },
            {
                "carga": "C-200",
                "container": "CTR-2",
                "remessas": ["R2"],
                "of_numero": "610002",
                "data_agendamento": "29/09/2026",
            }
        ]
    }

    df = montar_relatorio_cabotagem(estado)
    assert "Data Ag. Recebimento Cliente" in df.columns
    assert df.loc[df["Container"] == "CTR-1", "Data Ag. Recebimento Cliente"].iloc[0] == "28/09/2026"
    assert df.loc[df["Container"] == "CTR-2", "Data Ag. Recebimento Cliente"].iloc[0] == "29/09/2026"



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


def test_montar_relatorio_cabotagem_diferencia_remessas_ausentes():
    estado = {
        "containers": [
            {
                "carga": "C-100",
                "container": "CTR-1",
                "remessas": ["111", "222", "333"],
                "of_numero": "6100001234",
            }
        ],
        "status_etapas": {
            "C-100_CTR-1": {
                "of": "success",
                "of_numero": "6100001234",
                "remessas_confirmadas": ["111", "222"],
                "remessas_ausentes": ["333"],
            }
        }
    }

    df = montar_relatorio_cabotagem(estado)

    assert len(df) == 3
    
    r111 = df[df["Remessa"] == "111"].iloc[0]
    assert r111["OF"] == "6100001234"
    assert r111["Status"] == "Gerada"

    r222 = df[df["Remessa"] == "222"].iloc[0]
    assert r222["OF"] == "6100001234"
    assert r222["Status"] == "Gerada"

    r333 = df[df["Remessa"] == "333"].iloc[0]
    assert r333["OF"] == ""
    assert r333["Status"] == "Não Encontrada"


def test_formatar_data_abreviada_varios_formatos():
    from src.expedicao.cabotagem_processador import formatar_data_abreviada

    # Formato ISO com e sem hora
    fmt, iso = formatar_data_abreviada("2026-09-30 00:00:00")
    assert fmt == "30/09/2026"
    assert iso == "2026-09-30"

    fmt, iso = formatar_data_abreviada("2026-09-28")
    assert fmt == "28/09/2026"
    assert iso == "2026-09-28"

    # Formato Brasileiro DD/MM/AAAA
    fmt, iso = formatar_data_abreviada("15/10/2026")
    assert fmt == "15/10/2026"
    assert iso == "2026-10-15"

    # Serial do Excel (45565 -> 30/09/2024)
    fmt, iso = formatar_data_abreviada("45565")
    assert fmt == "30/09/2024"
    assert iso == "2024-09-30"

    # Valores nulos / vazios
    fmt, iso = formatar_data_abreviada(None)
    assert fmt == ""
    assert iso == ""

    fmt, iso = formatar_data_abreviada("nan")
    assert fmt == ""
    assert iso == ""

    fmt, iso = formatar_data_abreviada("-")
    assert fmt == ""
    assert iso == ""



