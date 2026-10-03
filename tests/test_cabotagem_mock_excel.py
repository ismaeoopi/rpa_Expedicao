import io
import pandas as pd
from unittest.mock import patch
from src.expedicao.cabotagem_processador import obter_dados_cabotagem, cabotagem_estado

def test_obter_dados_cabotagem_com_data_agendamento():
    mock_data = {
        'CARGA': ['C-001', 'C-001', 'C-002', 'C-003'],
        'CONTAINER': ['CTR-10', 'CTR-11', 'CTR-20', 'CTR-30'],
        'REMESSA': ['REM-1', 'REM-2', 'REM-3', 'REM-4'],
        'CLIENTE': ['Cliente Alpha', 'Cliente Alpha', 'Cliente Beta', 'Cliente Gama'],
        'VALOR FRETE': ['1000', '1000', '2000', '1500'],
        'OF': ['', '', '', ''],
        'Data Ag. Recebimento Cliente': ['2026-09-15 00:00:00', '2026-09-20', '30/09/2026', '2026-09-10']
    }
    df_mock = pd.DataFrame(mock_data)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_mock.to_excel(writer, sheet_name='Cabotagem', index=False)
    binary_content = buffer.getvalue()

    with patch('src.expedicao.cabotagem_processador.SharePointClient') as MockClient:
        instance = MockClient.return_value
        instance.baixar_arquivo.return_value = binary_content
        with patch.dict('os.environ', {'PLANILHA_CABOTAGEM': 'dummy.xlsx', 'PLANILHA_CABOTAGEM_ABA': 'Cabotagem'}):
            cargas = obter_dados_cabotagem()

    assert len(cargas) == 3

    # C-002 tem data 30/09/2026 -> deve ser a primeira (mais recente)
    assert cargas[0]['carga'] == 'C-002'
    assert cargas[0]['data_agendamento'] == '30/09/2026'

    # C-001 tem containers com 15/09 e 20/09 -> a data da carga é 20/09/2026 (mais recente entre seus containers)
    assert cargas[1]['carga'] == 'C-001'
    assert cargas[1]['data_agendamento'] == '20/09/2026'

    # C-003 tem data 10/09/2026 -> mais antiga
    assert cargas[2]['carga'] == 'C-003'
    assert cargas[2]['data_agendamento'] == '10/09/2026'

    # Containers individuais
    c001_containers = {c['container']: c for c in cargas[1]['containers']}
    assert c001_containers['CTR-10']['data_agendamento'] == '15/09/2026'
    assert c001_containers['CTR-11']['data_agendamento'] == '20/09/2026'

if __name__ == '__main__':
    test_obter_dados_cabotagem_com_data_agendamento()
    print('TESTE DE OBTENÇÃO E ORDENAÇÃO PASSOU COM SUCESSO!')
