import os
import re
import io
import pandas as pd
from dotenv import load_dotenv
from src.utils.common import log_sys
from src.utils.sharepoint import SharePointClient, ENV_PATH, salvar_configuracoes_env
from Entreposto import encontrar_coluna, normalizar_termo

def converter_para_float_cabotagem(valor):
    if pd.isna(valor):
        return 0.0
    val_str = str(valor).strip()
    if not val_str or val_str == "-":
        return 0.0
    # Remove R$, $, espaços e letras
    val_str = re.sub(r'[A-Za-z$R\s]', '', val_str)
    if ',' in val_str:
        if '.' in val_str:
            val_str = val_str.replace('.', '')
        val_str = val_str.replace(',', '.')
    try:
        return float(val_str)
    except ValueError:
        return 0.0

# Estado global da Cabotagem
cabotagem_estado = {
    "planilha_caminho": "",
    "containers": [], # Lista de containers estruturados
    "status_etapas": {}, # {container_id: {"of": "pending", "of_numero": "", "erro_detalhe": ""}}
    "selecionados": [] # Chaves selecionadas para processamento
}


def _extrair_numero_of(val) -> str:
    """Extrai apenas o número da OF, seja string, dict ou repr de dict."""
    if not val:
        return ""
    if isinstance(val, dict):
        return str(val.get("of_numero", "") or "").strip()
    val_str = str(val).strip()
    if val_str.startswith("{") and "of_numero" in val_str:
        import ast
        try:
            parsed = ast.literal_eval(val_str)
            if isinstance(parsed, dict):
                return str(parsed.get("of_numero", "") or "").strip()
        except Exception:
            pass
        match = re.search(r"'of_numero':\s*'([^']+)'", val_str)
        if match:
            return match.group(1)
    return val_str


def montar_relatorio_cabotagem(estado=None) -> pd.DataFrame:
    """Cria um DataFrame com carga, container, remessa, OF e status para exportação Excel."""
    estado = estado or cabotagem_estado
    linhas = []

    containers = estado.get("containers", []) or []
    selecionados = estado.get("selecionados", []) or []

    # Exporta apenas as cargas/containers enviadas para processamento quando houver seleção
    if selecionados:
        containers = [
            c for c in containers
            if f"{c.get('carga')}_{c.get('container')}" in selecionados
        ]

    for container in containers:
        carga = container.get("carga", "")
        container_id = container.get("container", "")
        remessas = container.get("remessas", []) or []
        if not remessas:
            continue

        c_key = f"{carga}_{container_id}"
        status_info = estado.get("status_etapas", {}).get(c_key, {})
        raw_of = status_info.get("of_numero") or container.get("of_numero") or ""
        of_numero = _extrair_numero_of(raw_of)
        status_exec = status_info.get("of", "pending")

        for remessa in remessas:
            remessas_ausentes_lista = status_info.get("remessas_ausentes", [])

            # Determinar OF e Status para esta remessa específica
            if remessa in remessas_ausentes_lista:
                of_para_remessa = ""
                status_remessa = "Não Encontrada"
            elif status_exec == "running":
                of_para_remessa = ""
                status_remessa = "Em processamento"
            elif status_exec == "error":
                of_para_remessa = ""
                status_remessa = "Erro"
            elif of_numero:
                of_para_remessa = of_numero
                status_remessa = "Gerada"
            else:
                of_para_remessa = ""
                status_remessa = "Pendente"

            linhas.append({
                "Carga": carga,
                "Container": container_id,
                "Remessa": remessa,
                "OF": of_para_remessa,
                "Status": status_remessa,
            })

    if not linhas:
        linhas.append({
            "Carga": "",
            "Container": "",
            "Remessa": "",
            "OF": "",
            "Status": "Pendente",
        })

    return pd.DataFrame(linhas, columns=["Carga", "Container", "Remessa", "OF", "Status"])



