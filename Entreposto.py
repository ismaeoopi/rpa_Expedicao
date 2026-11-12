import os
import io
import threading
import time
import pandas as pd
from dotenv import load_dotenv
from openpyxl import load_workbook
from pandas.io.parsers import TextParser
from src.utils.common import log_sys
from src.utils.sharepoint import SharePointClient, ENV_PATH

# Estado global da última execução para retornar ao frontend
ultimo_resultado = {
    "entreposto": None,
    "cargas": [], # Lista de dicts: {"carga": "123", "status": "OK" / "Falta fazer a seleção", "remessa_picking": ""}
    "status": "idle", # "idle", "running", "success", "error"
    "erro": None
}

# Mantém um snapshot curto das planilhas para que a seleção de cargas use os
# mesmos dados que acabaram de ser exibidos. O cache é apenas uma otimização:
# se estiver ausente ou vencido, o carregamento normal do SharePoint é usado.
_CACHE_TTL_SEGUNDOS = 10 * 60
_MAX_COLUNAS_EXCEL = 64
_cache_planilhas = {}
_cache_planilhas_lock = threading.Lock()


def limpar_cache_planilhas(entreposto_nome=None):
    """Invalida snapshots carregados do SharePoint."""
    with _cache_planilhas_lock:
        if entreposto_nome is None:
            _cache_planilhas.clear()
        else:
            _cache_planilhas.pop(str(entreposto_nome).upper(), None)


def normalizar_cargas(serie):
    """
    Normaliza IDs de carga de forma vetorizada.

    Preserva IDs alfanuméricos como ``IT21/10-26`` e, por compatibilidade com
    a regra anterior, reduz ``380787/10`` para ``380787``.
    """
    cargas = serie.fillna("").astype(str).str.strip()
    prefixos_numericos = cargas.str.extract(r"^(\d+)\s*/", expand=False)
    return cargas.where(prefixos_numericos.isna(), prefixos_numericos)


def _copiar_planilhas(planilhas):
    return {descricao: df.copy(deep=True) for descricao, df in planilhas.items()}


