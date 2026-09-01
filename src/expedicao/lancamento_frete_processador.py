import os
import re
import io
import pandas as pd
from collections import defaultdict
from dotenv import load_dotenv
from src.utils.common import log_sys
from src.utils.sharepoint import SharePointClient, ENV_PATH
from Entreposto import encontrar_coluna, normalizar_termo

# Estado global do processador de Lançamento de Fretes
lancamento_frete_estado = {
    "auditoria_caminho": "",
    "corporativo_caminho": "",
    "fretes": [], # Lista de fretes estruturados
    "status_etapas": {}, # {cte_key: {"status": "pending", "detalhe": "", "of": "", "rc": ""}}
    "selecionados": [] # Keys selecionadas para processamento
}

def converter_para_float_frete(valor):
    if pd.isna(valor):
        return 0.0
    val_str = str(valor).strip()
    if not val_str or val_str == "-" or val_str.lower() == "nan":
        return 0.0
    val_str = re.sub(r'[A-Za-z$R\s]', '', val_str)
    if ',' in val_str:
        if '.' in val_str:
            val_str = val_str.replace('.', '')
        val_str = val_str.replace(',', '.')
    try:
        return float(val_str)
    except ValueError:
        return 0.0

def _promover_cabecalho_se_necessario(df: pd.DataFrame) -> pd.DataFrame:
    """Verifica e promove a linha real de cabeçalho (geralmente linha 2 no Excel P716)."""
    colunas_norm = [normalizar_termo(str(c)) for c in df.columns]
    tem_headers_ja = any(n in colunas_norm for n in ["CTE", "CT-E", "EMISSOR", "CHAVE DE ACESSO", "EMPRESA"])
    
    if not tem_headers_ja:
        linha_cabecalho_idx = -1
        for idx in range(min(15, len(df))):
            valores_linha = [str(x).upper() for x in df.iloc[idx].values]
            if any("CT-E" in v or "EMISSOR" in v or "CHAVE DE ACESSO" in v or "EMPRESA" in v for v in valores_linha):
                linha_cabecalho_idx = idx
                break
        if linha_cabecalho_idx != -1:
            novas_colunas = []
            for col_idx, col_val in enumerate(df.iloc[linha_cabecalho_idx]):
                val_str = str(col_val).strip()
                if val_str == "" or val_str.lower() == "nan":
                    novas_colunas.append(str(df.columns[col_idx]))
                else:
                    novas_colunas.append(val_str)
            df.columns = novas_colunas
            df = df.iloc[linha_cabecalho_idx + 1:].reset_index(drop=True)
    return df

