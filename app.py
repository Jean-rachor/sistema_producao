# ============================================================
# app.py – Back-end Flask do Sistema de Ordens de Produção
# ============================================================

from flask import Flask, jsonify, request
from flask_cors import CORS
from database import init_db, get_connection
import datetime
import time
import platform

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

# ── ROTA 1: Página Inicial ──────────────────────────────────
@app.route('/')
def index():
    return app.send_static_file('index.html')


# ── ROTA 2: Status da API (COMPLETO) ────────────────────────
@app.route('/status')
def status():
    """Health check completo da API."""

    inicio = time.time()

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) as total FROM ordens')
        resultado = cursor.fetchone()

        total_ordens = resultado["total"]
        db_status = "online"

        conn.close()

    except Exception as e:
        total_ordens = None
        db_status = "erro"
        erro_db = str(e)

    tempo_resposta = round((time.time() - inicio) * 1000, 2)

    resposta = {
        "status": "online",
        "sistema": "Sistema de Ordens de Producao",
        "versao": "1.0.0",
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

        "banco": {
            "status": db_status,
            "total_ordens": total_ordens
        },

        "performance": {
            "tempo_resposta_ms": tempo_resposta
        },

        "servidor": {
            "sistema_operacional": platform.system(),
            "versao_so": platform.version(),
            "python": platform.python_version()
        }
    }

    if db_status == "erro":
        resposta["banco"]["erro"] = erro_db

    return jsonify(resposta)


# ── ROTA 3: Listar todas as ordens ──────────────────────────
@app.route('/ordens', methods=['GET'])
def listar_ordens():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM ordens ORDER BY id DESC')
    ordens = cursor.fetchall()

    conn.close()

    return jsonify([dict(o) for o in ordens])


# ── ROTA 4: Boas-vindas dinâmicas ───────────────────────────
@app.route('/fabrica/<nome_fabrica>')
def boas_vindas(nome_fabrica):
    """
    Rota com parametro dinamico.
    Exemplo: /fabrica/WEG
    """
    return jsonify({
        "mensagem": f"Bem-vindo, {nome_fabrica}! Sistema de OP online.",
        "dica": "Esta e uma rota com parametro dinamico do Flask."
    })


# ── PONTO DE ENTRADA ───────────────────────────────────────
if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)