def obter_dados_cabotagem() -> list:
    """
    Baixa a planilha de Cabotagem do SharePoint e monta a lista de containers
    com suas respectivas remessas, valores de frete calculados e status.
    """
    global cabotagem_estado
    
    load_dotenv(ENV_PATH)
    caminho_sp = os.getenv("PLANILHA_CABOTAGEM")
    if not caminho_sp:
        raise ValueError("A planilha de Cabotagem (PLANILHA_CABOTAGEM) não está configurada.")
        
    log_sys.write(f"🔄 Conectando ao SharePoint para acessar Cabotagem...")
    client = SharePointClient()
    conteudo_binario = client.baixar_arquivo(caminho_sp)
    
    log_sys.write(f"📊 Carregando dados no Pandas...")
    xl = pd.ExcelFile(io.BytesIO(conteudo_binario))
    aba_selecionada = 0
    # Tenta obter aba configurada ou a primeira
    aba_env = os.getenv("PLANILHA_CABOTAGEM_ABA")
    if aba_env and aba_env in xl.sheet_names:
        aba_selecionada = aba_env
    else:
        aba_selecionada = xl.sheet_names[0]
        
    log_sys.write(f"📖 Lendo aba '{aba_selecionada}'...")
    df = xl.parse(aba_selecionada, dtype=str)
    log_sys.write(f"📊 Total de linhas brutas lidas do Excel: {len(df)}")
    
    # 1. Promover cabeçalho se necessário
    colunas_norm = [normalizar_termo(str(c)) for c in df.columns]
    tem_headers_ja = any(n in colunas_norm for n in ["REMESSA", "CARGA", "CONTAINER"])
    
    if not tem_headers_ja:
        linha_cabecalho_idx = -1
        for idx in range(min(15, len(df))): # Aumentado de 5 para 15
            valores_linha = [str(x).upper() for x in df.iloc[idx].values]
            if any("REMESSA" in v or "CARGA" in v or "CONTAINER" in v for v in valores_linha):
                linha_cabecalho_idx = idx
                break
        if linha_cabecalho_idx != -1:
            log_sys.write(f"📌 Cabeçalho real identificado na linha {linha_cabecalho_idx}. Promovendo...")
            novas_colunas = []
            for col_idx, col_val in enumerate(df.iloc[linha_cabecalho_idx]):
                val_str = str(col_val).strip()
                if val_str == "" or val_str.lower() == "nan":
                    novas_colunas.append(str(df.columns[col_idx]))
                else:
                    novas_colunas.append(val_str)
            df.columns = novas_colunas
            df = df.iloc[linha_cabecalho_idx + 1:].reset_index(drop=True)
            
    log_sys.write(f"📊 Total de linhas após tratamento de cabeçalho: {len(df)}")
    if len(df) > 0:
        log_sys.write(f"🔍 Primeiras 3 linhas de dados: {df.head(3).to_dict(orient='records')}")

            
    # 2. Identificar colunas cruciais
    col_carga = encontrar_coluna(df, ["OPERACAO", "OPERAÇÃO", "CARGA", "NOCARGA", "NUM CARGA", "NUMERO CARGA"], "Planilha Cabotagem")
    col_container = encontrar_coluna(df, ["CONTAINER", "ID CONTAINER", "NUM CONTAINER", "CONTEINER"], "Planilha Cabotagem")
    col_remessa = encontrar_coluna(df, ["REMESSA", "REMESSAS", "DELIVERY", "FUS"], "Planilha Cabotagem")
    col_transportadora = encontrar_coluna(df, ["TRANSPORTADORA", "TRANSP", "CARRIER", "REDESPACHO"], "Planilha Cabotagem")
    col_valor_frete = encontrar_coluna(df, ["VALOR DO FRETE", "VALOR DE FRETE", "VALOR FRETE", "FRETE", "VALOR"], "Planilha Cabotagem")
    col_of = encontrar_coluna(df, ["ORDEM DE FRETE", "OF", "NUMERO OF", "Nº OF", "N° OF"], "Planilha Cabotagem")
    col_cliente = encontrar_coluna(df, ["CLIENTE", "NOME CLIENTE", "CLIENTE ABREV"], "Planilha Cabotagem")
    
    # Validação amigável
    colunas_faltantes = []
    if not col_carga: colunas_faltantes.append("Carga / Operação")
    if not col_container: colunas_faltantes.append("Container")
    if not col_remessa: colunas_faltantes.append("Remessa")
    
    if colunas_faltantes:
        msg = f"❌ Colunas obrigatórias ausentes na planilha: {', '.join(colunas_faltantes)}."
        log_sys.write(msg)
        raise KeyError(msg)
        
    log_sys.write(f"✔️ Colunas identificadas -> Carga: '{col_carga}', Container: '{col_container}', Remessa: '{col_remessa}'")
    if col_transportadora:
        log_sys.write(f"✔️ Transportadora identificada na coluna: '{col_transportadora}'")
    else:
        log_sys.write("⚠️ Coluna de Transportadora não encontrada. Usará a transportadora padrão configurada.")
        
    if col_valor_frete:
        log_sys.write(f"✔️ Valor de Frete identificado na coluna: '{col_valor_frete}'")
    else:
        log_sys.write("⚠️ Coluna de Valor de Frete não encontrada. Usará R$ 0,00 por padrão.")
        
    if col_of:
        log_sys.write(f"✔️ Coluna de OF identificada: '{col_of}'")
    else:
        log_sys.write("⚠️ Coluna de OF não encontrada na planilha. Uma nova coluna virtual será simulada.")
        
    if col_cliente:
        log_sys.write(f"✔️ Coluna de Cliente identificada: '{col_cliente}'")
        
    # Limpeza e normalização
    df[col_carga] = df[col_carga].fillna("").astype(str).str.strip()
    df[col_container] = df[col_container].fillna("").astype(str).str.strip()
    df[col_remessa] = df[col_remessa].fillna("").astype(str).str.strip()
    
    if col_transportadora:
        df[col_transportadora] = df[col_transportadora].fillna("").astype(str).str.strip()
    if col_valor_frete:
        df[col_valor_frete] = df[col_valor_frete].fillna("").astype(str).str.strip()
    if col_of:
        df[col_of] = df[col_of].fillna("").astype(str).str.strip()
    else:
        df["OF"] = ""
        col_of = "OF"
        
    if col_cliente:
        df[col_cliente] = df[col_cliente].fillna("").astype(str).str.strip()
        
    # 3. Mapear containers da carga
    cargas_list = []
    
    # Agrupa por Carga globalmente para calcular o total de containers por carga
    carga_grupos = df.groupby(col_carga)
    
    for carga_id, df_carga in carga_grupos:
        if not carga_id or carga_id.lower() in ["nan", "none", ""]:
            continue
            
        # Filtra os containers dessa carga
        unique_containers = [c for c in df_carga[col_container].unique() if c and c.lower() not in ["nan", "none", ""]]
        total_containers = len(unique_containers)
        
        # Pega o Cliente da carga
        cliente_nome = ""
        if col_cliente:
            for val in df_carga[col_cliente]:
                if val and val.lower() not in ["nan", "none", ""]:
                    cliente_nome = val.strip()
                    break
                    
        # Pega o valor total do frete da carga (primeiro valor não vazio encontrado)
        valor_total_frete = 0.0
        frete_preenchido = False
        if col_valor_frete:
            for val in df_carga[col_valor_frete]:
                if val and str(val).strip().lower() not in ["nan", "none", "", "-"]:
                    raw_val = str(val).strip()
                    parsed_val = converter_para_float_cabotagem(val)
                    log_sys.write(f"🔍 Carga {carga_id} | Valor Bruto: '{raw_val}' | Valor Convertido: {parsed_val}")
                    valor_total_frete = parsed_val
                    frete_preenchido = True
                    break
                    
        # Monta a lista de containers para esta carga
        containers_c = []
        todos_com_of = True
        
        for container_id in unique_containers:
            df_container = df_carga[df_carga[col_container] == container_id]
            
            # Coleta todas as remessas
            remessas = [r for r in df_container[col_remessa].unique() if r and r.lower() not in ["nan", "none", ""]]
            if not remessas:
                continue
                
            # Verifica se já possui OF preenchida
            of_existente = ""
            for o in df_container[col_of]:
                if o and o.lower() not in ["nan", "none", "", "-"]:
                    of_existente = o.strip()
                    break
                    
            if not of_existente:
                todos_com_of = False
                
            # Transportadora fixa configurada no .env
            transportadora_padrao = os.getenv("CABOTAGEM_TRANSPORTADORA_PADRAO", "9190617").strip()
            transportadora_codigo = transportadora_padrao or "9190617"
            transportadora = f"Fixo ({transportadora_codigo})"
            log_sys.write(f"🚚 Usando transportadora fixa do .env: {transportadora_codigo}")
                        
            # Calcula o valor do frete para o container
            if total_containers > 1:
                valor_container = valor_total_frete / total_containers
                dividido = True
            else:
                valor_container = valor_total_frete
                dividido = False
                
            containers_c.append({
                "container": container_id,
                "remessas": remessas,
                "transportadora": transportadora,
                "transportadora_codigo": transportadora_codigo,
                "valor_container": round(valor_container, 2),
                "dividido": dividido,
                "of_numero": of_existente,
                "pendente": not bool(of_existente)
            })
            
        # Se TODOS os containers desta carga já possuem OF, não traz ela (pula)
        if todos_com_of and len(containers_c) > 0:
            continue
            
        if containers_c:
            cargas_list.append({
                "carga": carga_id,
                "cliente": cliente_nome,
                "valor_total_carga": valor_total_frete,
                "total_containers_carga": total_containers,
                "frete_preenchido": frete_preenchido,
                "containers": containers_c
            })
            
    # Atualiza o estado global com os containers nivelados para o executor de background
    containers_flat = []
    for c_item in cargas_list:
        for c in c_item["containers"]:
            containers_flat.append({
                "carga": c_item["carga"],
                "container": c["container"],
                "remessas": c["remessas"],
                "transportadora": c["transportadora"],
                "transportadora_codigo": c["transportadora_codigo"],
                "valor_container": c["valor_container"],
                "dividido": c["dividido"],
                "total_containers_carga": c_item["total_containers_carga"],
                "of_numero": c["of_numero"],
                "pendente": c["pendente"],
                "frete_preenchido": c_item["frete_preenchido"]
            })
            
    cabotagem_estado["containers"] = containers_flat
    cabotagem_estado["planilha_caminho"] = caminho_sp
    cabotagem_estado["selecionados"] = []
    
    # Inicializa status_etapas para os que estão no estado global
    for c in containers_flat:
        c_key = f"{c['carga']}_{c['container']}"
        if c_key not in cabotagem_estado["status_etapas"]:
            cabotagem_estado["status_etapas"][c_key] = {
                "of": "success" if c["of_numero"] else "pending",
                "of_numero": c["of_numero"],
                "erro_detalhe": ""
            }
            
    return cargas_list