def obter_dados_lancamento_frete() -> list:
    """
    Baixa as planilhas de Auditoria e Corporativo do SharePoint,
    promove cabeçalhos, consolida e cruza as informações usando a chave CT-e / Chave de Acesso.
    """
    global lancamento_frete_estado
    load_dotenv(ENV_PATH)

    auditoria_id = os.getenv("PLANILHA_AUDITORIA_FRETE_P716", "39BE56B3-0D60-4207-BFC3-2A16DE2C4DB6")
    corporativo_id = os.getenv("PLANILHA_LANCAMENTO_FRETE_CORP_P716", "94ABF29E-08F2-4E5E-BD7F-B94D71AC3E0C")

    log_sys.write("🔄 Conectando ao SharePoint para carregar planilhas de Frete P716...")
    client = SharePointClient()

    # 1. Carregar Planilha de Auditoria
    log_sys.write("📊 Baixando planilha base: Auditoria_Lançamto_de_Frete_P716...")
    bin_auditoria = client.baixar_arquivo(auditoria_id)
    xl_auditoria = pd.ExcelFile(io.BytesIO(bin_auditoria))
    sheet_auditoria = "CTes" if "CTes" in xl_auditoria.sheet_names else xl_auditoria.sheet_names[0]
    df_auditoria = xl_auditoria.parse(sheet_auditoria, dtype=str)
    df_auditoria = _promover_cabecalho_se_necessario(df_auditoria)
    log_sys.write(f"📖 Planilha Auditoria lida ({len(df_auditoria)} linhas).")

    # 2. Carregar Planilha Corporativa
    df_corp = None
    df_fiscal = None
    try:
        log_sys.write("📊 Baixando planilha complementar: P716 - Lançamento de frete Corporativo...")
        bin_corp = client.baixar_arquivo(corporativo_id)
        xl_corp = pd.ExcelFile(io.BytesIO(bin_corp))
        sheet_corp = "CTes" if "CTes" in xl_corp.sheet_names else xl_corp.sheet_names[0]
        df_corp = xl_corp.parse(sheet_corp, dtype=str)
        df_corp = _promover_cabecalho_se_necessario(df_corp)
        
        if "Fiscal" in xl_corp.sheet_names:
            df_fiscal = xl_corp.parse("Fiscal", dtype=str)
            df_fiscal = _promover_cabecalho_se_necessario(df_fiscal)
    except Exception as e_corp:
        log_sys.write(f"⚠️ Alerta ao carregar planilha corporativa: {e_corp}")

    # 3. Mapear colunas da Planilha de Auditoria
    col_cte = encontrar_coluna(df_auditoria, ["CT-E", "CTE", "NUMERO CTE", "NUM CTE"], "Auditoria")
    col_chave = encontrar_coluna(df_auditoria, ["CHAVE DE ACESSO", "CHAVE", "CHAVE ACESSO"], "Auditoria")
    col_empresa = encontrar_coluna(df_auditoria, ["EMPRESA", "EMP"], "Auditoria")
    col_estab = encontrar_coluna(df_auditoria, ["ESTAB.", "ESTABELECIMENTO", "ESTAB"], "Auditoria")
    col_planta = encontrar_coluna(df_auditoria, ["PLANTA", "UNIDADE"], "Auditoria")
    col_tipo = encontrar_coluna(df_auditoria, ["TIPO", "TIPO FRETE", "TIPO CTE"], "Auditoria")
    col_cod_emissor = encontrar_coluna(df_auditoria, ["CÓD EMISSOR", "COD EMISSOR", "CÓD. EMISSOR", "CODIGO EMISSOR", "COD. EMISSOR"], "Auditoria")
    col_emissor = encontrar_coluna(df_auditoria, ["EMISSOR", "NOME EMISSOR", "TRANSPORTADORA"], "Auditoria")
    col_remetente = encontrar_coluna(df_auditoria, ["REMETENTE", "NOME REMETENTE"], "Auditoria")
    col_destinatario = encontrar_coluna(df_auditoria, ["DESTINATÁRIO", "DESTINATARIO", "CLIENTE"], "Auditoria")
    col_valor_final = encontrar_coluna(df_auditoria, ["VALOR FINAL", "VALOR FRETE", "VALOR", "VALOR TOTAL"], "Auditoria")
    col_valor_sem_icms = encontrar_coluna(df_auditoria, ["VALOR S/ ICMS", "VALOR SEM ICMS"], "Auditoria")
    col_icms = encontrar_coluna(df_auditoria, ["ICMS", "VALOR ICMS"], "Auditoria")
    col_of = encontrar_coluna(df_auditoria, ["OF", "ORDEM DE FRETE", "Nº OF"], "Auditoria")
    col_rc = encontrar_coluna(df_auditoria, ["RC", "REQUISICAO", "REQUISIÇÃO"], "Auditoria")
    col_fatura = encontrar_coluna(df_auditoria, ["FATURA", "NUM FATURA"], "Auditoria")
    col_vencimento = encontrar_coluna(df_auditoria, ["VENCIMENTO", "DT VENCIMENTO"], "Auditoria")
    col_status = encontrar_coluna(df_auditoria, ["STATUS", "SITUACAO", "SITUAÇÃO"], "Auditoria")
    col_uf_origem = encontrar_coluna(df_auditoria, ["UF ORIGEM", "UF ORIG"], "Auditoria")
    col_uf_destino = encontrar_coluna(df_auditoria, ["UF DESTINO", "UF DEST"], "Auditoria")

    # Mapeamento auxiliar do Corporativo (se houver)
    corp_map = {}
    if df_corp is not None:
        c_cte = encontrar_coluna(df_corp, ["CT-E", "CTE"], "Corp")
        c_chave = encontrar_coluna(df_corp, ["CHAVE DE ACESSO", "CHAVE"], "Corp")
        c_dest = encontrar_coluna(df_corp, ["DESTINATÁRIO", "DESTINATARIO", "CLIENTE"], "Corp")
        c_remet = encontrar_coluna(df_corp, ["REMETENTE"], "Corp")
        
        for idx, row in df_corp.iterrows():
            k_cte = str(row[c_cte]).strip() if c_cte and pd.notna(row[c_cte]) else ""
            k_chave = str(row[c_chave]).strip() if c_chave and pd.notna(row[c_chave]) else ""
            key = k_chave if k_chave else k_cte
            if key and key.lower() not in ["nan", "none"]:
                corp_map[key] = {
                    "destinatario": str(row[c_dest]).strip() if c_dest and pd.notna(row[c_dest]) else "",
                    "remetente": str(row[c_remet]).strip() if c_remet and pd.notna(row[c_remet]) else ""
                }

    # Mapeamento do Fiscal (se houver)
    fiscal_map = {}
    if df_fiscal is not None:
        f_cte = encontrar_coluna(df_fiscal, ["RC[CT-E]", "CT-E", "CTE"], "Fiscal")
        f_chave = encontrar_coluna(df_fiscal, ["RC[CHAVE DE ACESSO]", "CHAVE"], "Fiscal")
        f_status = encontrar_coluna(df_fiscal, ["RC[STATUS FINANCEIRO]", "STATUS"], "Fiscal")
        f_dt_escrit = encontrar_coluna(df_fiscal, ["RC[DT_LANÇAMENTO_FISCAL]", "DATA FISCAL"], "Fiscal")
        
        for idx, row in df_fiscal.iterrows():
            k_cte = str(row[f_cte]).strip() if f_cte and pd.notna(row[f_cte]) else ""
            k_chave = str(row[f_chave]).strip() if f_chave and pd.notna(row[f_chave]) else ""
            key = k_chave if k_chave else k_cte
            if key and key.lower() not in ["nan", "none"]:
                fiscal_map[key] = {
                    "status_financeiro": str(row[f_status]).strip() if f_status and pd.notna(row[f_status]) else "",
                    "dt_fiscal": str(row[f_dt_escrit]).strip() if f_dt_escrit and pd.notna(row[f_dt_escrit]) else ""
                }

    fretes_list = []
    
    for idx, row in df_auditoria.iterrows():
        cte_num = str(row[col_cte]).strip() if col_cte and pd.notna(row[col_cte]) else ""
        chave_acesso = str(row[col_chave]).strip() if col_chave and pd.notna(row[col_chave]) else ""
        
        if not cte_num and not chave_acesso:
            continue
        if cte_num.lower() in ["nan", "none", "ct-e", "cte"] or chave_acesso.lower() in ["nan", "none"]:
            continue
            
        key_primary = chave_acesso if chave_acesso else cte_num
        
        # Complementa com informações corporativas/fiscais
        info_corp = corp_map.get(key_primary, corp_map.get(cte_num, {}))
        info_fiscal = fiscal_map.get(key_primary, fiscal_map.get(cte_num, {}))

        destinatario = str(row[col_destinatario]).strip() if col_destinatario and pd.notna(row[col_destinatario]) else ""
        if not destinatario or destinatario.lower() in ["nan", "none"]:
            destinatario = info_corp.get("destinatario", "")

        remetente = str(row[col_remetente]).strip() if col_remetente and pd.notna(row[col_remetente]) else ""
        if not remetente or remetente.lower() in ["nan", "none"]:
            remetente = info_corp.get("remetente", "")

        valor_final = converter_para_float_frete(row[col_valor_final]) if col_valor_final and pd.notna(row[col_valor_final]) else 0.0
        valor_sem_icms = converter_para_float_frete(row[col_valor_sem_icms]) if col_valor_sem_icms and pd.notna(row[col_valor_sem_icms]) else 0.0
        icms = converter_para_float_frete(row[col_icms]) if col_icms and pd.notna(row[col_icms]) else 0.0

        # O valor líquido de frete (Sem ICMS) é o principal para lançamento
        valor_exibicao = valor_sem_icms if valor_sem_icms > 0 else valor_final

        # Extrai OF buscando em 'Ordem de frete', 'OF' ou 'OF ORIGINAL'
        of_num = ""
        for possible_of_col in [col_of, "Ordem de frete", "OF", "OF ORIGINAL"]:
            if possible_of_col:
                col_found = encontrar_coluna(df_auditoria, [possible_of_col], "Auditoria") if isinstance(possible_of_col, str) else possible_of_col
                if col_found and col_found in df_auditoria.columns and pd.notna(row[col_found]):
                    val_o = str(row[col_found]).strip()
                    if val_o and val_o.lower() not in ["nan", "none", "", "-"]:
                        of_num = val_o
                        break

        rc_num = str(row[col_rc]).strip() if col_rc and pd.notna(row[col_rc]) else ""
        if rc_num.lower() in ["nan", "none"]: rc_num = ""

        status_text = str(row[col_status]).strip() if col_status and pd.notna(row[col_status]) else "Pendente"
        if status_text.lower() in ["nan", "none", ""]: status_text = "Pendente"

        fatura = str(row[col_fatura]).strip() if col_fatura and pd.notna(row[col_fatura]) else ""
        if fatura.lower() in ["nan", "none"]: fatura = ""

        vencimento = str(row[col_vencimento]).strip() if col_vencimento and pd.notna(row[col_vencimento]) else ""
        if vencimento.lower() in ["nan", "none"]: vencimento = ""

        planta_val = str(row[col_planta]).strip() if col_planta and pd.notna(row[col_planta]) else ""
        estab_val = str(row[col_estab]).strip() if col_estab and pd.notna(row[col_estab]) else "P716"
        if not planta_val or planta_val.lower() in ["nan", "none"]:
            planta_val = estab_val

        # Código numérico do emissor/fornecedor no SAP (Cód Emissor)
        cod_emissor_val = str(row[col_cod_emissor]).strip() if col_cod_emissor and pd.notna(row[col_cod_emissor]) else ""
        if cod_emissor_val.lower() in ["nan", "none"]: cod_emissor_val = ""
        # Remove casas decimais caso venha como float (ex: "9190617.0" → "9190617")
        if cod_emissor_val.endswith(".0"):
            cod_emissor_val = cod_emissor_val[:-2]

        item_cte = {
            "cte_key": key_primary,
            "cte_numero": cte_num,
            "chave_acesso": chave_acesso,
            "empresa": str(row[col_empresa]).strip() if col_empresa and pd.notna(row[col_empresa]) else "VMG1",
            "estab": estab_val,
            "planta": planta_val,
            "tipo": str(row[col_tipo]).strip() if col_tipo and pd.notna(row[col_tipo]) else "RC",
            "cod_emissor": cod_emissor_val,
            "emissor": str(row[col_emissor]).strip() if col_emissor and pd.notna(row[col_emissor]) else "N/A",
            "remetente": remetente,
            "destinatario": destinatario,
            "uf_origem": str(row[col_uf_origem]).strip() if col_uf_origem and pd.notna(row[col_uf_origem]) else "",
            "uf_destino": str(row[col_uf_destino]).strip() if col_uf_destino and pd.notna(row[col_uf_destino]) else "",
            "valor_final": round(valor_exibicao, 2),
            "valor_bruto": round(valor_final, 2),
            "valor_sem_icms": round(valor_sem_icms, 2),
            "icms": round(icms, 2),
            "of_numero": of_num,
            "rc_numero": rc_num,
            "fatura": fatura,
            "vencimento": vencimento,
            "status": status_text,
            "status_financeiro": info_fiscal.get("status_financeiro", "")
        }
        fretes_list.append(item_cte)

    # ── Incluir CT-es da planilha Corporativa que NÃO estão na Auditoria ──────
    keys_ja_incluidas = set(f["cte_key"] for f in fretes_list)

    if df_corp is not None:
        log_sys.write("🔄 Verificando CT-es exclusivos da planilha Corporativa...")

        # Mapear TODAS as colunas relevantes da Corporativa
        cc_cte = encontrar_coluna(df_corp, ["CT-E", "CTE", "NUMERO CTE", "NUM CTE"], "Corp")
        cc_chave = encontrar_coluna(df_corp, ["CHAVE DE ACESSO", "CHAVE", "CHAVE ACESSO"], "Corp")
        cc_empresa = encontrar_coluna(df_corp, ["EMPRESA", "EMP"], "Corp")
        cc_estab = encontrar_coluna(df_corp, ["ESTAB.", "ESTABELECIMENTO", "ESTAB"], "Corp")
        cc_planta = encontrar_coluna(df_corp, ["PLANTA", "UNIDADE"], "Corp")
        cc_tipo = encontrar_coluna(df_corp, ["TIPO", "TIPO FRETE", "TIPO CTE"], "Corp")
        cc_cod_emissor = encontrar_coluna(df_corp, ["CÓD EMISSOR", "COD EMISSOR", "CÓD. EMISSOR", "CODIGO EMISSOR", "COD. EMISSOR"], "Corp")
        cc_emissor = encontrar_coluna(df_corp, ["EMISSOR", "NOME EMISSOR", "TRANSPORTADORA"], "Corp")
        cc_remetente = encontrar_coluna(df_corp, ["REMETENTE", "NOME REMETENTE"], "Corp")
        cc_destinatario = encontrar_coluna(df_corp, ["DESTINATÁRIO", "DESTINATARIO", "CLIENTE"], "Corp")
        cc_valor_final = encontrar_coluna(df_corp, ["VALOR FINAL", "VALOR FRETE", "VALOR", "VALOR TOTAL"], "Corp")
        cc_valor_sem_icms = encontrar_coluna(df_corp, ["VALOR S/ ICMS", "VALOR SEM ICMS"], "Corp")
        cc_icms = encontrar_coluna(df_corp, ["ICMS", "VALOR ICMS"], "Corp")
        cc_of = encontrar_coluna(df_corp, ["OF", "ORDEM DE FRETE", "Nº OF"], "Corp")
        cc_rc = encontrar_coluna(df_corp, ["RC", "REQUISICAO", "REQUISIÇÃO"], "Corp")
        cc_fatura = encontrar_coluna(df_corp, ["FATURA", "NUM FATURA"], "Corp")
        cc_vencimento = encontrar_coluna(df_corp, ["VENCIMENTO", "DT VENCIMENTO"], "Corp")
        cc_status = encontrar_coluna(df_corp, ["STATUS", "SITUACAO", "SITUAÇÃO"], "Corp")
        cc_uf_origem = encontrar_coluna(df_corp, ["UF ORIGEM", "UF ORIG"], "Corp")
        cc_uf_destino = encontrar_coluna(df_corp, ["UF DESTINO", "UF DEST"], "Corp")

        count_novos_corp = 0
        for idx, row in df_corp.iterrows():
            cte_num = str(row[cc_cte]).strip() if cc_cte and pd.notna(row[cc_cte]) else ""
            chave_acesso = str(row[cc_chave]).strip() if cc_chave and pd.notna(row[cc_chave]) else ""

            if not cte_num and not chave_acesso:
                continue
            if cte_num.lower() in ["nan", "none", "ct-e", "cte"] or chave_acesso.lower() in ["nan", "none"]:
                continue

            key_primary = chave_acesso if chave_acesso else cte_num

            # Pular se já existe na lista (veio da Auditoria)
            if key_primary in keys_ja_incluidas:
                continue

            info_fiscal = fiscal_map.get(key_primary, fiscal_map.get(cte_num, {}))

            destinatario = str(row[cc_destinatario]).strip() if cc_destinatario and pd.notna(row[cc_destinatario]) else ""
            if destinatario.lower() in ["nan", "none"]: destinatario = ""

            remetente = str(row[cc_remetente]).strip() if cc_remetente and pd.notna(row[cc_remetente]) else ""
            if remetente.lower() in ["nan", "none"]: remetente = ""

            valor_final = converter_para_float_frete(row[cc_valor_final]) if cc_valor_final and pd.notna(row[cc_valor_final]) else 0.0
            valor_sem_icms = converter_para_float_frete(row[cc_valor_sem_icms]) if cc_valor_sem_icms and pd.notna(row[cc_valor_sem_icms]) else 0.0
            icms = converter_para_float_frete(row[cc_icms]) if cc_icms and pd.notna(row[cc_icms]) else 0.0

            valor_exibicao = valor_sem_icms if valor_sem_icms > 0 else valor_final

            # Extrai OF
            of_num = ""
            for possible_of_col in [cc_of, "Ordem de frete", "OF", "OF ORIGINAL"]:
                if possible_of_col:
                    col_found = encontrar_coluna(df_corp, [possible_of_col], "Corp") if isinstance(possible_of_col, str) else possible_of_col
                    if col_found and col_found in df_corp.columns and pd.notna(row[col_found]):
                        val_o = str(row[col_found]).strip()
                        if val_o and val_o.lower() not in ["nan", "none", "", "-"]:
                            of_num = val_o
                            break

            rc_num = str(row[cc_rc]).strip() if cc_rc and pd.notna(row[cc_rc]) else ""
            if rc_num.lower() in ["nan", "none"]: rc_num = ""

            status_text = str(row[cc_status]).strip() if cc_status and pd.notna(row[cc_status]) else "Pendente"
            if status_text.lower() in ["nan", "none", ""]: status_text = "Pendente"

            fatura = str(row[cc_fatura]).strip() if cc_fatura and pd.notna(row[cc_fatura]) else ""
            if fatura.lower() in ["nan", "none"]: fatura = ""

            vencimento = str(row[cc_vencimento]).strip() if cc_vencimento and pd.notna(row[cc_vencimento]) else ""
            if vencimento.lower() in ["nan", "none"]: vencimento = ""

            planta_val = str(row[cc_planta]).strip() if cc_planta and pd.notna(row[cc_planta]) else ""
            estab_val = str(row[cc_estab]).strip() if cc_estab and pd.notna(row[cc_estab]) else "P716"
            if not planta_val or planta_val.lower() in ["nan", "none"]:
                planta_val = estab_val

            cod_emissor_val = str(row[cc_cod_emissor]).strip() if cc_cod_emissor and pd.notna(row[cc_cod_emissor]) else ""
            if cod_emissor_val.lower() in ["nan", "none"]: cod_emissor_val = ""
            if cod_emissor_val.endswith(".0"):
                cod_emissor_val = cod_emissor_val[:-2]

            item_cte = {
                "cte_key": key_primary,
                "cte_numero": cte_num,
                "chave_acesso": chave_acesso,
                "empresa": str(row[cc_empresa]).strip() if cc_empresa and pd.notna(row[cc_empresa]) else "VMG1",
                "estab": estab_val,
                "planta": planta_val,
                "tipo": str(row[cc_tipo]).strip() if cc_tipo and pd.notna(row[cc_tipo]) else "RC",
                "cod_emissor": cod_emissor_val,
                "emissor": str(row[cc_emissor]).strip() if cc_emissor and pd.notna(row[cc_emissor]) else "N/A",
                "remetente": remetente,
                "destinatario": destinatario,
                "uf_origem": str(row[cc_uf_origem]).strip() if cc_uf_origem and pd.notna(row[cc_uf_origem]) else "",
                "uf_destino": str(row[cc_uf_destino]).strip() if cc_uf_destino and pd.notna(row[cc_uf_destino]) else "",
                "valor_final": round(valor_exibicao, 2),
                "valor_bruto": round(valor_final, 2),
                "valor_sem_icms": round(valor_sem_icms, 2),
                "icms": round(icms, 2),
                "of_numero": of_num,
                "rc_numero": rc_num,
                "fatura": fatura,
                "vencimento": vencimento,
                "status": status_text,
                "status_financeiro": info_fiscal.get("status_financeiro", "")
            }
            fretes_list.append(item_cte)
            keys_ja_incluidas.add(key_primary)
            count_novos_corp += 1

        log_sys.write(f"📋 {count_novos_corp} CT-e(s) adicionados exclusivamente da planilha Corporativa.")

    lancamento_frete_estado["fretes"] = fretes_list
    lancamento_frete_estado["auditoria_caminho"] = auditoria_id
    lancamento_frete_estado["corporativo_caminho"] = corporativo_id
    lancamento_frete_estado["selecionados"] = []

    # Inicializa status_etapas
    for f in fretes_list:
        k = f["cte_key"]
        if k not in lancamento_frete_estado["status_etapas"]:
            lancamento_frete_estado["status_etapas"][k] = {
                "status": "success" if "ok" in f["status"].lower() or "escriturado" in f["status"].lower() else "pending",
                "detalhe": "",
                "of": f["of_numero"],
                "rc": f["rc_numero"]
            }

    log_sys.write(f"🎉 Total de {len(fretes_list)} registros de frete consolidados com sucesso!")
    return fretes_list

