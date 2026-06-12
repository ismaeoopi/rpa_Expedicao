import os
import io
import pandas as pd
from dotenv import load_dotenv
from src.utils.common import log_sys
from src.utils.sharepoint import SharePointClient, ENV_PATH

# Estado global da última execução para retornar ao frontend
ultimo_resultado = {
    "entreposto": None,
    "cargas": [], # Lista de dicts: {"carga": "123", "status": "OK" / "Falta fazer a seleção", "remessa_picking": ""}
    "status": "idle", # "idle", "running", "success", "error"
    "erro": None
}

def normalizar_termo(texto):
    import re
    import unicodedata
    if not isinstance(texto, str):
        texto = str(texto)
    # Remove acentos
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8')
    # Caixa alta e remove caracteres especiais e espaços
    texto = texto.upper()
    texto = re.sub(r'[^A-Z0-9]', '', texto)
    return texto.strip()

def encontrar_coluna(df, nomes_possiveis, descricao_planilha="Planilha"):
    """
    Busca no DataFrame uma coluna correspondente de forma tolerante a acentos,
    espaços e caracteres especiais.
    """
    colunas_encontradas = list(df.columns)
    log_sys.write(f"📊 Colunas da {descricao_planilha}: {[str(c) for c in colunas_encontradas[:20]]}")
    
    nomes_norm = [normalizar_termo(n) for n in nomes_possiveis]
    
    # 1. Busca por correspondência exata após normalização
    for col in df.columns:
        col_norm = normalizar_termo(col)
        if col_norm in nomes_norm:
            return col
            
    # 2. Busca por correspondência parcial contida
    for col in df.columns:
        col_norm = normalizar_termo(col)
        for nome_n in nomes_norm:
            if nome_n and (nome_n in col_norm or col_norm in nome_n):
                return col
                
def converter_para_float(valor):
    if pd.isna(valor):
        return 0.0
    val_str = str(valor).strip()
    if not val_str or val_str == "-":
        return 0.0
    # Remove separators
    if ',' in val_str:
        if '.' in val_str:
            val_str = val_str.replace('.', '')
        val_str = val_str.replace(',', '.')
    try:
        return float(val_str)
    except ValueError:
        return 0.0

def selecionar_aba_cargas(sheet_names):
    # Procura por 'Dados da carga', 'Dados', 'Cargas', 'Carga'
    for name in sheet_names:
        name_lower = name.lower().strip()
        if name_lower == 'dados da carga' or name_lower == 'dados de carga':
            return name
    for name in sheet_names:
        name_lower = name.lower().strip()
        if 'dados' in name_lower:
            return name
    for name in sheet_names:
        name_lower = name.lower().strip()
        if 'carga' in name_lower and 'ficha' not in name_lower:
            return name
    return sheet_names[0] if sheet_names else 0

def selecionar_aba_estoque(sheet_names):
    # Procura por 'Estoque SAP 2025', 'Estoque SAP 202', 'Estoque SAP', 'Estoque'
    # Dá preferência para abas com 'SAP' no nome
    for name in sheet_names:
        name_lower = name.lower().strip()
        if 'estoque sap 2025' in name_lower:
            return name
    for name in sheet_names:
        name_lower = name.lower().strip()
        if 'estoque sap 202' in name_lower:
            return name
    for name in sheet_names:
        name_lower = name.lower().strip()
        if 'estoque sap' in name_lower:
            return name
    for name in sheet_names:
        name_lower = name.lower().strip()
        if 'estoque' in name_lower:
            return name
    return sheet_names[0] if sheet_names else 0

