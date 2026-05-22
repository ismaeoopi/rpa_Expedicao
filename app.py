import os
import sys
import threading
from datetime import datetime
from flask import Flask, render_template, jsonify, request

# --- IMPORTAÇÕES MODULARES ---
from src.utils.common import log_sys
from src.utils.windows_utils import abrir_seletor_ficheiro_excel, abrir_seletor_pasta
from src.expedicao.picking import processarPicking
from src.expedicao.selecao_uc import processarRemessaComUc
from src.expedicao.sm_remessa import smRemessa
from src.expedicao.fip_etiquetas import salvarFIP
from src.estoque.packlist import analisar_planilha_packlist
from src.estoque.processo_completo import processo_estoque
import src.utils.db as db

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
app = Flask(__name__, template_folder=template_folder)

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
            if opcao == 1:
                processarRemessaComUc(caminho, dados_colados)
            elif opcao == 2:
                processarPicking(caminho, dados_colados)
            elif opcao == 3:
                smRemessa(caminho, dados_colados)
            elif opcao == 4:
                salvarFIP(remessas, caminho_pasta if caminho_pasta else None)
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