def _ler_planilha_excel_limitada(
    conteudo_binario,
    descricao,
    entreposto_nome,
    aba_configurada=None,
):
    """
    Lê somente a faixa de colunas usada pelo processo.

    Algumas planilhas possuem formatação até XFD (16.384 colunas). O leitor
    padrão do Pandas materializa todas essas células vazias. As colunas de
    negócio atuais ocupam menos de 30 posições; o limite de 64 mantém folga
    para novas colunas sem percorrer a dimensão artificial da planilha.
    """
    workbook = load_workbook(
        io.BytesIO(conteudo_binario),
        read_only=True,
        data_only=True,
        keep_links=False,
    )
    try:
        if aba_configurada and aba_configurada in workbook.sheetnames:
            aba_selecionada = aba_configurada
        elif "Cargas" in descricao:
            aba_selecionada = selecionar_aba_cargas(workbook.sheetnames)
        else:
            aba_selecionada = selecionar_aba_estoque(
                workbook.sheetnames, entreposto_nome
            )

        dados = []
        ultima_linha_com_dados = -1
        for numero_linha, linha in enumerate(
            workbook[aba_selecionada].iter_rows(
                max_col=_MAX_COLUNAS_EXCEL, values_only=True
            )
        ):
            valores = ["" if valor is None else valor for valor in linha]
            while valores and valores[-1] == "":
                valores.pop()
            if valores:
                ultima_linha_com_dados = numero_linha
            dados.append(valores)

        dados = dados[: ultima_linha_com_dados + 1]
        if not dados:
            return pd.DataFrame(), aba_selecionada

        largura = max(len(linha) for linha in dados)
        dados = [linha + [""] * (largura - len(linha)) for linha in dados]
        dataframe = TextParser(
            dados,
            dtype=str,
            skip_blank_lines=False,
        ).read()
        return dataframe, aba_selecionada
    finally:
        workbook.close()

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
    espaços e caracteres especiais, respeitando rigorosamente a ordem de prioridade
    de nomes_possiveis.
    """
    if df is None or df.empty:
        return None

    colunas_encontradas = list(df.columns)
    log_sys.write(f"📊 Colunas da {descricao_planilha}: {[str(c) for c in colunas_encontradas[:20]]}")

    colunas_norm = {normalizar_termo(c): c for c in df.columns}

    # 1. Busca por correspondência exata na ordem de prioridade de nomes_possiveis
    for nome in nomes_possiveis:
        nome_norm = normalizar_termo(nome)
        if nome_norm and nome_norm in colunas_norm:
            return colunas_norm[nome_norm]

    # 2. Busca por correspondência parcial contida na ordem de prioridade
    for nome in nomes_possiveis:
        nome_norm = normalizar_termo(nome)
        if not nome_norm:
            continue
        for col_norm, col_orig in colunas_norm.items():
            if nome_norm in col_norm or col_norm in nome_norm:
                return col_orig

    return None
                
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

def selecionar_aba_estoque(sheet_names, entreposto_nome=None):
    # 1. Se informou o entreposto (ex: IPOJUCA), busca por 'estoque sap' + o nome do entreposto
    if entreposto_nome:
        ent_lower = entreposto_nome.lower().strip()
        for name in sheet_names:
            name_lower = name.lower().strip()
            if 'estoque sap' in name_lower and ent_lower in name_lower:
                return name
                
    # 2. Procura por 'Estoque SAP' com o ano mais recente (decrescente: 2026, 2025, etc.)
    for ano in range(2026, 2021, -1):
        for name in sheet_names:
            name_lower = name.lower().strip()
            if f'estoque sap {ano}' in name_lower:
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

def carregar_planilhas_em_memoria(entreposto_nome, usar_cache=False):
    """
    Busca do .env as planilhas mapeadas para o entreposto informado,
    conecta no SharePoint e baixa os dados em memória.
    Retorna um dicionário contendo os DataFrames.
    """
    load_dotenv(ENV_PATH)
    entreposto_chave = str(entreposto_nome).upper()
    
    # Define as chaves do .env com base no entreposto selecionado
    if entreposto_chave == "IPOJUCA":
        chaves_caminhos = {
            "Planilha de Cargas": os.getenv("PLANILHA_IPOJUCA_1"),
            "Planilha de Estoque": os.getenv("PLANILHA_IPOJUCA_2")
        }
    elif entreposto_chave == "ITAJAI":
        chaves_caminhos = {
            "Planilha de Cargas": os.getenv("PLANILHA_ITAJAI_1"),
            "Planilha de Estoque": os.getenv("PLANILHA_ITAJAI_2")
        }
    else:
        raise ValueError(f"Entreposto '{entreposto_nome}' desconhecido.")

    caminhos_cache = tuple(chaves_caminhos.items())
    if usar_cache:
        agora = time.monotonic()
        with _cache_planilhas_lock:
            snapshot = _cache_planilhas.get(entreposto_chave)
            if (
                snapshot
                and snapshot["caminhos"] == caminhos_cache
                and agora - snapshot["criado_em"] <= _CACHE_TTL_SEGUNDOS
            ):
                log_sys.write(
                    f"⚡ Reutilizando planilhas já carregadas para {entreposto_chave}."
                )
                return _copiar_planilhas(snapshot["dados"])

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

            numero_planilha = "1" if "Cargas" in desc else "2"
            aba_env = os.getenv(
                f"PLANILHA_{entreposto_chave}_{numero_planilha}_ABA"
            )

            try:
                df, aba_selecionada = _ler_planilha_excel_limitada(
                    conteudo_binario,
                    desc,
                    entreposto_nome,
                    aba_configurada=aba_env,
                )
                log_sys.write(
                    f"📖 Lendo aba '{aba_selecionada}' com faixa otimizada "
                    f"({len(df.columns)} colunas úteis)..."
                )
            except Exception as erro_otimizacao:
                log_sys.write(
                    "⚠️ Leitura otimizada indisponível; usando método "
                    f"compatível. Detalhe: {erro_otimizacao}"
                )
                xl = pd.ExcelFile(io.BytesIO(conteudo_binario))
                if aba_env and aba_env in xl.sheet_names:
                    aba_selecionada = aba_env
                elif "Cargas" in desc:
                    aba_selecionada = selecionar_aba_cargas(xl.sheet_names)
                else:
                    aba_selecionada = selecionar_aba_estoque(
                        xl.sheet_names, entreposto_nome
                    )
                log_sys.write(f"📖 Lendo aba '{aba_selecionada}'...")
                df = xl.parse(aba_selecionada, dtype=str)

            log_sys.write(f"✅ {desc} processada! Linhas encontradas: {len(df)}")
            planilhas_carregadas[desc] = df
        except Exception as e:
            log_sys.write(f"❌ Falha ao processar '{nome_arquivo}': {str(e)}")
            raise e

    if len(planilhas_carregadas) == len(chaves_caminhos):
        with _cache_planilhas_lock:
            _cache_planilhas[entreposto_chave] = {
                "criado_em": time.monotonic(),
                "caminhos": caminhos_cache,
                "dados": _copiar_planilhas(planilhas_carregadas),
            }

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
        dados = carregar_planilhas_em_memoria(entreposto_nome, usar_cache=True)
        
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

        # A normalização era refeita linha a linha para cada carga ausente.
        # Calculá-la uma única vez remove as varreduras repetidas do DataFrame.
        cargas_normalizadas = normalizar_cargas(df_cargas[col_cargas_n_carga])
        
        # Obter IDs únicos das cargas
        cargas_alvo_serie = cargas_normalizadas.loc[df_cargas_filtrado.index]
        filtro_cargas_validas = (
            cargas_alvo_serie.ne("")
            & cargas_alvo_serie.str.lower().ne("nan")
            & cargas_alvo_serie.str.len().le(20)
        )
        cargas_alvo = (
            cargas_alvo_serie[filtro_cargas_validas].drop_duplicates().tolist()
        )

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
                linhas_carga = df_cargas[cargas_normalizadas == carga_id]
                
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
