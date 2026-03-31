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


# ── ROTA 2: Status da API ───────────────────────────────────
@app.route('/status')
def status():
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


# ── ROTA 4: Buscar ordem por ID ─────────────────────────────
@app.route('/ordens/<int:ordem_id>', methods=['GET'])
def buscar_ordem(ordem_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM ordens WHERE id = ?', (ordem_id,))
    ordem = cursor.fetchone()

    conn.close()

    if ordem is None:
        return jsonify({'erro': f'Ordem {ordem_id} nao encontrada.'}), 404

    return jsonify(dict(ordem)), 200


# ── ROTA 5: Criar nova ordem (POST) ─────────────────────────
@app.route('/ordens', methods=['POST'])
def criar_ordem():
    dados = request.get_json()

    if not dados:
        return jsonify({'erro': 'Body da requisicao ausente ou invalido.'}), 400

    produto = dados.get('produto', '').strip()
    if not produto:
        return jsonify({'erro': 'Campo "produto" e obrigatorio.'}), 400

    quantidade = dados.get('quantidade')
    if quantidade is None:
        return jsonify({'erro': 'Campo "quantidade" e obrigatorio.'}), 400

    try:
        quantidade = int(quantidade)
        if quantidade <= 0:
            raise ValueError()
    except:
        return jsonify({'erro': 'Quantidade deve ser inteiro positivo.'}), 400

    status_validos = ['Pendente', 'Em andamento', 'Concluida']
    status = dados.get('status', 'Pendente')

    if status not in status_validos:
        return jsonify({'erro': f'Status invalido. Use {status_validos}'}), 400

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        'INSERT INTO ordens (produto, quantidade, status) VALUES (?, ?, ?)',
        (produto, quantidade, status)
    )

    conn.commit()
    novo_id = cursor.lastrowid
    conn.close()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM ordens WHERE id = ?', (novo_id,))
    nova_ordem = cursor.fetchone()

    conn.close()

    return jsonify(dict(nova_ordem)), 201


# ── ROTA 6: Atualizar status (PUT) ──────────────────────────
@app.route('/ordens/<int:ordem_id>', methods=['PUT'])
def atualizar_ordem(ordem_id):
    dados = request.get_json()

    if not dados:
        return jsonify({'erro': 'Body da requisicao ausente ou invalido.'}), 400

    status_validos = ['Pendente', 'Em andamento', 'Concluida']
    novo_status = dados.get('status', '').strip()

    if not novo_status:
        return jsonify({'erro': 'Campo "status" e obrigatorio.'}), 400

    if novo_status not in status_validos:
        return jsonify({
            'erro': f'Status invalido. Valores permitidos: {status_validos}'
        }), 400

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT id FROM ordens WHERE id = ?', (ordem_id,))
    if cursor.fetchone() is None:
        conn.close()
        return jsonify({'erro': f'Ordem {ordem_id} nao encontrada.'}), 404

    cursor.execute(
        'UPDATE ordens SET status = ? WHERE id = ?',
        (novo_status, ordem_id)
    )

    conn.commit()
    conn.close()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM ordens WHERE id = ?', (ordem_id,))
    ordem_atualizada = cursor.fetchone()

    conn.close()

    return jsonify(dict(ordem_atualizada)), 200


# ── ROTA 7: Remover ordem (DELETE) ──────────────────────────
@app.route('/ordens/<int:ordem_id>', methods=['DELETE'])
def remover_ordem(ordem_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT id, produto FROM ordens WHERE id = ?', (ordem_id,))
    ordem = cursor.fetchone()

    if ordem is None:
        conn.close()
        return jsonify({'erro': f'Ordem {ordem_id} nao encontrada.'}), 404

    nome_produto = ordem['produto']

    cursor.execute('DELETE FROM ordens WHERE id = ?', (ordem_id,))
    conn.commit()
    conn.close()

    return jsonify({
        'mensagem': f'Ordem {ordem_id} ({nome_produto}) removida com sucesso.',
        'id_removido': ordem_id
    }), 200


# ── ROTA 8: Boas-vindas ─────────────────────────────────────
@app.route('/fabrica/<nome_fabrica>')
def boas_vindas(nome_fabrica):
    return jsonify({
        "mensagem": f"Bem-vindo, {nome_fabrica}! Sistema de OP online."
    })

@app.route('/teste-delete', methods=['DELETE'])
def teste_delete():
    return {"msg": "DELETE funcionando"}, 200

# ── PONTO DE ENTRADA ───────────────────────────────────────
if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)