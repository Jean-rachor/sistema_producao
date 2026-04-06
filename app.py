"""
app.py - Back-end Flask do Sistema de Ordens de Producao.
API REST com CRUD completo, autenticacao por API Key,
sanitizacao de entradas e tratamento de erros global.
Author: Codex
Date: 2026
Version: 2.0.0 (com seguranca)
SENAI Jaragua do Sul - Tecnico em Cibersistemas para Automacao WEG
"""

from functools import wraps
import datetime
import html

from flask import Flask, jsonify, request
from flask_cors import CORS

from database import get_connection, init_db


app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

# Chave de autenticacao da API
# Em producao: use variavel de ambiente
API_KEY = 'senai-cibersistemas-2026-chave-segura'


def requer_autenticacao(f):
    """Protege rotas exigindo X-API-Key valida no cabecalho."""

    @wraps(f)
    def decorador(*args, **kwargs):
        chave = request.headers.get('X-API-Key')

        if not chave:
            return jsonify({
                'erro': 'Autenticacao necessaria. Envie X-API-Key.'
            }), 401

        if chave != API_KEY:
            return jsonify({'erro': 'Chave de API invalida.'}), 403

        return f(*args, **kwargs)

    return decorador


@app.errorhandler(400)
def bad_request(e):
    return jsonify({'erro': 'Requisicao invalida.'}), 400


@app.errorhandler(401)
def unauthorized(e):
    return jsonify({'erro': 'Autenticacao necessaria.'}), 401


@app.errorhandler(403)
def forbidden(e):
    return jsonify({'erro': 'Acesso negado.'}), 403


@app.errorhandler(404)
def not_found(e):
    return jsonify({'erro': 'Recurso nao encontrado.'}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({'erro': 'Metodo nao permitido.'}), 405


@app.errorhandler(500)
def internal_error(e):
    return jsonify({
        'erro': 'Erro interno. Contate o administrador.'
    }), 500


@app.route('/')
def index():
    """Serve o arquivo index.html da pasta static."""
    return app.send_static_file('index.html')


@app.route('/status')
def status():
    """Health check da API com contagem de ordens."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) AS total FROM ordens')
    resultado = cursor.fetchone()
    conn.close()

    total_ordens = resultado['total']

    return jsonify({
        'status': 'online',
        'sistema': 'Sistema de Ordens de Producao',
        'versao': '2.0.0',
        'total_ordens': total_ordens,
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })


@app.route('/ordens', methods=['GET'])
def listar_ordens():
    """Lista todas as ordens. Aceita ?status= como filtro."""
    status_filtro = request.args.get('status')

    conn = get_connection()
    cursor = conn.cursor()

    if status_filtro:
        cursor.execute(
            'SELECT * FROM ordens WHERE status = ? ORDER BY id DESC',
            (status_filtro,)
        )
    else:
        cursor.execute('SELECT * FROM ordens ORDER BY id DESC')

    ordens = cursor.fetchall()
    conn.close()

    return jsonify([dict(o) for o in ordens])


@app.route('/ordens/<int:ordem_id>', methods=['GET'])
def buscar_ordem(ordem_id):
    """Busca uma ordem pelo ID. Retorna 404 se nao encontrada."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM ordens WHERE id = ?', (ordem_id,))
    ordem = cursor.fetchone()
    conn.close()

    if ordem is None:
        return jsonify({'erro': f'Ordem {ordem_id} nao encontrada.'}), 404

    return jsonify(dict(ordem)), 200


@app.route('/ordens', methods=['POST'])
@requer_autenticacao
def criar_ordem():
    """Cria nova ordem. Requer X-API-Key. Sanitiza entradas."""
    dados = request.get_json(silent=True)

    if not dados:
        return jsonify({'erro': 'Body ausente ou invalido.'}), 400

    produto = html.escape(str(dados.get('produto', '')).strip())
    if not produto:
        return jsonify({'erro': 'Campo produto e obrigatorio.'}), 400

    if len(produto) > 200:
        return jsonify({'erro': 'Produto: max 200 caracteres.'}), 400

    quantidade = dados.get('quantidade')
    if quantidade is None:
        return jsonify({'erro': 'Campo quantidade e obrigatorio.'}), 400

    try:
        quantidade = int(quantidade)
        if quantidade <= 0 or quantidade > 999999:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({
            'erro': 'quantidade: inteiro entre 1 e 999999.'
        }), 400

    status_validos = ['Pendente', 'Em andamento', 'Concluida']
    status = dados.get('status', 'Pendente')
    if status not in status_validos:
        return jsonify({
            'erro': f'Status invalido. Use: {status_validos}'
        }), 400

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


@app.route('/ordens/<int:ordem_id>', methods=['PUT'])
@requer_autenticacao
def atualizar_ordem(ordem_id):
    """Atualiza status de uma ordem. Requer X-API-Key."""
    dados = request.get_json(silent=True)

    if not dados:
        return jsonify({'erro': 'Body ausente ou invalido.'}), 400

    status_validos = ['Pendente', 'Em andamento', 'Concluida']
    novo_status = dados.get('status', '').strip()

    if not novo_status:
        return jsonify({'erro': 'Campo status e obrigatorio.'}), 400

    if novo_status not in status_validos:
        return jsonify({
            'erro': f'Status invalido. Use: {status_validos}'
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


@app.route('/ordens/<int:ordem_id>', methods=['DELETE'])
@requer_autenticacao
def remover_ordem(ordem_id):
    """Remove ordem pelo ID. Requer X-API-Key."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, produto FROM ordens WHERE id = ?', (ordem_id,))
    ordem = cursor.fetchone()

    if ordem is None:
        conn.close()
        return jsonify({'erro': f'Ordem {ordem_id} nao encontrada.'}), 404

    nome_produto = ordem['produto']
    cursor.execute('DELETE FROM ordens WHERE id = ?', (ordem_id,))

    cursor.execute('SELECT COUNT(*) AS total FROM ordens')
    total_restante = cursor.fetchone()['total']
    if total_restante == 0:
        cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'ordens'")

    conn.commit()
    conn.close()

    return jsonify({
        'mensagem': f'Ordem {ordem_id} ({nome_produto}) removida.',
        'id_removido': ordem_id
    }), 200


@app.route('/fabrica/<nome_fabrica>')
def boas_vindas(nome_fabrica):
    return jsonify({
        'mensagem': f'Bem-vindo, {nome_fabrica}! Sistema de OP online.'
    })


@app.route('/teste-delete', methods=['DELETE'])
def teste_delete():
    return {'msg': 'DELETE funcionando'}, 200


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
