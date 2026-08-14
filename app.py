import os
import sys
import threading
from datetime import datetime
from flask import Flask, render_template, jsonify, request, send_file
import io

# --- IMPORTAÇÕES MODULARES ---
from src.utils.common import log_sys
from src.utils.windows_utils import abrir_seletor_ficheiro_excel, abrir_seletor_pasta
from src.expedicao.picking import processarPicking
from src.expedicao.selecao_uc import processarRemessaComUc
from src.expedicao.sm_remessa import smRemessa
from src.expedicao.fip_etiquetas import salvarFIP
from src.expedicao.sap_packlist import baixar_packlist_sap
from src.estoque.packlist import analisar_planilha_packlist
from src.estoque.processo_completo import processo_estoque
from src.estoque.processo_sap import processo_estoque_sem_planilha
import src.utils.db as db
from dotenv import load_dotenv
from src.utils.sharepoint import SharePointClient, salvar_configuracoes_env, ENV_PATH
from Entreposto import executar_automacao_entreposto
from src.expedicao import EntrepostoProcessador
from src.utils.sap_utils import conectar_sap
from src.expedicao.cabotagem_processador import obter_dados_cabotagem, rodar_criar_of_cabotagem, cabotagem_estado



# --- MECANISMO AUTOMÁTICO DE ATUALIZAÇÃO (SEM DEPENDÊNCIAS) ---
try:
    import updater
    updater.check_for_updates()
except Exception as e:
    print(f"Erro ao verificar atualizações: {e}")

# --- CONFIGURAÇÃO FLASK PARA PATH AMBIENTE EM EXECUTÁVEL ---
if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

template_folder = os.path.join(base_dir, 'templates')
static_folder = os.path.join(base_dir, 'static')
app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)

# --- ROTAS DA API FLASK PARA INTEGRAÇÃO FRONTEND ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/expedicao')
def expedicao():
    return render_template('expedicao.html')

@app.route('/estoque')
def estoque():
    return render_template('estoque.html')

@app.route('/estoque_sem_planilha')
def estoque_sem_planilha():
    return render_template('estoque_sem_planilha.html')

@app.route('/entreposto')
def entreposto():
    return render_template('entreposto.html')

@app.route('/entreposto_processamento')
def entreposto_processamento():
    return render_template('entreposto_processamento.html')

@app.route('/cabotagem')
def cabotagem():
    return render_template('cabotagem.html')

@app.route('/cabotagem_processamento')
def cabotagem_processamento():
    return render_template('cabotagem_processamento.html')

@app.route('/sto')
def sto():
    return render_template('sto.html')



@app.route('/api/inicializar', methods=['GET'])
def inicializar():
    usuario_completo = os.getlogin()
    primeiro_nome = usuario_completo.split('.')[0].capitalize()
    hora_atual = datetime.now().hour
    saudacao = "Bom dia" if 5 <= hora_atual < 12 else "Boa tarde" if 12 <= hora_atual < 18 else "Boa noite"
    return jsonify({"nome": primeiro_nome, "saudacao": saudacao})

@app.route('/api/selecionar_arquivo', methods=['GET'])
def selecionar_arquivo():
    """
    Abre a caixa de diálogo nativa do Windows para selecionar um ficheiro Excel.
    Retorna o caminho do ficheiro selecionado.
    """
    caminho = abrir_seletor_ficheiro_excel()
    if caminho:
        nome_ficheiro = os.path.basename(caminho)
        log_sys.write(f"📂 Ficheiro Excel selecionado: {nome_ficheiro}")
    else:
        log_sys.write("⚠️ Nenhum ficheiro Excel foi selecionado.")
    
    return jsonify({"caminho": caminho})

@app.route('/api/selecionar_pasta', methods=['GET'])
def selecionar_pasta():
    """
    Abre a caixa de diálogo nativa do Windows para selecionar uma pasta de destino.
    Retorna o caminho da pasta selecionada.
    """
    caminho = abrir_seletor_pasta()
    if caminho:
        nome_pasta = os.path.basename(caminho)
        log_sys.write(f"📁 Pasta de destino selecionada: {nome_pasta}")
    else:
        log_sys.write("⚠️ Nenhuma pasta foi selecionada.")
    
    return jsonify({"caminho": caminho})

