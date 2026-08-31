"""
debug_rc_cte.py
===============
Script de depuração/teste para criar RC de CTE no SAP GUI (ME51N).

Como usar:
  1. Abra o SAP Logon e faça login em uma sessão.
  2. Ajuste os dados na seção "⚙️ CONFIGURAÇÕES DE TESTE" abaixo.
  3. Execute:
        python debug_rc_cte.py

Modos disponíveis:
  SALVAR = False  → apenas preenche os campos na tela, NÃO cria a RC (modo seguro para validar)
  SALVAR = True   → executa o save e gera o número da RC no SAP

Passos que podem ser executados individualmente (comentar/descomentar):
  - PASSO_1_CABECALHO    : abre ME51N e preenche o cabeçalho
  - PASSO_2_LINHA_0      : preenche a primeira linha completa
  - PASSO_3_COPIAR       : copia a linha 0 N-1 vezes
  - PASSO_4_PRECOS       : atualiza o preço de cada linha
  - PASSO_5_WEPOS        : desmarca o flag de entrada de mercadoria
  - PASSO_6_ANEXO        : adiciona o arquivo de anexo
  - PASSO_7_SALVAR       : salva e captura o número da RC
"""

import os
import sys
import time

# ── garante que a raiz do projeto esteja no path ──────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.utils.sap_utils import conectar_sap
from src.expedicao.sap_rc_cte import (
    criar_rc_cte,          # função completa (todos os passos)
    _abrir_me51n,
    _preencher_cabecalho,
    _preencher_linha_0,
    _copiar_linhas,
    _atualizar_precos,
    _desmarcar_wepos_todos,
    _adicionar_anexo,
    _salvar_rc,
)


# =============================================================================
# ⚙️  CONFIGURAÇÕES DE TESTE  –  EDITE AQUI
# =============================================================================

# Lista de CTEs com número e valor de frete (formato SAP: vírgula como decimal)
CTES = [
    {"numero": "562847", "valor": "2.664,78"},
    {"numero": "573186", "valor": "5.782,15"},
    {"numero": "573187", "valor": "5.782,15"},
    {"numero": "573188", "valor": "5.782,15"},
    {"numero": "573190", "valor": "5.782,15"},
    {"numero": "573191", "valor": "5.782,15"},
    {"numero": "573192", "valor": "5.782,15"},
    {"numero": "573194", "valor": "5.782,15"},
    {"numero": "573195", "valor": "5.782,15"},
]

CENTRO_CUSTO    = "AQ203"
FORNECEDOR      = "9190617"
MATERIAL        = "CTE.16.04"
PLANTA          = "p716"
TIPO_IMPUTACAO  = "K"          # K = Centro de Custo | F = Ordem de Investimento
TIPO_DOC        = "NB"
DATA_HOJE       = None         # None = usa a data de hoje automaticamente (DDMMYYYY)

CAMINHO_ANEXO   = r"C:\Users\ismael.nascimento\Downloads\ "[:-1]  # barra simples no final
ARQUIVO_ANEXO   = "Tabela_Cabotagem_2026.xlsx"

# True  → salva a RC no SAP e retorna o número
# False → preenche os campos mas NÃO salva (modo seguro para testes)
SALVAR = False

# Modo de execução:
#   "COMPLETO"  → executa todos os passos de uma vez via criar_rc_cte()
#   "PASSO_A_PASSO" → executa cada passo individualmente (útil para depurar onde falha)
MODO = "COMPLETO"

# =============================================================================


def separador(titulo: str = "") -> None:
    linha = "─" * 60
    if titulo:
        print(f"\n{linha}")
        print(f"  {titulo}")
        print(linha)
    else:
        print(linha)


def main():
    separador("🛠️  DEBUG – CRIAÇÃO DE RC PARA CTE (ME51N)")
    print(f"  Modo         : {MODO}")
    print(f"  Salvar RC    : {'✅ SIM' if SALVAR else '❌ NÃO (modo teste)'}")
    print(f"  Total CTEs   : {len(CTES)}")
    print(f"  Centro Custo : {CENTRO_CUSTO}")
    print(f"  Fornecedor   : {FORNECEDOR}")
    print(f"  Material     : {MATERIAL}")
    print(f"  Planta       : {PLANTA}")
    print(f"  Anexo        : {ARQUIVO_ANEXO}")
    separador()

    # ── Conecta ao SAP GUI ─────────────────────────────────────────────────────
    print("\n🔌 Conectando ao SAP GUI...")
    session = conectar_sap()
    if not session:
        print("❌ Não foi possível conectar ao SAP GUI.")
        print("   Verifique se o SAP Logon está aberto e com uma sessão ativa.")
        sys.exit(1)
    print("✅ Conectado ao SAP GUI!\n")

    # ── Execução ───────────────────────────────────────────────────────────────
    if MODO == "COMPLETO":
        _executar_completo(session)
    elif MODO == "PASSO_A_PASSO":
        _executar_passo_a_passo(session)
    else:
        print(f"❌ Modo desconhecido: '{MODO}'. Use 'COMPLETO' ou 'PASSO_A_PASSO'.")
        sys.exit(1)


