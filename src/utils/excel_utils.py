import os
import io
import pandas as pd
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
    else:
        return lerExcel(caminhoExcel)