@app.route('/api/analisar_packlist', methods=['POST'])
def analisar_packlist():
    dados = request.json
    caminho = dados.get('caminho', '')
    if not caminho or not os.path.exists(caminho):
        return jsonify({"status": "error", "message": "Arquivo inválido ou não selecionado."}), 400
    
    resultado = analisar_planilha_packlist(caminho)
    return jsonify(resultado)

@app.route('/api/estoque/estado_pendente', methods=['GET'])
def estado_pendente():
    lote = db.buscar_lote_pendente()
    if lote:
        return jsonify({"pendente": True, "lote": lote})
    return jsonify({"pendente": False})

@app.route('/api/estoque/status', methods=['GET'])
def estoque_status():
    """
    Retorna o status detalhado dos itens do lote atual em andamento
    ou do último lote executado caso não haja um em andamento.
    """
    lote = db.buscar_lote_pendente()
    if not lote:
        lote = db.buscar_ultimo_lote()
    
    if lote:
        return jsonify({"status": "success", "lote": lote})
    return jsonify({"status": "empty", "message": "Nenhum lote processado até o momento."})

@app.route('/api/estoque/cancelar_pendente', methods=['POST'])
def cancelar_pendente():
    db.cancelar_lote_pendente()
    return jsonify({"status": "ok"})

@app.route('/api/estoque/executar', methods=['POST'])
def executar_estoque():
    dados = request.json
    caminho = dados.get('caminho', '')
    ponto_partida = int(dados.get('ponto_partida', 1))
    op_global = dados.get('op_global', None)
    inbound_global = dados.get('inbound_global', None)
    lote_id = dados.get('lote_id', None)

    ui_info = dados.get('ui_info', None)
    ui_tpMigo = dados.get('ui_tpMigo', None)
    ui_opt = dados.get('ui_opt', None)

    if log_sys.is_running:
        return jsonify({"status": "error", "message": "Já existe uma automação em andamento."}), 400

    def worker():
        log_sys.is_running = True
        try:
            if ponto_partida <= 4:
                processo_estoque(caminho, ponto_partida, op_global, inbound_global, lote_id)
            elif ponto_partida == 5:
                from src.estoque.msc import executar_msc1n
                executar_msc1n(caminho, ui_info=ui_info)
            elif ponto_partida == 6:
                from src.estoque.msc import executar_msc2n
                executar_msc2n(caminho)
            elif ponto_partida == 7:
                from src.estoque.msc import ajustar_fator
                ajustar_fator(caminho)
            elif ponto_partida == 8:
                from src.estoque.migo import executar_transferencia_migo
                executar_transferencia_migo(caminho, auto=False, ui_tpMigo=ui_tpMigo)
            elif ponto_partida == 9:
                from src.estoque.migo import executar_migo_zp1
                executar_migo_zp1(caminho, auto=False, op=op_global, ui_opt=ui_opt)
            elif ponto_partida == 10:
                from src.estoque.prdi import executar_prdi
                executar_prdi(caminho, auto=False, inbound=inbound_global)
            elif ponto_partida == 11:
                from src.estoque.brid import brid
                brid(caminho)
            elif ponto_partida == 12:
                from src.estoque.mon import localizarMon
                localizarMon(caminho)
        except Exception as e:
            log_sys.write(f"❌ Falha fatal na thread do processo de estoque: {e}")
        finally:
            log_sys.is_running = False

    t = threading.Thread(target=worker)
    t.daemon = True
    t.start()
    return jsonify({"status": "started"})

