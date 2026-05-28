import win32com.client as win32
import pandas as pd
import time

def limpar_numero(valor_txt):
    if not valor_txt: return 0.0
    valor_txt = valor_txt.strip().replace('.', '').replace(',', '.')
    try:
        return float(valor_txt)
    except ValueError:
        return 0.0

def extrair_dados_sap(inbound=None):
    try:
        SapGuiAuto = win32.GetObject("SAPGUI")
        application = SapGuiAuto.GetScriptingEngine
        connection = application.Children(0)
        session = connection.Children(0)
    except Exception:
        print("Erro: Certifique-se de que o SAP está aberto na tela correta.")
        return None

    # Navegação inicial
    session.findById("wnd[0]/tbar[0]/okcd").text = "/nvl32n"
    session.findById("wnd[0]").sendVKey(0)
    if not inbound:
        inbound = input("Digite o número do documento de entrada: ")    
    session.findById("wnd[0]/usr/ctxtLIKP-VBELN").text = inbound
    session.findById("wnd[0]").sendVKey(0)
    # Note o 'r' logo antes das aspas iniciais
    semiAcabado = session.findById(r"wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\01/ssubSUBSCREEN_BODY:SAPMV50A:1202/tblSAPMV50ATC_LIPS_OVER_INB/ctxtLIPS-MATNR[1,0]").text
    session.findById("wnd[0]/tbar[1]/btn[18]").press()

    # Caminho base da tabela
    path_tab = "wnd[0]/usr/tabsTS_HU_VERP/tabpUE6INH/ssubTAB:SAPLV51G:6040/tblSAPLV51GTC_HU_005"
    try:

        tabela = session.findById(path_tab)
    except Exception:
        session.findById("wnd[0]/tbar[0]/btn[3]").press()
        session.findById("wnd[0]/usr/tabsTS_HU_VERP/tabpUE6INH").select()
        tabela = session.findById(path_tab)
    
    lista_paletes = []
    lista_lotes = []
    pallet_atual = None
    posicao_absoluta = 0

    print(" Descendo a tabela via scroll... Acompanhe:")

    while True:
        # VERIFICAÇÃO DINÂMICA DO SCROLL

            # Força o scroll a ir para a posição atual
        session.findById("wnd[0]/usr/tabsTS_HU_VERP/tabpUE6INH/ssubTAB:SAPLV51G:6040/tblSAPLV51GTC_HU_005").verticalScrollbar.position = posicao_absoluta

        linha_visual = 0

        # Captura dos dados usando a linha corrigida
        try:
            hierarquia = session.findById(f"{path_tab}/txtHUMV4-HISTU[0,{linha_visual}]").text.strip()
            id_palete = session.findById(f"{path_tab}/txtHUMV4-IDENT[1,{linha_visual}]").text.strip()
            pesoBruto = session.findById(f"{path_tab}/txtHUMV4-BRGEW[9,{linha_visual}]").text.strip()
            pesobob = session.findById(f"{path_tab}/txtHUMV4-QUANTITY[3,{linha_visual}]").text.strip()
            bob = session.findById(f"{path_tab}/txtHUMV4-VOLUM[12,{linha_visual}]").text.strip()
            charg = session.findById(f"{path_tab}/ctxtHUMV4-CHARG[6,{linha_visual}]").text.strip()
        except Exception:
            # Se estourar o limite físico de linhas visíveis da tela do SAP, encerra o loop de forma segura
            print(f" -> [Fim] Limite da tela alcançado na posição {posicao_absoluta}.")
            break

        # CRITÉRIO DE PARADA PRÉVIA: Se a linha atual/próxima estiver completamente sem dados
        if not hierarquia and not id_palete and not pesoBruto:
            print(f" -> [Fim] Próxima linha vazia encontrada na posição {posicao_absoluta}. Encerrando leitura.")
            break

        print(f"   ↳ Lendo Posição {posicao_absoluta:02d} (Linha Visual: {linha_visual}) | Hierarquia: {hierarquia} | ID: {id_palete}")

        # Se a hierarquia for "0", encontramos um NOVO PALETE
        if hierarquia == "0":
            if pallet_atual is not None:
                lista_paletes.append(pallet_atual)  # Salva o palete anterior antes de iniciar o novo
            
            pallet_atual = {
                "ID Palete": id_palete,
                "Semi Acabado": semiAcabado,
                "Peso Bruto Palete": limpar_numero(pesoBruto),
                "Qtd Bobinas": int(limpar_numero(bob)) if bob else 0,
                "Peso Líquido Total (Soma)": 0.0,
                "Lotes": [],
                "peso_bob": 0.0
            }
        
        # Se a hierarquia for "1", pertence ao palete atual (acumula peso líquido e lotes)
        elif hierarquia == "1" and pallet_atual is not None:
            pallet_atual["Peso Líquido Total (Soma)"] += limpar_numero(pesoBruto)
            pallet_atual["peso_bob"] += limpar_numero(pesobob)
            if charg and charg not in pallet_atual["Lotes"]:
                pallet_atual["Lotes"].append(charg)
            
            # Adiciona à lista de lotes individuais
            lista_lotes.append({
                "ID Palete": pallet_atual["ID Palete"],
                "Semi Acabado": pallet_atual["Semi Acabado"],
                "Lotes": charg,
                "peso_bob": limpar_numero(pesobob)
            })

        proxima = session.findById(f"{path_tab}/txtHUMV4-HISTU[0,1]").text.strip()
        if proxima != "1" and proxima != "0":
            print(f" -> [Fim] Próxima linha de detalhes vazia ou sem hierarquia '1' encontrada na posição {posicao_absoluta}. Encerrando leitura.")
            break

        # Incrementa para avançar a tabela no próximo loop
        posicao_absoluta += 1

    # Adiciona o último palete processado após sair do loop principal
    if pallet_atual is not None:
        lista_paletes.append(pallet_atual)

    # Une os lotes coletados em uma string separada por vírgula para o Excel
    for p in lista_paletes:
        p["Lotes"] = ", ".join(p["Lotes"])

    return lista_paletes, lista_lotes