def carregar_planilhas_em_memoria(entreposto_nome):
    """
    Busca do .env as planilhas mapeadas para o entreposto informado,
    conecta no SharePoint e baixa os dados em memória.
    Retorna um dicionário contendo os DataFrames.
    """
    load_dotenv(ENV_PATH)
    
    # Define as chaves do .env com base no entreposto selecionado
    if entreposto_nome.upper() == "IPOJUCA":
        chaves_caminhos = {
            "Planilha de Cargas": os.getenv("PLANILHA_IPOJUCA_1"),
            "Planilha de Estoque": os.getenv("PLANILHA_IPOJUCA_2")
        }
    elif entreposto_nome.upper() == "ITAJAI":
        chaves_caminhos = {
            "Planilha de Cargas": os.getenv("PLANILHA_ITAJAI_1"),
            "Planilha de Estoque": os.getenv("PLANILHA_ITAJAI_2")
        }
    else:
        raise ValueError(f"Entreposto '{entreposto_nome}' desconhecido.")

    log_sys.write(f"🔄 Conectando ao SharePoint para acessar {entreposto_nome}...")

    client = SharePointClient()
    planilhas_carregadas = {}

    for desc, caminho_sp in chaves_caminhos.items():
        if not caminho_sp:
            log_sys.write(f"⚠️ {desc} não configurada no arquivo de configurações (.env).")
            continue

        nome_arquivo = os.path.basename(caminho_sp)
        log_sys.write(f"📥 Lendo {desc} do SharePoint: '{nome_arquivo}'...")
        try:
            conteudo_binario = client.baixar_arquivo(caminho_sp)
            log_sys.write(f"📊 Carregando dados no Pandas diretamente da memória...")
            
            # Carrega a planilha e seleciona a aba correta de forma dinâmica
            xl = pd.ExcelFile(io.BytesIO(conteudo_binario))
            aba_selecionada = 0
            
            if "Cargas" in desc:
                aba_env = os.getenv(f"PLANILHA_{entreposto_nome.upper()}_1_ABA")
                if aba_env and aba_env in xl.sheet_names:
                    aba_selecionada = aba_env
                else:
                    aba_selecionada = selecionar_aba_cargas(xl.sheet_names)
            elif "Estoque" in desc:
                aba_env = os.getenv(f"PLANILHA_{entreposto_nome.upper()}_2_ABA")
                if aba_env and aba_env in xl.sheet_names:
                    aba_selecionada = aba_env
                else:
                    aba_selecionada = selecionar_aba_estoque(xl.sheet_names)
            
            log_sys.write(f"📖 Lendo aba '{aba_selecionada}'...")
            df = xl.parse(aba_selecionada, dtype=str)
            log_sys.write(f"✅ {desc} processada! Linhas encontradas: {len(df)}")
            planilhas_carregadas[desc] = df
        except Exception as e:
            log_sys.write(f"❌ Falha ao processar '{nome_arquivo}': {str(e)}")
            raise e

    return planilhas_carregadas