def _formatar_valor_sap(valor_float: float) -> str:
    """
    Converte um float para o formato SAP de valor monetário:
    ponto como separador de milhar, vírgula como decimal.
    Ex: 2664.78 → "2.664,78"
    """
    return f"{valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def rodar_processamento_lancamento_frete(
    ctes_selecionados: list,
    centro_custo: str,
    caminho_anexo: str = "",
    arquivo_anexo: str = "",
):
    """
    Executa a criação de RCs no SAP ME51N para os fretes selecionados.

    Agrupa os CTes selecionados por Cód Emissor (fornecedor SAP) e cria
    uma RC por grupo usando criar_rc_cte().

    Parâmetros
    ----------
    ctes_selecionados : list de cte_keys
    centro_custo      : código do CC (ex: "AQ203")
    caminho_anexo     : pasta do arquivo de anexo (ex: "C:\\Users\\...\\Downloads\\")
    arquivo_anexo     : nome do arquivo (ex: "Tabela_Cabotagem_2026.xlsx")
    """
    global lancamento_frete_estado
    lancamento_frete_estado["selecionados"] = ctes_selecionados

    log_sys.write("=== [Lançamento de Fretes P716] Iniciando Criação de RCs no SAP ===")
    log_sys.write(f"   Centro de Custo : {centro_custo}")
    log_sys.write(f"   Anexo           : {arquivo_anexo or '(nenhum)'}")
    log_sys.write(f"   CTes selecionados: {len(ctes_selecionados)}")

    # Marca todos como 'running'
    for key_sel in ctes_selecionados:
        lancamento_frete_estado["status_etapas"].setdefault(key_sel, {})
        lancamento_frete_estado["status_etapas"][key_sel].update({
            "status": "running",
            "detalhe": "Aguardando processamento...",
            "rc": ""
        })

    # Localiza os registros selecionados
    fretes_sel = [
        f for f in lancamento_frete_estado["fretes"]
        if f["cte_key"] in ctes_selecionados
    ]

    if not fretes_sel:
        log_sys.write("⚠️ Nenhum registro encontrado para as keys selecionadas.")
        return

    # Agrupa por Cód Emissor (um grupo = uma RC no SAP)
    grupos: dict = defaultdict(list)
    sem_codigo: list = []
    for f in fretes_sel:
        cod = f.get("cod_emissor", "").strip()
        if cod:
            grupos[cod].append(f)
        else:
            sem_codigo.append(f)
            log_sys.write(f"⚠️ CT-e {f['cte_numero']} sem Cód Emissor – será ignorado.")
            lancamento_frete_estado["status_etapas"][f["cte_key"]].update({
                "status": "error",
                "detalhe": "Sem Cód Emissor na planilha"
            })

    if not grupos:
        log_sys.write("❌ Nenhum CT-e com Cód Emissor válido para processar.")
        return

    # Conecta ao SAP GUI
    from src.utils.sap_utils import conectar_sap
    session = conectar_sap()
    if not session:
        log_sys.write("❌ Não foi possível conectar ao SAP GUI. Verifique se o SAP está aberto.")
        for f in fretes_sel:
            if f.get("cod_emissor"):
                lancamento_frete_estado["status_etapas"][f["cte_key"]].update({
                    "status": "error", "detalhe": "SAP GUI não disponível"
                })
        return

    # Importa a automação de RC
    from src.expedicao.sap_rc_cte import criar_rc_cte

    # Processa cada grupo de fornecedor
    for cod_emissor, itens in grupos.items():
        nome_emissor = itens[0].get("emissor", cod_emissor)
        log_sys.write(f"\n🚚 Grupo: Fornecedor {cod_emissor} ({nome_emissor}) – {len(itens)} CT-e(s)")

        # Monta a lista de CTes para criar_rc_cte()
        # Valor principal: Valor S/ ICMS (col_valor_sem_icms); fallback: valor_final
        ctes_payload = []
        for f in itens:
            valor = f.get("valor_sem_icms") or f.get("valor_final") or 0.0
            ctes_payload.append({
                "numero": f["cte_numero"],
                "valor": _formatar_valor_sap(valor)
            })
            log_sys.write(f"   CT-e {f['cte_numero']} | Valor S/ ICMS: R$ {valor:,.2f} → SAP: {_formatar_valor_sap(valor)}")

        try:
            rc_gerada = criar_rc_cte(
                session=session,
                ctes=ctes_payload,
                centro_custo=centro_custo,
                fornecedor=cod_emissor,
                caminho_anexo=caminho_anexo,
                arquivo_anexo=arquivo_anexo,
                prefixo_cabecalho=f"Fretes {nome_emissor}",
                salvar=True,
            )

            log_sys.write(f"✅ RC gerada para fornecedor {cod_emissor}: {rc_gerada}")

            # Atualiza status de cada CT-e do grupo
            for f in itens:
                lancamento_frete_estado["status_etapas"][f["cte_key"]].update({
                    "status": "success",
                    "detalhe": f"RC: {rc_gerada}",
                    "rc": rc_gerada
                })

        except Exception as ex:
            log_sys.write(f"❌ Erro ao criar RC para fornecedor {cod_emissor}: {ex}")
            for f in itens:
                lancamento_frete_estado["status_etapas"][f["cte_key"]].update({
                    "status": "error",
                    "detalhe": str(ex),
                    "rc": ""
                })

    log_sys.write("\n🎉 Processamento de Lançamento de Fretes concluído!")

