import os
import io
import pandas as pd
from datetime import timedelta
from src.utils.common import log_sys

ABA = "Picking"
colunaRemessa = "REMESSA"
colunaUc = "UC"

def valorFloatexcel(valor):
    if pd.isna(valor) or valor is None or str(valor).strip() == "":
        return ""
    valor_str = str(valor).strip()
    if "," in valor_str:
        valorParaFloat = valor_str.replace(".","").replace(",",".")
    else:
        valorParaFloat = valor_str
    try:
        valorRound = round(float(valorParaFloat),3)
        return f"{valorRound:.3f}".replace('.',',')
    except ValueError:
        log_sys.write(f"Erro ao converter o valor '{valor}' para float.")
        return 0.0

def valorFloatPy(valor):
    if valor is None:
        return 0.0
    valorStr = str(valor).strip()
    if not valorStr:
        return 0.0
    valorStr = valorStr.replace(".","").replace(",",".")
    try:
        return round(float(valorStr),3)
    except ValueError:
        log_sys.write(f"Erro ao converter o valor '{valor}' para float.")
        return 0.0

def lerExcel(caminho):
    caminhoAbsoluto = os.path.abspath(caminho)
    log_sys.write(f"📂 Lendo planilha em: {caminhoAbsoluto}")
    try:
        df = pd.read_excel(caminhoAbsoluto, sheet_name=ABA, dtype=str)
        df.dropna(subset=[colunaRemessa], inplace=True)
        log_sys.write(f"✅ Planilha lida com sucesso: {len(df)} linhas para processar.")
        return df
    except FileNotFoundError:
        log_sys.write(f"❌ ERRO: O arquivo '{caminhoAbsoluto}' não foi encontrado.")
        return None
    except PermissionError:
        log_sys.write("❌ ERRO: Permissão negada. A planilha está aberta! Feche-a para continuar.")
        return None
    except Exception as e:
        log_sys.write(f"❌ ERRO ao ler a planilha: {e}")
        return None

def lerDados(caminhoExcel, dados_colados=None):
    if dados_colados and str(dados_colados).strip():
        try:
            log_sys.write("📄 Lendo dados colados diretamente da interface...")
            df = pd.read_csv(io.StringIO(dados_colados), sep='\t', dtype=str)
            df.columns = [str(c).strip().upper() for c in df.columns]
            if colunaRemessa not in df.columns:
                 log_sys.write(f"❌ ERRO: Coluna '{colunaRemessa}' não encontrada nos dados colados.")
                 return None
            df.dropna(subset=[colunaRemessa], inplace=True)
            log_sys.write(f"✅ Dados colados lidos com sucesso: {len(df)} linhas para processar.")
            return df
        except Exception as e:
            log_sys.write(f"❌ ERRO ao processar dados colados: {e}")
            return None
            return None
    else:
        return lerExcel(caminhoExcel)

def tratar_datas(valor_data):
    """Retorna (Data Produção, Data Vencimento)"""
    if pd.isna(valor_data): return "", ""
    try:
        dt = pd.to_datetime(valor_data)
        dt_prod = dt.strftime("%d.%m.%Y") # Ajustado para . porque a data SAP geralmente usa .
        dt_prod_br = dt.strftime("%d%m%Y") 
        dt_venc = (dt + timedelta(days=365)).strftime("%d%m%Y")
        return dt_prod_br, dt_venc
    except: return "", ""

def ler_excel_universal(caminho, aba, coluna_validacao=0):
    """Função única para ler Excel, substituindo as 3 anteriores."""
    try:
        log_sys.write(f"📂 Lendo: {aba}...")
        # Lê tudo como string para evitar erros de conversão automática do pandas
        df = pd.read_excel(caminho, sheet_name=aba, dtype=str)
        
        # Validação dinâmica da coluna (pode ser índice ou nome)
        if isinstance(coluna_validacao, int):
            df.dropna(subset=[df.columns[coluna_validacao]], inplace=True)
        else:
             if coluna_validacao in df.columns:
                df.dropna(subset=[coluna_validacao], inplace=True)
        
        log_sys.write(f"✅ {len(df)} linhas carregadas.")
        return df
    except Exception as e:
        log_sys.write(f"❌ Erro ao ler Excel: {e}")
        return None