def executar_automacao_entreposto(entreposto_nome):
    """
    Executa o fluxo de filtragem e cruzamento de cargas/estoque.
    """
    global ultimo_resultado
    
    ultimo_resultado["entreposto"] = entreposto_nome
    ultimo_resultado["status"] = "running"
    ultimo_resultado["cargas"] = []
    ultimo_resultado["erro"] = None
    
    try:
        dados = carregar_planilhas_em_memoria(entreposto_nome)
        
        df_cargas = dados.get("Planilha de Cargas")
        df_estoque = dados.get("Planilha de Estoque")
        
        if df_cargas is None or df_estoque is None:
            raise ValueError("Ambas as planilhas (Cargas e Estoque) precisam estar configuradas e carregadas.")

        log_sys.write("🔍 Analisando e filtrando as planilhas...")
        
        # 1. Ajustar cabeçalho dinâmico se a planilha de Cargas tiver o cabeçalho real em uma das primeiras linhas
        # Procuramos uma linha que contenha "REMESSA / PICKING", "SEQ" ou "OV"
        colunas_norm = [normalizar_termo(str(c)) for c in df_cargas.columns]
        tem_headers_ja = any(n in colunas_norm for n in ["REMESSAPICKING", "SEQ", "NOCARGA", "CARGA"])
        
        if not tem_headers_ja:
            linha_cabecalho_idx = -1
            for idx in range(min(5, len(df_cargas))):
                valores_linha = [str(x).upper() for x in df_cargas.iloc[idx].values]
                tem_remessa_picking = any("REMESSA / PICKING" in v or "REMESSA/PICKING" in v for v in valores_linha)
                tem_seq = any("SEQ" in v or "CARGA" in v for v in valores_linha)
                if tem_remessa_picking or tem_seq:
                    linha_cabecalho_idx = idx
                    break

            if linha_cabecalho_idx != -1:
                log_sys.write(f"📌 Cabeçalho real identificado na linha {linha_cabecalho_idx} da Planilha de Cargas. Promovendo linha...")
                novas_colunas = []
                for col_idx, col_val in enumerate(df_cargas.iloc[linha_cabecalho_idx]):
                    val_str = str(col_val).strip()
                    if val_str == "" or val_str.lower() == "nan":
                        # Mantém o nome antigo da coluna se o valor na linha for nulo
                        novas_colunas.append(str(df_cargas.columns[col_idx]))
                    else:
                        novas_colunas.append(val_str)
                df_cargas.columns = novas_colunas
                df_cargas = df_cargas.iloc[linha_cabecalho_idx + 1:].reset_index(drop=True)
        else:
            log_sys.write("📌 Colunas da Planilha de Cargas já identificadas corretamente no cabeçalho inicial.")

        # 2. Identificar colunas na Planilha de Cargas após a promoção do cabeçalho
        col_cargas_remessa = encontrar_coluna(df_cargas, ["REMESSA / PICKING", "REMESSA/PICKING", "STATUS"], "Planilha de Cargas")
        col_cargas_n_carga = encontrar_coluna(df_cargas, ["Nº DA CARGA", "N° DA CARGA", "Nº CARGA", "N° CARGA", "CARGA", "NUM CARGA"], "Planilha de Cargas")

        if not col_cargas_n_carga:
            raise KeyError("Coluna correspondente ao número da carga (ex: 'Nº da Carga') não foi identificada na Planilha de Cargas.")
        if not col_cargas_remessa:
            raise KeyError("Coluna correspondente a 'REMESSA / PICKING' não foi identificada na Planilha de Cargas.")

        # 3. Filtrar Cargas com a coluna REMESSA / PICKING vazia (onde o status do processo ainda está em branco)
        # Considera vazio se for NaN ou string em branco
        filtro_vazias = df_cargas[col_cargas_remessa].isna() | (df_cargas[col_cargas_remessa].astype(str).str.strip() == "")
        df_cargas_filtrado = df_cargas[filtro_vazias]
        
        # Obter IDs únicos das cargas
        cargas_alvo = []
        for c in df_cargas_filtrado[col_cargas_n_carga].dropna().unique():
            c_str = str(c).strip()
            if c_str == "" or c_str.lower() == "nan":
                continue
            # Se for do formato "380787/10" (apenas números), extrai apenas "380787"
            if "/" in c_str:
                partes = c_str.split("/")
                if partes[0].strip().isdigit():
                    c_str = partes[0].strip()
            # Ignora textos observativos (cargas válidas devem ser curtas, ex: menos de 20 caracteres)
            if not c_str or len(c_str) > 20:
                continue
            if c_str not in cargas_alvo:
                cargas_alvo.append(c_str)

        log_sys.write(f"📋 Encontradas {len(cargas_alvo)} cargas pendentes (sem Remessa/Picking): {cargas_alvo}")

        if not cargas_alvo:
            log_sys.write("✨ Nenhuma carga pendente identificada na Planilha de Cargas.")
            ultimo_resultado["status"] = "success"
            return True

        # 4. Ajustar cabeçalho dinâmico na Planilha de Estoque
        colunas_est_norm = [normalizar_termo(str(c)) for c in df_estoque.columns]
        tem_headers_est_ja = any(n in colunas_est_norm for n in ["NOCARGA", "CARGA", "MATERIAL", "LOTE"])
        
        if not tem_headers_est_ja:
            linha_cabecalho_est_idx = -1
            for idx in range(min(5, len(df_estoque))):
                valores_linha = [str(x).upper() for x in df_estoque.iloc[idx].values]
                tem_carga_termo = any("CARGA" in v or "MATERIAL" in v or "LOTE" in v for v in valores_linha)
                if tem_carga_termo:
                    linha_cabecalho_est_idx = idx
                    break

            if linha_cabecalho_est_idx != -1:
                log_sys.write(f"📌 Cabeçalho real identificado na linha {linha_cabecalho_est_idx} da Planilha de Estoque. Promovendo linha...")
                novas_colunas = []
                for col_idx, col_val in enumerate(df_estoque.iloc[linha_cabecalho_est_idx]):
                    val_str = str(col_val).strip()
                    if val_str == "" or val_str.lower() == "nan":
                        novas_colunas.append(str(df_estoque.columns[col_idx]))
                    else:
                        novas_colunas.append(val_str)
                df_estoque.columns = novas_colunas
                df_estoque = df_estoque.iloc[linha_cabecalho_est_idx + 1:].reset_index(drop=True)
        else:
            log_sys.write("📌 Colunas da Planilha de Estoque já identificadas corretamente no cabeçalho inicial.")

        # 5. Identificar coluna Nº CARGA na Planilha de Estoque
        col_estoque_n_carga = encontrar_coluna(df_estoque, ["Nº CARGA", "N° CARGA", "CARGA", "NUM CARGA"], "Planilha de Estoque")
        if not col_estoque_n_carga:
            raise KeyError("Coluna correspondente a 'Nº CARGA' não foi identificada na Planilha de Estoque.")

        # Converter coluna de carga do Estoque para string para comparação consistente
        df_estoque[col_estoque_n_carga] = df_estoque[col_estoque_n_carga].dropna().astype(str).str.strip()
        cargas_estoque_existentes = set(df_estoque[col_estoque_n_carga].unique())

        # Identificar colunas adicionais para cálculo
        col_cargas_peso_liq = encontrar_coluna(df_cargas, ["PESO LIQ", "PESO LIQUIDO", "P LIQ", "PESO LIQ. DADOS", "NET WEIGHT"], "Planilha de Cargas")
        col_cargas_pllt = encontrar_coluna(df_cargas, ["PLLT", "PALETE", "PALETES", "QTD PALETES", "PALLETS"], "Planilha de Cargas")

        col_estoque_peso_liq = encontrar_coluna(df_estoque, ["PESO LIQUIDO", "PESO LIQ", "NET WEIGHT"], "Planilha de Estoque")
        col_estoque_peso_bruto = encontrar_coluna(df_estoque, ["PESO BRUTO", "GROSS WEIGHT"], "Planilha de Estoque")
        col_estoque_remessa = encontrar_coluna(df_estoque, ["REMESSA", "REMESSA/PICKING", "REMESSA / PICKING", "DELIVERY", "REMESSA SAP", "REMESSAPICKING", "Nº REMESSA", "N° REMESSA"], "Planilha de Estoque")
        col_estoque_ov = encontrar_coluna(df_estoque, ["DOCUMENTO VENDAS", "OV", "ORDEM DE VENDA", "PEDIDO"], "Planilha de Estoque")

        # 4. Realizar o cruzamento das informações e cálculo de pesos/paletes
        cargas_resultado = []
        for carga_id in cargas_alvo:
            # Verifica se esta carga existe na planilha de estoque
            existe_no_estoque = carga_id in cargas_estoque_existentes
            status = "OK" if existe_no_estoque else "Falta fazer a seleção"
            
            peso_liquido = 0.0
            peso_bruto = "-"
            qtd_paletes = 0
            remessas_info = []
            
            if existe_no_estoque:
                # Filtrar registros correspondentes no Estoque
                linhas_estoque = df_estoque[df_estoque[col_estoque_n_carga] == carga_id]
                qtd_paletes = len(linhas_estoque)
                
                # Peso Líquido do Estoque
                if col_estoque_peso_liq:
                    peso_liquido = sum(linhas_estoque[col_estoque_peso_liq].apply(converter_para_float))
                
                # Peso Bruto do Estoque
                if col_estoque_peso_bruto:
                    peso_bruto = sum(linhas_estoque[col_estoque_peso_bruto].apply(converter_para_float))
                    peso_bruto = round(peso_bruto, 3)
                else:
                    peso_bruto = "-"
                    
                peso_liquido = round(peso_liquido, 3)

                # Agrupar por Remessa e OV no estoque
                groupby_cols = []
                if col_estoque_remessa:
                    groupby_cols.append(col_estoque_remessa)
                if col_estoque_ov:
                    groupby_cols.append(col_estoque_ov)

                if groupby_cols:
                    for chaves, grupo_remessa in linhas_estoque.groupby(groupby_cols, dropna=False):
                        if len(groupby_cols) == 2:
                            remessa_val, ov_val = chaves
                        else:
                            if col_estoque_remessa:
                                remessa_val = chaves
                                ov_val = "-"
                            else:
                                remessa_val = "-"
                                ov_val = chaves

                        remessa_str = str(remessa_val).strip() if not pd.isna(remessa_val) else "Sem Remessa"
                        if remessa_str.lower() in ["nan", "", "none"]:
                            remessa_str = "Sem Remessa"
                            
                        ov_str = str(ov_val).strip() if not pd.isna(ov_val) else "-"
                        if ov_str.lower() in ["nan", "", "none"]:
                            ov_str = "-"
                            
                        peso_liq_rem = 0.0
                        peso_bruto_rem = 0.0
                        
                        if col_estoque_peso_liq:
                            peso_liq_rem = sum(grupo_remessa[col_estoque_peso_liq].apply(converter_para_float))
                        if col_estoque_peso_bruto:
                            peso_bruto_rem = sum(grupo_remessa[col_estoque_peso_bruto].apply(converter_para_float))
                            
                        qtd_paletes_rem = len(grupo_remessa)
                        
                        remessas_info.append({
                            "remessa": remessa_str,
                            "ov": ov_str,
                            "peso_liquido": round(peso_liq_rem, 3),
                            "peso_bruto": round(peso_bruto_rem, 3),
                            "qtd_paletes": qtd_paletes_rem
                        })
                else:
                    remessas_info.append({
                        "remessa": "Geral",
                        "ov": "-",
                        "peso_liquido": peso_liquido,
                        "peso_bruto": peso_bruto if isinstance(peso_bruto, float) else 0.0,
                        "qtd_paletes": qtd_paletes
                    })

                log_sys.write(f"✔️ Carga {carga_id} localizada no estoque. Status: OK (Peso Liq: {peso_liquido}, Peso Bruto: {peso_bruto}, Paletes: {qtd_paletes})")
            else:
                # Filtrar registros correspondentes nas Cargas
                df_cargas_copy = df_cargas.copy()
                df_cargas_copy[col_cargas_n_carga] = df_cargas_copy[col_cargas_n_carga].dropna().astype(str).str.strip()
                
                def matches_carga(val):
                    val_s = str(val).strip()
                    if "/" in val_s:
                        partes = val_s.split("/")
                        if partes[0].strip().isdigit():
                            val_s = partes[0].strip()
                    return val_s == carga_id
                
                linhas_carga = df_cargas_copy[df_cargas_copy[col_cargas_n_carga].apply(matches_carga)]
                
                # Peso Líquido das Cargas
                if col_cargas_peso_liq:
                    peso_liquido = sum(linhas_carga[col_cargas_peso_liq].apply(converter_para_float))
                
                # Qtd Paletes das Cargas
                if col_cargas_pllt:
                    qtd_paletes = int(sum(linhas_carga[col_cargas_pllt].apply(converter_para_float)))
                
                peso_liquido = round(peso_liquido, 3)
                peso_bruto = "-"
                log_sys.write(f"⚠️ Carga {carga_id} NÃO encontrada no estoque! Status: Falta fazer a seleção (Peso Liq: {peso_liquido}, Peso Bruto: -, Paletes: {qtd_paletes})")
            
            cargas_resultado.append({
                "carga": carga_id,
                "status": status,
                "remessa_picking": "",
                "peso_liquido": peso_liquido,
                "peso_bruto": peso_bruto,
                "qtd_paletes": qtd_paletes,
                "remessas": remessas_info
            })

        ultimo_resultado["cargas"] = cargas_resultado
        ultimo_resultado["status"] = "success"
        log_sys.write(f"🎉 Processamento concluído com sucesso para o Entreposto {entreposto_nome}!")
        return True

    except Exception as e:
        log_sys.write(f"❌ Ocorreu um erro durante a automação: {str(e)}")
        ultimo_resultado["status"] = "error"
        ultimo_resultado["erro"] = str(e)
        return False
