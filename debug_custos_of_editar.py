"""
debug_custos_of_editar.py
=========================
Script de depuração/teste para EDITAR os custos de uma OF no SAP Fiori
(transação FreightOrder-changeRoad) via Playwright (navegador Web).

Caso de uso configurado:
  OF     : 6100325111
  Linhas : CAMIL - 1.817,27
           CAMIL - 1.817,27
  → Como ambas são o mesmo cliente, os valores são SOMADOS automaticamente
    e o SAP recebe apenas UMA edição: CAMIL → 3.634,54

Regra de agrupamento (automática):
  Se dois ou mais itens de EDICOES tiverem o mesmo texto_linha,
  seus valores são somados antes de enviar ao SAP.
  Isso evita tentar editar a mesma linha duas vezes.

Como usar:
  1. Certifique-se de que o arquivo .env contém SAP_WEB_USER e SAP_WEB_PASSWORD.
  2. Execute:
        python debug_custos_of_editar.py

Modos disponíveis:
  SALVAR = False  → preenche os campos no navegador mas NÃO grava no SAP (modo seguro)
  SALVAR = True   → pressiona Ctrl+S e salva a OF no SAP
"""

import os
import sys
from collections import OrderedDict

# ── garante que a raiz do projeto esteja no path ──────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.expedicao.sap_custos_of import consultar_e_editar_custos_of


# =============================================================================
# ⚙️  CONFIGURAÇÕES DE TESTE  –  EDITE AQUI
# =============================================================================

OF_NUMERO = "6100327025"

# Liste aqui todos os itens de custo — inclusive repetidos.
# Se o mesmo cliente aparecer mais de uma vez, os valores serão SOMADOS
# e apenas UMA edição será enviada ao SAP (pois o SAP exibe uma linha por cliente).
#
# Formato do valor: use ponto como separador de milhar e vírgula como decimal
# (padrão SAP Brasil). Exemplos: "1.817,27" | "500,00" | "12.345,67"
EDICOES = [
    {"texto_linha": "ASB", "valor": "807,21"},
    {"texto_linha": "FOUNTAIN", "valor": "780,99"},
]

# True  → salva a OF no SAP (Ctrl+S) ao final de todas as edições
# False → preenche o valor na tela mas NÃO salva (modo seguro para testes)
SALVAR = False

# False → exibe o navegador durante a automação (recomendado para debug)
# True  → roda em background sem janela
HEADLESS = False

# Segundos para manter o navegador aberto após a última edição (útil para conferir)
TEMPO_ESPERA_VISUAL = 30

# =============================================================================


def _parse_valor_sap(valor_str: str) -> float:
    """
    Converte valor no formato SAP Brasil para float.
    Exemplos: '1.817,27' → 1817.27 | '500,00' → 500.0
    """
    # Remove separador de milhar (ponto) e converte decimal (vírgula → ponto)
    return float(valor_str.replace(".", "").replace(",", "."))


def _format_valor_sap(valor_float: float) -> str:
    """
    Converte float para o formato SAP Brasil (vírgula decimal, ponto milhar).
    Exemplos: 3634.54 → '3.634,54' | 500.0 → '500,00'
    """
    # Formata com 2 casas decimais e separadores no padrão pt-BR
    partes = f"{valor_float:,.2f}"          # '3,634.54' (padrão en-US)
    # Inverte separadores: '.' → milhar, ',' → decimal
    partes = partes.replace(",", "X").replace(".", ",").replace("X", ".")
    return partes


def _agrupar_edicoes(edicoes: list) -> tuple[list, list]:
    """
    Agrupa as edições pelo texto_linha, somando os valores de clientes repetidos.

    Retorna:
        edicoes_agrupadas : lista final a enviar ao SAP (um item por cliente único)
        log_agrupamento   : linhas de texto descrevendo o que foi somado (para exibição)
    """
    acumulador: OrderedDict = OrderedDict()  # mantém a ordem de inserção

    for ed in edicoes:
        chave = (ed.get("texto_linha", "").strip().upper(), ed.get("linha_editar", 1))
        texto = ed.get("texto_linha", "").strip()
        valor = _parse_valor_sap(ed.get("valor", "0,00"))

        if texto.upper() in [k[0] for k in acumulador]:
            # Já existe → somar ao valor acumulado (usa a chave do primeiro encontrado)
            chave_existente = next(k for k in acumulador if k[0] == texto.upper())
            acumulador[chave_existente]["valor_float"] += valor
            acumulador[chave_existente]["parcelas"].append(ed.get("valor", "0,00"))
        else:
            acumulador[chave] = {
                "texto_linha": texto,
                "linha_editar": ed.get("linha_editar", 1),
                "valor_float": valor,
                "parcelas": [ed.get("valor", "0,00")],
            }

    edicoes_agrupadas = []
    log_agrupamento = []

    for dados in acumulador.values():
        valor_final = _format_valor_sap(dados["valor_float"])
        edicoes_agrupadas.append({
            "texto_linha": dados["texto_linha"],
            "linha_editar": dados["linha_editar"],
            "valor": valor_final,
        })

        if len(dados["parcelas"]) > 1:
            soma_str = " + ".join(dados["parcelas"])
            log_agrupamento.append(
                f"  ➕ '{dados['texto_linha']}' (valores somados): "
                f"{soma_str} = {valor_final}"
            )
        else:
            log_agrupamento.append(
                f"  • '{dados['texto_linha']}' → {valor_final}"
            )

    return edicoes_agrupadas, log_agrupamento