def _executar_completo(session) -> None:
    """Executa todos os passos em sequência via função principal."""
    separador("▶  EXECUÇÃO COMPLETA")
    try:
        numero_rc = criar_rc_cte(
            session=session,
            ctes=CTES,
            centro_custo=CENTRO_CUSTO,
            fornecedor=FORNECEDOR,
            material=MATERIAL,
            planta=PLANTA,
            data_hoje=DATA_HOJE,
            caminho_anexo=CAMINHO_ANEXO,
            arquivo_anexo=ARQUIVO_ANEXO,
            tipo_imputacao=TIPO_IMPUTACAO,
            tipo_doc=TIPO_DOC,
            salvar=SALVAR,
        )
        separador("✅  RESULTADO FINAL")
        if SALVAR:
            print(f"  RC gerada: {numero_rc}")
        else:
            print("  Execução em MODO TESTE – RC não foi salva.")
            print("  Defina SALVAR = True para gravar no SAP.")
    except Exception as e:
        separador("❌  ERRO NA EXECUÇÃO")
        print(f"  {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


def _executar_passo_a_passo(session) -> None:
    """
    Executa cada passo individualmente com pausa entre eles.
    Comente os passos que não deseja executar para isolar o problema.
    """
    import datetime
    data_hoje = DATA_HOJE or datetime.date.today().strftime("%d%m%Y")

    # ── PASSO 1: Abrir ME51N e preencher cabeçalho ────────────────────────────
    separador("PASSO 1 – Abrir ME51N e Cabeçalho")
    try:
        _abrir_me51n(session, TIPO_DOC)
        _preencher_cabecalho(session, CTES)
        print("  ✅ Passo 1 OK")
    except Exception as e:
        print(f"  ❌ Passo 1 FALHOU: {e}")
        _aguardar_confirmacao("Corrija o problema e pressione Enter para continuar...")

    # ── PASSO 2: Preencher linha 0 (completa) ─────────────────────────────────
    separador("PASSO 2 – Primeira Linha (item 0)")
    try:
        _preencher_linha_0(
            session,
            cte=CTES[0],
            planta=PLANTA,
            material=MATERIAL,
            tipo_imputacao=TIPO_IMPUTACAO,
            data_hoje=data_hoje,
            centro_custo=CENTRO_CUSTO,
            fornecedor=FORNECEDOR,
        )
        print("  ✅ Passo 2 OK")
    except Exception as e:
        print(f"  ❌ Passo 2 FALHOU: {e}")
        _aguardar_confirmacao()

    # ── PASSO 3: Copiar linha 0 (N-1 cópias) ─────────────────────────────────
    separador(f"PASSO 3 – Copiar linha 0 ({len(CTES) - 1} cópia(s))")
    try:
        if len(CTES) > 1:
            _copiar_linhas(session, len(CTES))
            print("  ✅ Passo 3 OK")
        else:
            print("  ℹ️  Apenas 1 CTE – sem necessidade de cópia.")
    except Exception as e:
        print(f"  ❌ Passo 3 FALHOU: {e}")
        _aguardar_confirmacao()

    # ── PASSO 4: Atualizar preços linha a linha ───────────────────────────────
    separador("PASSO 4 – Atualizar Preços (PREIS)")
    try:
        _atualizar_precos(session, CTES)
        print("  ✅ Passo 4 OK")
    except Exception as e:
        print(f"  ❌ Passo 4 FALHOU: {e}")
        _aguardar_confirmacao()

    # ── PASSO 5: Desmarcar WEPOS em todas as linhas ───────────────────────────
    separador(f"PASSO 5 – Desmarcar WEPOS ({len(CTES)} linha(s))")
    try:
        if len(CTES) > 1:
            _desmarcar_wepos_todos(session, len(CTES))
        print("  ✅ Passo 5 OK")
    except Exception as e:
        print(f"  ❌ Passo 5 FALHOU: {e}")
        _aguardar_confirmacao()

    # ── PASSO 6: Adicionar anexo ──────────────────────────────────────────────
    separador("PASSO 6 – Adicionar Anexo")
    try:
        if CAMINHO_ANEXO and ARQUIVO_ANEXO:
            _adicionar_anexo(session, CAMINHO_ANEXO, ARQUIVO_ANEXO)
            print("  ✅ Passo 6 OK")
        else:
            print("  ℹ️  CAMINHO_ANEXO ou ARQUIVO_ANEXO vazios – passo ignorado.")
    except Exception as e:
        print(f"  ❌ Passo 6 FALHOU: {e}")
        _aguardar_confirmacao()

    # ── PASSO 7: Salvar ───────────────────────────────────────────────────────
    separador("PASSO 7 – Salvar RC")
    try:
        if SALVAR:
            numero_rc = _salvar_rc(session)
            print(f"  ✅ RC gerada: {numero_rc}")
        else:
            print("  ⚠️  SALVAR = False – RC não salva (modo teste).")
            print("      Altere SALVAR = True para gravar no SAP.")
    except Exception as e:
        print(f"  ❌ Passo 7 FALHOU: {e}")

    separador("🏁  FIM DA EXECUÇÃO PASSO A PASSO")


def _aguardar_confirmacao(msg: str = "Pressione Enter para continuar para o próximo passo...") -> None:
    """Pausa a execução aguardando confirmação do usuário."""
    input(f"\n  ⏸️  {msg}\n")


if __name__ == "__main__":
    main()
