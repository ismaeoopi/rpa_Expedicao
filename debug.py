# debug_sap.py
import sys
from src.estoque.processo_sap import executar_processo_sap_direto

# Defina a inbound de teste aqui
INBOUND_TESTE = "181194577"

if __name__ == "__main__":
    executar_processo_sap_direto(INBOUND_TESTE)
