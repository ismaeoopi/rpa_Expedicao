import os
import win32gui, win32con
from datetime import datetime

from src.utils.common import log_sys
from src.estoque.msc import executar_msc1n, executar_msc2n, ajustar_fator
from src.estoque.migo import executar_transferencia_migo, executar_migo_zp1
from src.estoque.prdi import executar_prdi
from src.estoque.processo_completo import processo_completo
from src.estoque.brid import brid
from src.estoque.mon import localizarMon

def main():
    usuario_completo = os.getlogin()
    primeiro_nome = usuario_completo.split('.')[0].capitalize()
    hora_atual = datetime.now().hour
    if 5 <= hora_atual < 12:
        saudacao = "Bom dia"
    elif 12 <= hora_atual < 18:
        saudacao = "Boa tarde"
    else:
        saudacao = "Boa noite"

    while True:
        log_sys.write(f"""
            =========================================
            RPA ESTOQUE - V.1.1.1
            =========================================
            {saudacao}, {primeiro_nome}, o que vamos fazer hoje?

            1) Criar e Alterar Lote (MSC1N / MSC2N)
            2) MIGO (311, 411, ZP1)
            3) PRDI
            4) PROCESSO COMPLETO (Via Packing List)
            ⚠️  Obs: Obrigatório colunas "ACABADO" e "LOTE"
            5) BRIDGE 🏁
            6) Localizar Mon
            
            0) Sair
            """)
        try:
            opt = int(input("Opção: "))
        except: continue

        if opt == 0: break
        
        filtro_excel = "Arquivos Excel\0*.xlsx;.xls\0Todos os arquivos\0.*\0\0"
        caminho, _, _ = win32gui.GetOpenFileNameW(
            Title="Selecione o arquivo Excel",
            Filter=filtro_excel,
            Flags=win32con.OFN_FILEMUSTEXIST | win32con.OFN_PATHMUSTEXIST
        )

        if not caminho: continue

        if opt == 1:
            log_sys.write("1) Criar\n2) Alterar\n3) Ajustar Fator")
            sub = int(input("Opção: "))
            if sub == 1: executar_msc1n(caminho)
            elif sub == 2: executar_msc2n(caminho)
            elif sub == 3: ajustar_fator(caminho)
        
        elif opt == 2:
            log_sys.write("1) 311 e 411\n2) ZP1")
            sub = int(input("Opção: "))
            if sub == 1: executar_transferencia_migo(caminho)
            elif sub == 2: executar_migo_zp1(caminho)

        elif opt == 3:
            executar_prdi(caminho)

        elif opt == 4:
            processo_completo(caminho)

        elif opt == 5:
            brid(caminho)

        elif opt == 6:
            localizarMon(caminho)

if __name__ == "__main__":
    main()
