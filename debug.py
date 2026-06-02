# debug_sap.py
import sys
from src.expedicao.selecao_uc import processarRemessaComUc

# Defina a inbound de teste aqui
INBOUND_TESTE = "181194577"

if __name__ == "__main__":
    # Executa o processador usando o arquivo ROBO.xlsx (nome em maiúsculas)
    processarRemessaComUc("Robo.xlsx")