@app.route('/api/estoque_sem_planilha/executar', methods=['POST'])
def executar_estoque_sem_planilha():
    dados = request.json
    vl32_list = dados.get('vl32_list', [])
    ponto_partida = int(dados.get('ponto_partida', 1))
    op_global = dados.get('op_global', None)
    migo_global = dados.get('migo_global', None)
    lote_id = dados.get('lote_id', None)

    if log_sys.is_running:
        return jsonify({"status": "error", "message": "Já existe uma automação em andamento."}), 400

    def worker():
        log_sys.is_running = True
        try:
            processo_estoque_sem_planilha(vl32_list, ponto_partida, op_global, migo_global, lote_id)
        except Exception as e:
            log_sys.write(f"❌ Falha fatal na thread do processo sem planilha: {e}")
        finally:
            log_sys.is_running = False

    t = threading.Thread(target=worker)
    t.daemon = True
    t.start()
    return jsonify({"status": "started"})

# Estado global para processamento da Expedição
expedicao_processamento_estado = {
    "caminho": "",
    "dados_colados": "",
    "remessas": [],
    "status_etapas": {}  # {remessa: {"selecao_uc": "pending", "picking": "pending", "sm": "pending", "erro_detalhe": ""}}
}

@app.route('/api/expedicao/carregar_dados', methods=['POST'])
def carregar_dados_expedicao():
    global expedicao_processamento_estado
    dados = request.json
    caminho = dados.get('caminho', '')
    dados_colados = dados.get('dados_colados', '')
    
    from src.utils.excel_utils import lerDados, colunaRemessa
    try:
        df = lerDados(caminho, dados_colados)
        if df is None or df.empty:
            return jsonify({"status": "error", "message": "Nenhum dado válido encontrado na planilha/texto colado."}), 400
        
        remessasUnicas = sorted(list(df[colunaRemessa].unique()))
        
        status_etapas = {}
        for remessa in remessasUnicas:
            status_etapas[remessa] = {
                "selecao_uc": "pending",
                "picking": "pending",
                "sm": "pending",
                "erro_detalhe": ""
            }
            
        expedicao_processamento_estado = {
            "caminho": caminho,
            "dados_colados": dados_colados,
            "remessas": remessasUnicas,
            "status_etapas": status_etapas
        }
        return jsonify({"status": "success", "remessas": remessasUnicas})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/expedicao/dados_processamento', methods=['GET'])
def dados_processamento_expedicao():
    global expedicao_processamento_estado
    return jsonify(expedicao_processamento_estado)

@app.route('/api/executar', methods=['POST'])
def executar():
    dados = request.json
    opcao = int(dados.get('opcao'))
    caminho = dados.get('caminho', '')
    dados_colados = dados.get('dados_colados', '')
    remessas = dados.get('remessas', '')
    caminho_pasta = dados.get('caminho_pasta', '')

    if log_sys.is_running:
        return jsonify({"status": "error", "message": "Já existe uma automação em andamento."}), 400

    def worker():
        log_sys.is_running = True
        try:
            status = expedicao_processamento_estado.get("status_etapas", {})
            if opcao == 1:
                processarRemessaComUc(caminho, dados_colados, status)
            elif opcao == 2:
                processarPicking(caminho, dados_colados, status)
            elif opcao == 3:
                smRemessa(caminho, dados_colados, status)
            elif opcao == 4:
                salvarFIP(remessas, caminho_pasta if caminho_pasta else None)
            elif opcao == 100:
                processarRemessaComUc(caminho, dados_colados, status)
                processarPicking(caminho, dados_colados, status)
                smRemessa(caminho, dados_colados, status)
        except Exception as e:
            log_sys.write(f"❌ Falha fatal na thread do processo: {e}")
        finally:
            log_sys.is_running = False

    t = threading.Thread(target=worker)
    t.daemon = True
    t.start()
    return jsonify({"status": "started"})

@app.route('/api/logs', methods=['GET'])
def buscar_logs():
    return jsonify({
        "novos_logs": log_sys.fetch_new(),
        "rodando": log_sys.is_running
    })