def gerar_relatorios(inbound=None):
    dados_paletes, dados_lotes = extrair_dados_sap(inbound)
    
    if dados_paletes:
        df1 = pd.DataFrame(dados_paletes)
        df2 = pd.DataFrame(dados_lotes) if dados_lotes else pd.DataFrame()
        
        # DF 1 - UC, Peso LIQ, Peso Bruto e nº de bob
        colunas_df1 = ["ID Palete", "Peso Líquido Total (Soma)", "Peso Bruto Palete", "Qtd Bobinas"]
        df1 = df1[colunas_df1].copy()
        df1.rename(columns={
            "ID Palete": "UC", 
            "Peso Líquido Total (Soma)": "Peso LIQ", 
            "Peso Bruto Palete": "Peso Bruto", 
            "Qtd Bobinas": "nº de bob"
        }, inplace=True)
        
        # DF 2 - Somente UC - lote, classificado em ASC pela UC
        if not df2.empty:
            colunas_df2 = ["ID Palete", "Semi Acabado", "Lotes", "peso_bob"]
            df2 = df2[colunas_df2].copy()
            df2.rename(columns={"ID Palete": "UC", "Semi Acabado": "Semi Acabado", "Lotes": "lote", "peso_bob": "peso_bob"}, inplace=True)
            df2 = df2.sort_values(by="UC", ascending=True)
        
        print("\n--- DATAFRAME 1: UC, Peso LIQ, Peso Bruto, nº de bob ---")
        print(df1.to_string(index=False))
        
        print("\n--- DATAFRAME 2: UC, lote (Ordenado por UC ASC) ---")
        print(df2.to_string(index=False))
        
        return df1, df2
    else:
        print("\n[ERRO] Nenhum dado coletado.")
        return None, None

if __name__ == "__main__":
    gerar_relatorios()