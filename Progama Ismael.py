# %%
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Automação RPA SAP GUI – Atualização de Remessas

1) Atualização básica: peso líquido e paletes (transação VL02N).
2) Picking: lote, peso, peso BR e picking.
3) Transportadora: parceiro de entrega (aba de parceiros).
Opções para rodar cada bloco isolado ou todos em sequência.
"""

import os
import sys
import time
import pandas as pd
import win32com.client as win32

# -----------------------------------------------------------------------------
# CONFIGURAÇÃO GERAL
# -----------------------------------------------------------------------------
EXCEL_FILE   = r"C:\Users\ismael.nascimento\OneDrive - VALGROUP\Scripts\python\picking.xlsx"    # ajuste
SHEET_NAME   = "Picking remessa"
SAP_TRX_BASIC   = "/nvl02n"
SAP_TRX_PICKING = "/nvl02n"
SAP_TRX_TRANS   = "/nvl02n"

# Colunas no Excel
COL_REMESSA       = "Remessa"
COL_PESO_LIQ      = "Peso Liq"
COL_PALETS        = "Qnt pllt"
COL_REM_PICK      = "Remessa PICKING"
COL_LOTE          = "Lotes"
COL_PESO          = "Peso"
COL_PESO_BR       = "Peso BR"
COL_TRANSPORT     = "Transportadora"

# -----------------------------------------------------------------------------
# UTILITÁRIOS
# -----------------------------------------------------------------------------
def conectar_sap():
    """Retorna session SAP GUI já aberta ou None."""
    try:
        SapGuiAuto  = win32.GetObject("SAPGUI")
        application = SapGuiAuto.GetScriptingEngine
        connection  = application.Children(0)
        session     = connection.Children(0)
        print("✅ Conectado ao SAP GUI.")
        return session
    except Exception as e:
        print(f"❌ Falha ao conectar ao SAP GUI: {e}")
        return None

def formatar_valor(v):
    """Converte ponto para vírgula e trata nulos."""
    if pd.isna(v) or str(v).strip()=="":
        return ""
    s = str(v).strip()
    if "." in s and "," not in s:
        s = s.replace(".", ",")
    return s

def read_excel():
    """Lê planilha única com todas as colunas."""
    path = os.path.abspath(EXCEL_FILE)
    print(f"\n📂 Lendo Excel: {path} (sheet: {SHEET_NAME})")
    try:
        df = pd.read_excel(path, sheet_name=SHEET_NAME, dtype=str)
        print(f"✅ Linhas carregadas: {len(df)}")
        return df.fillna("")  # facilita testes de vazio
    except Exception as e:
        print(f"❌ Erro ao ler Excel: {e}")
        return None


def esperar_id(session, elementos_id, timeout=10):
    """Espera até encontrar um dos IDs informados."""
    end = time.time() + timeout
    while time.time() < end:
        for eid in elementos_id:
            try:
                if session.findById(eid, False):
                    return True
            except: pass
        time.sleep(0.2)
    return False

def fechar_popups(session, keywords):
    """Fecha janelas popup que contenham alguma keyword no título."""
    try:
        while any(kw.lower() in session.ActiveWindow.Text.lower() for kw in keywords):
            session.findById("wnd[1]/tbar[0]/btn[0]").press()
            time.sleep(0.3)
    except:
        pass

# -----------------------------------------------------------------------------
# 1) ATUALIZAÇÃO BÁSICA (Peso Liq + Paletes)
# -----------------------------------------------------------------------------
def processar_basico(session, df):
    print("\n=== 1) Atualização Básica (VL02N) ===")
    for i, row in df.iterrows():
        rem = row[COL_REMESSA].strip()
        if not rem:
            continue
        peso_liq = formatar_valor(row[COL_PESO_LIQ])
        paletes  = formatar_valor(row[COL_PALETS])
        try:
            print(f"\n🚚 Remessa {rem}")
            # transação e digitar remessa
            session.findById("wnd[0]/tbar[0]/okcd").text = SAP_TRX_BASIC
            session.findById("wnd[0]").sendVKey(0)
            if not esperar_id(session, ["wnd[0]/usr/ctxtLIKP-VBELN"]):
                print("⚠️ Tela VL02N não carregou.")
                continue
            session.findById("wnd[0]/usr/ctxtLIKP-VBELN").text = rem
            session.findById("wnd[0]").sendVKey(0)
            time.sleep(0.5)
            fechar_popups(session, ["Informação"])
            session.findById("wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\01").select()
            # peso líquido
            if peso_liq:
                session.findById(
                    "wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\01"
                    "/ssubSUBSCREEN_BODY:SAPMV50A:1102/"
                    "tblSAPMV50ATC_LIPS_OVER/ctxtLIPS-VRKME[3,0]"
                ).text = "KG"
                session.findById(
                    "wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\01"
                    "/ssubSUBSCREEN_BODY:SAPMV50A:1102/"
                    "tblSAPMV50ATC_LIPS_OVER/txtLIPSD-G_LFIMG[2,0]"
                ).text = peso_liq
                session.findById("wnd[0]").sendVKey(0)
                fechar_popups(session, ["Informação"])
            # paletes
            if paletes:
                session.findById(
                    "wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\01"
                    "/ssubSUBSCREEN_BODY:SAPMV50A:1102/"
                    "txtLIKP-ANZPK"
                ).text = paletes
                session.findById("wnd[0]").sendVKey(0)
            # salvar
            session.findById("wnd[0]/tbar[0]/btn[11]").press()
            fechar_popups(session, ["SAP Credit Management"])
            print(f"✅ {rem} salvo.")
        except Exception as e:
            print(f"❌ Erro básico na remessa {rem}: {e}")

# -----------------------------------------------------------------------------
# 2) PICKING (Lote, Peso, Peso BR e Picking)
# -----------------------------------------------------------------------------
def preencher_lote_e_peso(session, grupo):
    """Preenche lote e peso no item, navegando por todas as linhas via scroll."""
    print("📋 Preenchendo Lote e Peso...")
    try:
        # Inicializa posição do scroll na primeira linha
        scroll = 1

        # Itera cada linha do grupo de itens da remessa
        for _, row in grupo.iterrows():
            lote = formatar_valor(row[COL_LOTE])
            peso = formatar_valor(row[COL_PESO])

            print(f"    ➡ Lote: {lote or 'vazio'} | Peso: {peso or 'vazio'}")

            # Preenche campo Lote
            if lote:
                session.findById(
                    "wnd[0]/usr/tabsTAXI_TABSTRIP_ITEM/tabpT\\03/"
                    "ssubSUBSCREEN_BODY:SAPMV50A:3112/"
                    "tblSAPMV50ATC_LIPS_CHND/ctxtLIPS-CHARG[1,0]"
                ).text = lote

            # Preenche campo Peso
            if peso:
                session.findById(
                    "wnd[0]/usr/tabsTAXI_TABSTRIP_ITEM/tabpT\\03/"
                    "ssubSUBSCREEN_BODY:SAPMV50A:3112/"
                    "tblSAPMV50ATC_LIPS_CHND/txtLIPS-LFIMG[4,0]"
                ).text = peso

            # Confirma linha e avança
            session.findById("wnd[0]").sendVKey(0)
            time.sleep(0.3)

            # Ajusta scroll para a próxima linha
            scroll += 1
            session.findById(
                "wnd[0]/usr/tabsTAXI_TABSTRIP_ITEM/tabpT\\03/"
                "ssubSUBSCREEN_BODY:SAPMV50A:3112/"
                "tblSAPMV50ATC_LIPS_CHND"
            ).verticalScrollbar.Position = scroll
            time.sleep(0.2)

        print("✅ Lote e Peso preenchidos com sucesso.")
        return True

    except Exception as e:
        print(f"  ❌ ERRO na função 'preencher_lote_e_peso': {e}")
        return False
def preencher_peso_br_picking(session, grupo):
    """
    Preenche peso BR e picking no overview:
    - Volta à tela anterior
    - Abre a edição em massa (multi‐edição)
    - Rola linha a linha, copiando qty→picking e preenchendo peso BR
    - Confirma e salva
    """
    print("📦 Preenchendo Peso BR e Picking...")
    try:
        # 1) Volta da tela de ITEM para OVERVIEW
        session.findById("wnd[0]/tbar[0]/btn[3]").press()
        time.sleep(0.3)

        # 2) Seleciona a aba Overview (Picking)
        session.findById(
            "wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\02"
        ).select()
        time.sleep(0.5)

        # 3) Clica em “Multi‐edição” para abrir todos os campos de peso
        multi_id = (
            "wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\02/"
            "ssubSUBSCREEN_BODY:SAPMV50A:1104/"
            "tblSAPMV50ATC_LIPS_PICK/btnRV50A-CHMULT[10,0]"
        )
        session.findById(multi_id).press()
        time.sleep(0.5)

        # 4) Prepara para scroll na tabela de picking
        table_id = (
            "wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\02/"
            "ssubSUBSCREEN_BODY:SAPMV50A:1104/"
            "tblSAPMV50ATC_LIPS_PICK"
        )
        scroll = 1
        session.findById(table_id).verticalScrollbar.Position = scroll
        time.sleep(0.2)

        # 5) Itera sobre cada linha do grupo
        for _, row in grupo.iterrows():
            peso_br = formatar_valor(row[COL_PESO_BR])
            # copia qty → picking
            qty_id  = table_id + "/txtLIPSD-G_LFIMG[5,0]"
            pick_id = table_id + "/txtLIPSD-PIKMG[7,0]"
            qtd      = session.findById(qty_id).Text
            session.findById(pick_id).Text = qtd

            # preenche Peso BR
            if peso_br:
                br_id = table_id + "/txtLIPS-BRGEW[19,0]"
                session.findById(br_id).Text = peso_br

            # desce 1 linha no scroll
            scroll += 1
            session.findById(table_id).verticalScrollbar.Position = scroll
            time.sleep(0.2)

        # 6) Confirma edição em massa e reseta scroll
        session.findById("wnd[0]").sendVKey(0)
        time.sleep(0.3)
        session.findById(table_id).verticalScrollbar.Position = 0
        time.sleep(0.2)

        # 7) Salva a transação
        session.findById("wnd[0]/tbar[0]/btn[11]").press()
        print("✅ Peso BR e Picking preenchidos.")
        return True

    except Exception as e:
        print(f"❌ ERRO em preencher_peso_br_picking: {e}")
        return False

def processar_picking(session, df):
    print("\n=== 2) Picking (VL02N + lotes/pesos) ===")
    grupos = df[df[COL_REM_PICK].str.strip()!=""].groupby(COL_REM_PICK)
    for rem, grupo in grupos:
        try:
            print(f"\n🚚 Remessa PICKING {rem}")
            # transação
            session.findById("wnd[0]/tbar[0]/okcd").text = SAP_TRX_PICKING
            session.findById("wnd[0]").sendVKey(0)
            session.findById("wnd[0]/usr/ctxtLIKP-VBELN").text = rem
            session.findById("wnd[0]").sendVKey(0)
            time.sleep(0.5)
            fechar_popups(session, ["Informação"])
            # navegar para sub-tela de picking
            session.findById("wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\02").select()
            # abrir edição de lote/peso
            session.findById(
                "wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\02/"
                "ssubSUBSCREEN_BODY:SAPMV50A:1104/"
                "tblSAPMV50ATC_LIPS_PICK").getAbsoluteRow(0).Selected = True
            session.findById(
                "wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\02/"
                "ssubSUBSCREEN_BODY:SAPMV50A:1104/"
                "subSUBSCREEN_ICONBAR:SAPMV50A:1708/btnBT_CHSP_T"
            ).press()
            time.sleep(0.5)
            # lote & peso
            if not preencher_lote_e_peso(session, grupo):
                print("⚠️ Falha no lote/peso – pulando.")
                continue
            # peso BR & picking
            if not preencher_peso_br_picking(session, grupo):
                print("⚠️ Falha no peso BR – pulando.")
                continue
            print(f"✅ {rem} concluído.")
        except Exception as e:
            print(f"❌ Erro em picking {rem}: {e}")

# -----------------------------------------------------------------------------
# 3) TRANSPORTADORA (Parceiro de entrega)
# -----------------------------------------------------------------------------
def processar_transport(session, df):
    print("\n=== 3) Parceiro (Transportadora) ===")
    grupos = df[df[COL_TRANSPORT].str.strip()!=""].groupby(COL_REMESSA)
    for rem, grupo in grupos:
        transp = grupo[COL_TRANSPORT].iloc[0].strip()
        if not transp:
            continue
        try:
            print(f"\n🚚 Remessa {rem} – transp: {transp}")
            # transação
            session.findById("wnd[0]/tbar[0]/okcd").text = SAP_TRX_TRANS
            session.findById("wnd[0]").sendVKey(0)
            session.findById("wnd[0]/usr/ctxtLIKP-VBELN").text = rem
            session.findById("wnd[0]").sendVKey(0)
            time.sleep(0.5)
            # limites de erro
            sb = session.findById("wnd[0]/sbar").text.lower()
            if "não existe" in sb:
                print(f"⚠️ {rem} não existe no SAP.")
                continue
            # navegar à aba de parceiros
            session.findById("wnd[0]/tbar[1]/btn[8]").press()
            session.findById("wnd[0]/usr/tabsTAXI_TABSTRIP_HEAD/tabpT\\08").select()
            # tipo SP + código
            session.findById(
                "wnd[0]/usr/tabsTAXI_TABSTRIP_HEAD/tabpT\\08/"
                "ssubSUBSCREEN_BODY:SAPMV50A:2114/"
                "subSUBSCREEN_PARTNER_OVERVIEW:SAPLV09C:1000/"
                "tblSAPLV09CGV_TC_PARTNER_OVERVIEW/cmbGVS_TC_DATA-REC-PARVW[0,5]"
            ).key = "SP"
            if transp == "Em negociação - D+2>" or transp =="Em negociação":
                transp = input("Digite a transportadora a qual deseja faturar: ")
            session.findById(
                "wnd[0]/usr/tabsTAXI_TABSTRIP_HEAD/tabpT\\08/"
                "ssubSUBSCREEN_BODY:SAPMV50A:2114/"
                "subSUBSCREEN_PARTNER_OVERVIEW:SAPLV09C:1000/"
                "tblSAPLV09CGV_TC_PARTNER_OVERVIEW/ctxtGVS_TC_DATA-REC-PARTNER_EXT[1,5]"
            ).text = transp
            session.findById("wnd[0]").sendVKey(0)
            # salvar (SM)
            session.findById("wnd[0]/tbar[1]/btn[20]").press()
            print(f"✅ {rem} – parceiro atualizado.")
        except Exception as e:
            print(f"❌ Erro transportadora {rem}: {e}")

# -----------------------------------------------------------------------------
# MENU E FLUXO PRINCIPAL
# -----------------------------------------------------------------------------
def main():
    session = conectar_sap()
    if not session:
        sys.exit(1)

    df = read_excel()
    if df is None:
        sys.exit(1)

    while True:
        print("""
RPA Remessa / v.1.0.0 
              Desenvolvido por Ismael Nascimento com ajuda da IA
Escolha opção:
1) Atualização básica (Peso Liq + Paletes)
2) Picking (Lote, Peso, Peso BR)
3) Transportadora (Parceiro)
4) Executar tudo em sequência
0) Sair
""")
        opt = input("Opção: ").strip()
        if opt == "1":
            processar_basico(session, df)
        elif opt == "2":
            processar_picking(session, df)
        elif opt == "3":
            processar_transport(session, df)
        elif opt == "4":
            processar_basico(session, df)
            processar_picking(session, df)
            processar_transport(session, df)
        elif opt == "0":
            print("Saindo...")
            break
        else:
            print("Opção inválida.")
        # pequena pausa antes do próximo menu
        time.sleep(1)

    input("\nPressione Enter para encerrar...")

if __name__ == "__main__":
    main()