def montar_relatorio_lancamento_frete(estado=None) -> pd.DataFrame:
    """Gera um DataFrame formatado para exportação Excel."""
    estado = estado or lancamento_frete_estado
    linhas = []

    fretes = estado.get("fretes", []) or []
    selecionados = estado.get("selecionados", []) or []

    if selecionados:
        fretes = [f for f in fretes if f.get("cte_key") in selecionados]

    for f in fretes:
        k = f.get("cte_key")
        st_info = estado.get("status_etapas", {}).get(k, {})
        linhas.append({
            "Empresa": f.get("empresa"),
            "Estabelecimento": f.get("estab"),
            "Tipo": f.get("tipo"),
            "CT-e": f.get("cte_numero"),
            "Chave de Acesso": f.get("chave_acesso"),
            "Emissor (Transportadora)": f.get("emissor"),
            "Remetente": f.get("remetente"),
            "Destinatário (Cliente)": f.get("destinatario"),
            "UF Origem": f.get("uf_origem"),
            "UF Destino": f.get("uf_destino"),
            "Valor Final (R$)": f.get("valor_final"),
            "Valor S/ ICMS (R$)": f.get("valor_sem_icms"),
            "ICMS (R$)": f.get("icms"),
            "OF": f.get("of_numero"),
            "RC": f.get("rc_numero"),
            "Fatura": f.get("fatura"),
            "Vencimento": f.get("vencimento"),
            "Status Planilha": f.get("status"),
            "Status Processamento": st_info.get("status", "pending")
        })

    if not linhas:
        linhas.append({
            "CT-e": "", "Chave de Acesso": "", "Emissor": "", "Status": "Nenhum registro"
        })

    return pd.DataFrame(linhas)