@app.route('/api/sharepoint/config', methods=['GET', 'POST'])
def sharepoint_config():
    if request.method == 'POST':
        dados = request.json
        salvar_configuracoes_env({
            "SHAREPOINT_TENANT_ID": dados.get("tenant_id"),
            "SHAREPOINT_CLIENT_ID": dados.get("client_id"),
            "SHAREPOINT_CLIENT_SECRET": dados.get("client_secret"),
            "SHAREPOINT_DRIVE_ID": dados.get("drive_id"),
            "PLANILHA_IPOJUCA_1": dados.get("planilha_ipojuca_1"),
            "PLANILHA_IPOJUCA_2": dados.get("planilha_ipojuca_2"),
            "PLANILHA_ITAJAI_1": dados.get("planilha_itajai_1"),
            "PLANILHA_ITAJAI_2": dados.get("planilha_itajai_2"),
        })
        return jsonify({"status": "success", "message": "Configurações salvas no arquivo .env!"})
    
    # GET
    load_dotenv(ENV_PATH)
    return jsonify({
        "tenant_id": os.getenv("SHAREPOINT_TENANT_ID") or "",
        "client_id": os.getenv("SHAREPOINT_CLIENT_ID") or "",
        "client_secret": os.getenv("SHAREPOINT_CLIENT_SECRET") or "",
        "drive_id": os.getenv("SHAREPOINT_DRIVE_ID") or "",
        "planilha_ipojuca_1": os.getenv("PLANILHA_IPOJUCA_1") or "",
        "planilha_ipojuca_2": os.getenv("PLANILHA_IPOJUCA_2") or "",
        "planilha_itajai_1": os.getenv("PLANILHA_ITAJAI_1") or "",
        "planilha_itajai_2": os.getenv("PLANILHA_ITAJAI_2") or "",
    })

@app.route('/api/sharepoint/testar_conexao', methods=['POST'])
def sharepoint_testar_conexao():
    dados = request.json
    tenant_id = dados.get("tenant_id")
    client_id = dados.get("client_id")
    client_secret = dados.get("client_secret")
    drive_id = dados.get("drive_id")
    
    caminhos = {
        "planilha_ipojuca_1": dados.get("planilha_ipojuca_1"),
        "planilha_ipojuca_2": dados.get("planilha_ipojuca_2"),
        "planilha_itajai_1": dados.get("planilha_itajai_1"),
        "planilha_itajai_2": dados.get("planilha_itajai_2"),
    }
    
    client = SharePointClient(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        drive_id=drive_id
    )
    
    res = client.testar_conexao(caminhos)
    return jsonify(res)

@app.route('/api/entreposto/executar', methods=['POST'])
def executar_entreposto():
    dados = request.json
    entreposto = dados.get("entreposto")
    
    if not entreposto:
        return jsonify({"status": "error", "message": "Entreposto não informado."}), 400
        
    if log_sys.is_running:
        return jsonify({"status": "error", "message": "Já existe uma automação em andamento."}), 400

    def worker():
        log_sys.is_running = True
        try:
            executar_automacao_entreposto(entreposto)
        except Exception as e:
            log_sys.write(f"❌ Falha fatal na thread do entreposto: {e}")
        finally:
            log_sys.is_running = False

    t = threading.Thread(target=worker)
    t.daemon = True
    t.start()
    return jsonify({"status": "started"})

# Estado global para processamento
entreposto_processamento_estado = {
    "entreposto": None,
    "cargas": [],
    "dados": {},
    "status_etapas": {}  # {remessa: {"basico": "pending", "picking": "pending", "sm": "pending", "tolerancia": "pending"}}
}

@app.route('/api/entreposto/resultado', methods=['GET'])
def buscar_resultado_entreposto():
    from Entreposto import ultimo_resultado
    return jsonify(ultimo_resultado)

@app.route('/api/entreposto/dados_processamento', methods=['GET'])
def dados_processamento():
    global entreposto_processamento_estado
    return jsonify(entreposto_processamento_estado)

