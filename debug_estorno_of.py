"""
Script de diagnóstico e execução direta para Estorno de Ordens de Frete (OF).

Exemplos de uso:
1. Estornar uma única OF diretamente:
   python debug_estorno_of.py --of 6100319463 --doc 4500751841

2. Processar a planilha de teste:
   python debug_estorno_of.py --planilha "C:\\Users\\ismael.nascimento\\OneDrive - VALGROUP\\Scripts\\Estornos OF's\\Ajuste Outubro26 contabilidade FRETE - estorno  arq final 1.xlsx" --limite 2

3. Modo interativo:
   python debug_estorno_of.py
"""

import os
import sys
import argparse

# Raiz do projeto no sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.common import log_sys
from src.expedicao.sap_estorno_of import (
    estornar_of_individual,
    carregar_dados_estorno_planilha,
    executar_estorno_of_lote,
    atualizar_planilha_estorno,
)


def main():
    parser = argparse.ArgumentParser(description="Automação de Estorno de Ordem de Frete (OF) via SAP Playwright")
    parser.add_argument("--of", type=str, help="Número da Ordem de Frete (ex: 6100319463)")
    parser.add_argument("--doc", type=str, help="Documento de Compras / PO (ex: 4500751841)")
    parser.add_argument("--planilha", type=str, help="Caminho do arquivo Excel com os dados")
    parser.add_argument("--limite", type=int, default=0, help="Limite de itens a processar da planilha (0 = todos)")
    parser.add_argument("--headless", action="store_true", help="Executar em segundo plano sem abrir a janela do navegador")

    args = parser.parse_args()

    # Caso 1: OF e Documento de compras passados diretamente via linha de comando
    if args.of and args.doc:
        print(f"\n🚀 [Modo Individual] Iniciando estorno da OF {args.of} com PO {args.doc} (Headless: {args.headless})...")
        res = estornar_of_individual(
            of_numero=args.of,
            doc_compras=args.doc,
            headless=args.headless,
            caminho_planilha=args.planilha,
        )
        print("\n📊 Resultado:")
        for k, v in res.items():
            print(f"  {k}: {v}")
        return

    # Caso 2: Planilha informada via argumento
    if args.planilha:
        caminho_excel = os.path.abspath(args.planilha)
        if not os.path.isfile(caminho_excel):
            print(f"❌ Arquivo não encontrado: {caminho_excel}")
            return

        print(f"\n📂 Carregando dados da planilha: {caminho_excel}")
        itens = carregar_dados_estorno_planilha(caminho_excel)
        print(f"✅ {len(itens)} item(ns) encontrado(s).")

        if args.limite > 0:
            itens = itens[:args.limite]
            print(f"ℹ️ Limitando execução aos primeiros {args.limite} itens.")

        print(f"🚀 Iniciando processamento de {len(itens)} item(ns)...")
        resultados = executar_estorno_of_lote(
            itens=itens,
            headless=args.headless,
            caminho_planilha=caminho_excel,
        )
        print("\n📊 Resumo da Execução:")
        sucessos = sum(1 for r in resultados if r.get("sucesso"))
        erros = len(resultados) - sucessos
        print(f"  Total: {len(resultados)} | Sucessos: {sucessos} | Erros: {erros}")
        return

    # Caso 3: Modo interativo
    print("\n" + "=" * 60)
    print("🤖 RPA LOGÍSTICA - ESTORNO DE ORDENS DE FRETE (OF)")
    print("=" * 60)
    print("1. Executar estorno de uma OF individual")
    print("2. Processar planilha de estornos")
    print("0. Sair")

    opcao = input("\nEscolha uma opção (1/2/0): ").strip()

    if opcao == "1":
        of_num = input("Digite o número da Ordem de Frete (OF): ").strip()
        doc_compras = input("Digite o Documento de Compras (PO): ").strip()
        if not of_num or not doc_compras:
            print("❌ Número da OF e Documento de Compras são obrigatórios.")
            return

        print(f"\n🚀 Iniciando estorno da OF {of_num}...")
        res = estornar_of_individual(of_numero=of_num, doc_compras=doc_compras, headless=args.headless)
        print("\n📊 Resultado:")
        for k, v in res.items():
            print(f"  {k}: {v}")

    elif opcao == "2":
        default_path = r"C:\Users\ismael.nascimento\OneDrive - VALGROUP\Scripts\Estornos OF's\Ajuste Outubro26 contabilidade FRETE - estorno  arq final 1.xlsx"
        print(f"\nCaminho padrão sugerido:\n{default_path}")
        caminho = input("Pressione ENTER para usar o caminho padrão ou digite o caminho da planilha: ").strip()
        if not caminho:
            caminho = default_path

        if not os.path.isfile(caminho):
            print(f"❌ Arquivo não encontrado: {caminho}")
            return

        itens = carregar_dados_estorno_planilha(caminho)
        print(f"✅ {len(itens)} item(ns) encontrado(s) na planilha.")

        limite_str = input("Deseja limitar a quantidade de itens? (Digite o número ou ENTER para todos): ").strip()
        if limite_str.isdigit() and int(limite_str) > 0:
            itens = itens[:int(limite_str)]

        print(f"\n🚀 Iniciando lote de {len(itens)} item(ns)...")
        resultados = executar_estorno_of_lote(
            itens=itens,
            headless=args.headless,
            caminho_planilha=caminho,
        )
        sucessos = sum(1 for r in resultados if r.get("sucesso"))
        erros = len(resultados) - sucessos
        print(f"\n📊 Processamento finalizado! Total: {len(resultados)} | Sucessos: {sucessos} | Erros: {erros}")
    else:
        print("Operação cancelada.")


if __name__ == "__main__":
    main()

