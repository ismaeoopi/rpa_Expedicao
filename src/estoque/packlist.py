import pandas as pd
import math

def analisar_planilha_packlist(caminho_arquivo):
    """
    Analisa um arquivo Excel de Packlist e consolida as informações
    de volume, peso e itens de forma inteligente usando heurísticas
    para encontrar as colunas adequadas.
    """
    try:
        df = pd.read_excel(caminho_arquivo)
        
        # Limpar nomes das colunas
        df.columns = [str(col).strip().lower() for col in df.columns]
        
        # Heurísticas para nomes de colunas
        peso_keywords = ['peso', 'weight', 'kg', 'líquido', 'bruto']
        vol_keywords = ['vol', 'volume', 'm3', 'cbm']
        item_keywords = ['item', 'material', 'sku', 'produto', 'código', 'cod']
        qtd_keywords = ['qtd', 'qty', 'quantidade', 'quant']

        def encontrar_coluna(keywords):
            for col in df.columns:
                if any(kw in col for kw in keywords):
                    return col
            return None

        col_peso = encontrar_coluna(peso_keywords)
        col_vol = encontrar_coluna(vol_keywords)
        col_item = encontrar_coluna(item_keywords)
        col_qtd = encontrar_coluna(qtd_keywords)

        # Consolidar dados
        total_peso = 0.0
        total_vol = 0.0
        total_qtd = 0.0
        total_itens = 0
        
        # Helper function to convert to float safely
        def safe_sum(col_name):
            if col_name and col_name in df.columns:
                # Replace commas with dots if they are strings representing numbers
                s = df[col_name].astype(str).str.replace(',', '.')
                # Extract numbers
                s = pd.to_numeric(s, errors='coerce')
                return float(s.sum())
            return 0.0

        total_peso = safe_sum(col_peso)
        total_vol = safe_sum(col_vol)
        total_qtd = safe_sum(col_qtd)

        # Total de itens únicos (ou total de linhas se a coluna não for achada)
        if col_item and col_item in df.columns:
            total_itens = df[col_item].nunique()
        else:
            total_itens = len(df)
            
        # Top 5 itens por quantidade (se disponível)
        top_itens = []
        if col_item and col_qtd and col_item in df.columns and col_qtd in df.columns:
            # Dropna for aggregation
            df_itens = df[[col_item, col_qtd]].dropna()
            df_itens[col_qtd] = pd.to_numeric(df_itens[col_qtd].astype(str).str.replace(',', '.'), errors='coerce')
            agg_df = df_itens.groupby(col_item)[col_qtd].sum().reset_index()
            agg_df = agg_df.sort_values(by=col_qtd, ascending=False).head(5)
            
            for _, row in agg_df.iterrows():
                top_itens.append({
                    "item": str(row[col_item]),
                    "qtd": float(row[col_qtd])
                })

        return {
            "status": "success",
            "data": {
                "total_peso": round(total_peso, 2),
                "total_volume": round(total_vol, 3),
                "total_quantidade": round(total_qtd, 2) if total_qtd > 0 else len(df),
                "total_itens_unicos": total_itens,
                "colunas_identificadas": {
                    "peso": col_peso or "Não encontrada",
                    "volume": col_vol or "Não encontrada",
                    "item": col_item or "Não encontrada",
                    "quantidade": col_qtd or "Não encontrada"
                },
                "top_itens": top_itens,
                "total_linhas": len(df)
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Erro ao processar a planilha: {str(e)}"
        }