@app.route('/api/entreposto/multiplicadores', methods=['GET', 'POST'])
def api_multiplicadores():
    if request.method == 'POST':
        dados = request.json
        material = dados.get("material")
        try:
            multiplo = float(str(dados.get("multiplo")).replace(",", "."))
            if not material:
                raise ValueError("Material inválido")
            db.salvar_multiplicador(material.strip().upper(), multiplo)
            return jsonify({"status": "success", "message": "Multiplicador salvo com sucesso!"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400
    
    # GET
    try:
        return jsonify(db.obter_multiplicadores())
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/entreposto/multiplicadores/<material>', methods=['DELETE'])
def api_deletar_multiplicador(material):
    try:
        db.deletar_multiplicador(material.strip().upper())
        return jsonify({"status": "success", "message": "Multiplicador deletado com sucesso!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/entreposto/processar_selecionadas', methods=['POST'])
def processar_selecionadas_entreposto():
    global entreposto_processamento_estado
    dados = request.json
    cargas = dados.get("cargas", [])
    entreposto = dados.get("entreposto")
    
    if not cargas or not entreposto:
        return jsonify({"status": "error", "message": "Cargas ou Entreposto não informado."}), 400
        
    try:
        # Carrega os dados estruturados do SharePoint
        cargas_dados = EntrepostoProcessador.obter_dados_etapas(entreposto, cargas)
        
        # Inicializa o status das etapas para cada remessa
        status_etapas = {}
        for c_id, c_val in cargas_dados.items():
            for r_val in c_val["remessas"]:
                status_etapas[r_val["remessa"]] = {
                    "basico": "pending",
                    "picking": "pending",
                    "sm": "pending",
                    "tolerancia": "pending",
                    "of": "pending",
                    "of_numero": r_val.get("of_planilha", "")
                }
                
        entreposto_processamento_estado = {
            "entreposto": entreposto,
            "cargas": cargas,
            "dados": cargas_dados,
            "status_etapas": status_etapas
        }
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/entreposto/processar_etapa', methods=['POST'])
def processar_etapa_entreposto():
    global entreposto_processamento_estado
    dados = request.json
    etapa = dados.get("etapa")  # "1", "2", "3", "tolerancia", "all"
    multiplos_custom = dados.get("multiplos", {})  # {remessa: valor}
    remessas_selecionadas = dados.get("remessas_selecionadas", None)
    
    if not entreposto_processamento_estado["cargas"]:
        return jsonify({"status": "error", "message": "Nenhuma carga selecionada para processar."}), 400
        
    if log_sys.is_running:
        return jsonify({"status": "error", "message": "Já existe uma automação em andamento."}), 400
        
    def worker():
        log_sys.is_running = True
        
        # Só conecta no SAP GUI se a etapa precisar dele
        session = None
        if etapa in ["1", "2", "3", "tolerancia", "all"]:
            session = conectar_sap()
            if not session:
                log_sys.write("❌ Falha de conexão com o SAP GUI. Encerrando.")
                log_sys.is_running = False
                return
            
        dados_cargas = entreposto_processamento_estado["dados"]
        status_etapas = entreposto_processamento_estado["status_etapas"]
        
        # Reset status for selected remessas
        if remessas_selecionadas:
            for r_sel in remessas_selecionadas:
                if r_sel in status_etapas:
                    if etapa in ["1", "all"]:
                        status_etapas[r_sel]["basico"] = "pending"
                    if etapa in ["2", "all"]:
                        status_etapas[r_sel]["picking"] = "pending"
                    if etapa in ["3", "all"]:
                        status_etapas[r_sel]["sm"] = "pending"
                    if etapa == "tolerancia":
                        status_etapas[r_sel]["tolerancia"] = "pending"
                    if etapa == "of":
                        status_etapas[r_sel]["of"] = "pending"
                        status_etapas[r_sel]["of_numero"] = ""
        
        # Carrega credenciais do SAP Web se for etapa "of"
        usuario = ""
        senha = ""
        if etapa == "of":
            load_dotenv(ENV_PATH)
            usuario = os.getenv("SAP_WEB_USER") or ""
            senha = os.getenv("SAP_WEB_PASSWORD") or ""
            if not usuario or not senha:
                log_sys.write("❌ Credenciais SAP Web não configuradas nas configurações. Vá em 'Configurar Credenciais SAP' na página de Expedição.")
                log_sys.is_running = False
                return
        
        try:
            # ETAPA 1: Básico (Atualizar informações básicas)
            if etapa in ["1", "all"]:
                EntrepostoProcessador.rodar_atualizar_basico(session, dados_cargas, status_etapas, remessas_selecionadas)
                    
            # ETAPA 2: Picking
            if etapa in ["2", "all"]:
                EntrepostoProcessador.rodar_picking(session, dados_cargas, multiplos_custom, status_etapas, remessas_selecionadas)
                    
            # ETAPA 3: SM (Transportadora parceira)
            if etapa in ["3", "all"]:
                EntrepostoProcessador.rodar_sm(session, dados_cargas, status_etapas, remessas_selecionadas)
            
            # ETAPA Tolerância: Checar Tolerâncias via MM
            if etapa == "tolerancia":
                EntrepostoProcessador.rodar_verificar_tolerancia(session, dados_cargas, status_etapas, remessas_selecionadas)
                
            # ETAPA OF: Criar Ordem de Frete (SAP Web)
            if etapa == "of":
                EntrepostoProcessador.rodar_criar_ordem_frete(usuario, senha, dados_cargas, status_etapas, remessas_selecionadas)
                    
            log_sys.write("🎉 Processamento das etapas de Entreposto finalizado com sucesso!")
        except Exception as ex:
            log_sys.write(f"❌ Ocorreu um erro inesperado durante a automação: {ex}")
        finally:
            log_sys.is_running = False

    t = threading.Thread(target=worker)
    t.daemon = True
    t.start()
    return jsonify({"status": "started"})

@app.route('/api/sap_web/config', methods=['GET', 'POST'])
def sap_web_config():
    if request.method == 'POST':
        dados = request.json
        salvar_configuracoes_env({
            "SAP_WEB_USER": dados.get("sap_web_user"),
            "SAP_WEB_PASSWORD": dados.get("sap_web_password"),
        })
        return jsonify({"status": "success", "message": "Credenciais SAP Web salvas com sucesso!"})
    
    # GET
    load_dotenv(ENV_PATH)
    return jsonify({
        "sap_web_user": os.getenv("SAP_WEB_USER") or "",
        "sap_web_password": os.getenv("SAP_WEB_PASSWORD") or "",
    })

@app.route('/api/packlist/baixar', methods=['POST'])
def baixar_packlist():
    dados = request.json
    remessas_str = dados.get('remessas', '')
    pasta_destino = dados.get('pasta_destino', '')
    tipo = dados.get('tipo', 'normal')
    
    remessas = [r.strip() for r in remessas_str.split(',') if r.strip()]
    
    if not remessas:
        return jsonify({"status": "error", "message": "Nenhuma remessa informada."}), 400
    
    if not pasta_destino:
        return jsonify({"status": "error", "message": "Pasta de destino não selecionada."}), 400
    
    if log_sys.is_running:
        return jsonify({"status": "error", "message": "Já existe uma automação em andamento."}), 400
    
    load_dotenv(ENV_PATH)
    usuario = os.getenv("SAP_WEB_USER") or ""
    senha = os.getenv("SAP_WEB_PASSWORD") or ""
    
    def worker():
        log_sys.is_running = True
        try:
            baixar_packlist_sap(remessas, pasta_destino, usuario, senha, tipo=tipo)
        except Exception as e:
            log_sys.write(f"❌ Falha fatal no download de Packlist: {e}")
        finally:
            log_sys.is_running = False
    
    t = threading.Thread(target=worker)
    t.daemon = True
    t.start()
    return jsonify({"status": "started"})


@app.route('/api/entreposto/exportar_excel', methods=['POST'])
def exportar_excel_entreposto():
    import pandas as pd
    dados = request.json
    status_etapas = dados.get("status_etapas", {})
    
    rows = []
    for remessa, status in status_etapas.items():
        of_num = status.get("of_numero", "")
        rows.append({
            "Remessa": remessa,
            "Ordem de Frete (OF)": of_num if of_num else "Não Gerada",
            "Status OF": status.get("of", "pending")
        })
        
    df = pd.DataFrame(rows)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='OFs Geradas')
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='remessas_e_ofs.xlsx'
    )


# --- ROTAS DA API DE CABOTAGEM ---

@app.route('/api/cabotagem/config', methods=['GET', 'POST'])
def api_cabotagem_config():
    if request.method == 'POST':
        dados = request.json
        salvar_configuracoes_env({
            "PLANILHA_CABOTAGEM": dados.get("planilha_cabotagem"),
            "PLANILHA_CABOTAGEM_ABA": dados.get("planilha_cabotagem_aba"),
            "SAP_WEB_USER": dados.get("sap_web_user"),
            "SAP_WEB_PASSWORD": dados.get("sap_web_password"),
        })
        return jsonify({"status": "success", "message": "Configurações de Cabotagem salvas com sucesso!"})
    
    # GET
    load_dotenv(ENV_PATH)
    return jsonify({
        "planilha_cabotagem": os.getenv("PLANILHA_CABOTAGEM") or "",
        "planilha_cabotagem_aba": os.getenv("PLANILHA_CABOTAGEM_ABA") or "",
        "sap_web_user": os.getenv("SAP_WEB_USER") or "",
        "sap_web_password": os.getenv("SAP_WEB_PASSWORD") or "",
    })

@app.route('/api/cabotagem/carregar', methods=['POST'])
def api_cabotagem_carregar():
    try:
        containers = obter_dados_cabotagem()
        return jsonify({"status": "success", "containers": containers})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cabotagem/dados_processamento', methods=['GET'])
def api_cabotagem_dados_processamento():
    return jsonify(cabotagem_estado)

@app.route('/api/cabotagem/executar', methods=['POST'])
def api_cabotagem_executar():
    dados = request.json
    containers_selecionados = dados.get("containers", [])
    
    if not containers_selecionados:
        return jsonify({"status": "error", "message": "Nenhum container selecionado."}), 400
        
    if log_sys.is_running:
        return jsonify({"status": "error", "message": "Já existe uma automação em andamento."}), 400
        
    load_dotenv(ENV_PATH)
    usuario = os.getenv("SAP_WEB_USER") or ""
    senha = os.getenv("SAP_WEB_PASSWORD") or ""
    
    if not usuario or not senha:
        return jsonify({"status": "error", "message": "Credenciais SAP Web não configuradas nas configurações."}), 400
        
    def worker():
        log_sys.is_running = True
        try:
            rodar_criar_of_cabotagem(usuario, senha, containers_selecionados)
        except Exception as e:
            log_sys.write(f"❌ Falha fatal na thread de Cabotagem: {e}")
        finally:
            log_sys.is_running = False
            
    t = threading.Thread(target=worker)
    t.daemon = True
    t.start()
    
    return jsonify({"status": "started"})






@app.route('/api/cabotagem/exportar_excel', methods=['GET'])
def api_cabotagem_exportar_excel():
    from src.expedicao.cabotagem_processador import montar_relatorio_cabotagem
    import pandas as pd

    df = montar_relatorio_cabotagem(cabotagem_estado)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Cabotagem')
    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='cabotagem_ofs.xlsx'
    )


if __name__ == '__main__':
    
    import socket
    import webbrowser
    
    # 🔒 Checa se já tem outra instância rodando
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 5000))
        s.close()
    except OSError:
        print("⚠️  RPA Expedição já está em execução!")
        print("👉 Abrindo a janela existente...")
        webbrowser.open("http://127.0.0.1:5000")
        sys.exit(0)

    print("=" * 60)
    print("🚛 RPA Expedição - Painel de Controle v1.0.5")
    print("=" * 60)
    print("📡 Servidor iniciando em: http://127.0.0.1:5000")
    print("👉 Abra esse endereço no navegador (Chrome/Edge)")
    print("=" * 60)
    
    # Abre o navegador automaticamente após 1.5s
    import webbrowser
    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    
    # Sobe o Flask (uma vez só, na thread principal)
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False, threaded=True)