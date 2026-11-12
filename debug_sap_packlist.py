"""Executa isoladamente o download de Packlists no SAP Web.

Exemplos:
    python debug_sap_packlist.py 80000001
    python debug_sap_packlist.py 80000001,80000002 --tipo jbs
    python debug_sap_packlist.py 80000001 --destino C:\\Temp\\packlists

As credenciais sao lidas de ``SAP_WEB_USER`` e ``SAP_WEB_PASSWORD`` no
arquivo ``.env`` da raiz do projeto.
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


RAIZ_PROJETO = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ_PROJETO))

from src.expedicao.sap_packlist import baixar_packlist_sap


# Configuracoes usadas quando o script for executado sem argumentos.
# Tambem e possivel manter esta lista vazia e informar as remessas pela linha
# de comando, conforme os exemplos no inicio do arquivo.
REMESSAS_TESTE = ['80796156']
TIPO_PACKLIST = "normal"  # "normal" ou "jbs"
PASTA_DESTINO = RAIZ_PROJETO / "output" / "packlists"


def _interpretar_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Baixa Packlists do SAP Web para fins de depuracao."
    )
    parser.add_argument(
        "remessas",
        nargs="*",
        help="Numeros de remessa, separados por espaco ou virgula.",
    )
    parser.add_argument(
        "--tipo",
        choices=("normal", "jbs"),
        default=TIPO_PACKLIST,
        help=f"Fluxo do Packlist (padrao: {TIPO_PACKLIST}).",
    )
    parser.add_argument(
        "--destino",
        type=Path,
        default=PASTA_DESTINO,
        help=f"Pasta dos PDFs (padrao: {PASTA_DESTINO}).",
    )
    return parser.parse_args()


def _normalizar_remessas(valores: list[str]) -> list[str]:
    remessas = []
    for valor in valores:
        remessas.extend(item.strip() for item in valor.split(","))
    return [remessa for remessa in remessas if remessa]


def main() -> int:
    args = _interpretar_argumentos()
    remessas = _normalizar_remessas(args.remessas) or REMESSAS_TESTE

    if not remessas:
        print("Erro: informe ao menos uma remessa na linha de comando ou em REMESSAS_TESTE.")
        return 2

    load_dotenv(RAIZ_PROJETO / ".env")
    usuario = os.getenv("SAP_WEB_USER", "").strip()
    senha = os.getenv("SAP_WEB_PASSWORD", "")

    if not usuario or not senha:
        print(
            "Erro: configure SAP_WEB_USER e SAP_WEB_PASSWORD no arquivo .env "
            "da raiz do projeto."
        )
        return 2

    pasta_destino = args.destino.expanduser().resolve()

    print("=" * 60)
    print("DEBUG - DOWNLOAD DE PACKLIST DO SAP")
    print("=" * 60)
    print(f"Usuario: {usuario}")
    print(f"Remessas: {', '.join(remessas)}")
    print(f"Tipo: {args.tipo}")
    print(f"Destino: {pasta_destino}")
    print("Iniciando o navegador para executar o fluxo do SAP...")
    print("-" * 60)

    try:
        baixar_packlist_sap(
            remessas=remessas,
            pasta_destino=str(pasta_destino),
            usuario=usuario,
            senha=senha,
            tipo=args.tipo,
        )
    except KeyboardInterrupt:
        print("\nExecucao interrompida pelo usuario.")
        return 130
    except Exception as exc:
        print(f"Erro inesperado: {type(exc).__name__}: {exc}")
        return 1

    arquivos_encontrados = [
        pasta_destino / f"PackingList_{remessa}.pdf" for remessa in remessas
    ]
    arquivos_encontrados = [arquivo for arquivo in arquivos_encontrados if arquivo.is_file()]

    print("-" * 60)
    print(
        f"Finalizado: {len(arquivos_encontrados)}/{len(remessas)} "
        "arquivo(s) encontrado(s) no destino."
    )
    for arquivo in arquivos_encontrados:
        print(f"  OK: {arquivo}")

    return 0 if len(arquivos_encontrados) == len(remessas) else 1


if __name__ == "__main__":
    raise SystemExit(main())