def rodar_criar_of_cabotagem(usuario, senha, containers_selecionados):
    """
    Executa a criação de OF para os containers selecionados usando Playwright no background.
    """
    global cabotagem_estado
    cabotagem_estado["selecionados"] = containers_selecionados
    
    from src.expedicao.sap_cabotagem_playwright import rodar_criacao_of_cabotagem_playwright
    
    log_sys.write("=== [Cabotagem] Iniciando Criação de Ordens de Frete ===")
    
    # Encontra os containers estruturados correspondentes
    selecionados_dados = []
    for sel in containers_selecionados: # sel é no formato "carga_container"
        partes = sel.split("_")
        carga_id = partes[0]
        container_id = partes[1]
        
        # Acha nos dados carregados
        for c in cabotagem_estado["containers"]:
            if c["carga"] == carga_id and c["container"] == container_id:
                selecionados_dados.append(c)
                break
                
    for c in selecionados_dados:
        c_key = f"{c['carga']}_{c['container']}"
        cabotagem_estado["status_etapas"][c_key]["of"] = "running"
        
        log_sys.write(f"🚢 Processando Container {c['container']} (Carga {c['carga']}) | Remessas: {', '.join(c['remessas'])}")
        
        if not c["frete_preenchido"]:
            log_sys.write(f"⚠️ Alerta: O container {c['container']} (Carga {c['carga']}) não possui valor de frete preenchido na planilha.")
            
        try:
            res_of = rodar_criacao_of_cabotagem_playwright(
                remessas=c["remessas"],
                transportadora=c["transportadora_codigo"],
                valor_frete=c["valor_container"],
                usuario=usuario,
                senha=senha,
                headless=False
            )
            of_num = _extrair_numero_of(res_of)
            
            # Guardar quais remessas foram confirmadas e quais ausentes
            if isinstance(res_of, dict):
                cabotagem_estado["status_etapas"][c_key]["remessas_confirmadas"] = res_of.get("remessas_confirmadas", [])
                cabotagem_estado["status_etapas"][c_key]["remessas_ausentes"] = res_of.get("remessas_ausentes", [])

            cabotagem_estado["status_etapas"][c_key]["of"] = "success"
            cabotagem_estado["status_etapas"][c_key]["of_numero"] = of_num
            c["of_numero"] = of_num
            log_sys.write(f"✅ Ordem de Frete {of_num} criada com sucesso para o Container {c['container']}.")
            
            # Aqui podemos salvar de volta no SharePoint se necessário, mas para esta fase 1
            # o principal é gerar a OF e atualizar na UI.
            
        except Exception as e:
            cabotagem_estado["status_etapas"][c_key]["of"] = "error"
            cabotagem_estado["status_etapas"][c_key]["erro_detalhe"] = str(e)
            log_sys.write(f"❌ Erro ao processar container {c['container']}: {e}")
            
    log_sys.write("🎉 Processamento de Cabotagem finalizado!")