def separador(titulo: str = "") -> None:
    linha = "─" * 60
    if titulo:
        print(f"\n{linha}")
        print(f"  {titulo}")
        print(linha)
    else:
        print(linha)


def main():
    separador("🛠️  DEBUG – EDIÇÃO DE CUSTOS DE OF NO SAP FIORI")
    print(f"  OF           : {OF_NUMERO}")
    print(f"  Salvar       : {'✅ SIM' if SALVAR else '❌ NÃO (modo teste)'}")
    print(f"  Headless     : {'Sim' if HEADLESS else 'Não (navegador visível)'}")
    print(f"  Itens config : {len(EDICOES)}")
    print()

    # ── Agrupar/somar itens com o mesmo cliente ────────────────────────────────
    edicoes_final, log_group = _agrupar_edicoes(EDICOES)

    print("  📋 Edições após agrupamento (o que será enviado ao SAP):")
    for linha in log_group:
        print(linha)

    houve_agrupamento = len(edicoes_final) < len(EDICOES)
    if houve_agrupamento:
        print()
        print(f"  ℹ️  {len(EDICOES)} itens configurados → {len(edicoes_final)} edição(ões) "
              f"(clientes repetidos foram somados)")

    separador()

    try:
        # ─── UMA única chamada → UMA única sessão do browser ──────────────────
        res = consultar_e_editar_custos_of(
            of_numero=OF_NUMERO,
            salvar=SALVAR,
            headless=HEADLESS,
            tempo_espera_visual=TEMPO_ESPERA_VISUAL,
            edicoes=edicoes_final,    # ← lista já agrupada/somada
        )

        # ── Resumo dos resultados ──────────────────────────────────────────────
        separador("📊  RESULTADO FINAL")
        print(f"  OF processada  : {res.get('of_numero')}")

        edicoes_resultado = res.get("edicoes_resultado", [])
        total_ok  = sum(1 for r in edicoes_resultado if r.get("sucesso"))
        total_nok = len(edicoes_resultado) - total_ok

        print(f"  Edições OK     : {total_ok}/{len(edicoes_final)}")
        print(f"  Edições FALHAS : {total_nok}/{len(edicoes_final)}")
        print()

        for i, ed_res in enumerate(edicoes_resultado, 1):
            status = "✅ SIM" if ed_res.get("sucesso") else "❌ NÃO"
            alvo = ed_res.get("texto_linha") or f"linha {ed_res.get('linha_editar', i)}"
            print(f"  [{i}] {alvo!r:20s} → {ed_res.get('valor'):>12s}  |  OK: {status}")

        if res.get("linhas_extraidas"):
            print(f"\n  Linhas lidas do SAP: {len(res['linhas_extraidas'])}")

        # ── Verificação de total ───────────────────────────────────────────────
        verif = res.get("verificacao_total")
        if verif:
            print()
            print("  🔢 Verificação de total (SAP vs soma dos CT-es):")
            if verif["ok"] is True:
                print(f"     ✅ TOTAL CORRETO → SAP: {verif['sap']}  |  Esperado: {verif['esperado']}")
            elif verif["ok"] is False:
                print(f"     ❌ DIVERGÊNCIA   → SAP: {verif['sap']}  |  Esperado: {verif['esperado']}")
                print(f"        Diferença: {verif['diferenca']:.2f}")
            else:
                print(f"     ⚠️  Não foi possível ler o total do SAP.")
                print(f"        Esperado: {verif['esperado']}")

        if not SALVAR:
            print()
            print("  ⚠️  MODO TESTE – As alterações NÃO foram salvas no SAP.")
            print("      Altere SALVAR = True para gravar definitivamente.")

    except Exception as exc:
        separador("❌  ERRO NA EXECUÇÃO")
        print(f"  {type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc()

    separador("🏁  FIM")


if __name__ == "__main__":
    main()
