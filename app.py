"""
app.py - Back-end Flask do Sistema de Ordens de Producao.
"""

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from werkzeug.security import check_password_hash

from auth_utils import gerar_token_jwt, requer_autenticacao, requer_roles
from database import get_connection, init_db
from order_services import (
    ALLOWED_STATUSES,
    ServiceError,
    build_status_payload,
    create_order,
    delete_order,
    detect_bottlenecks,
    export_orders_pdf,
    export_orders_xlsx,
    forecast_overview,
    get_order_by_id,
    list_orders,
    load_logs,
    priority_order_sql,
    update_order_status,
)


app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)


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
    return jsonify({'erro': 'Erro interno. Contate o administrador.'}), 500


@app.route('/')
def index():
    return app.send_static_file('index.html')


@app.route('/login', methods=['POST'])
def login():
    dados = request.get_json(silent=True)
    if not dados:
        return jsonify({'erro': 'Body ausente ou invalido.'}), 400

    username = str(dados.get('username', '')).strip()
    password = str(dados.get('password', '')).strip()
    if not username or not password:
        return jsonify({'erro': 'Informe usuario e senha.'}), 400

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT username, senha_hash, role FROM usuarios WHERE username = ?',
            (username,)
        )
        usuario = cursor.fetchone()
    finally:
        conn.close()

    if usuario is None or not check_password_hash(usuario['senha_hash'], password):
        return jsonify({'erro': 'Credenciais invalidas.'}), 401

    return jsonify({
        'token': gerar_token_jwt(usuario['username'], usuario['role']),
        'usuario': {
            'username': usuario['username'],
            'role': usuario['role'],
        }
    }), 200


@app.route('/me', methods=['GET'])
@requer_autenticacao
def me():
    from auth_utils import usuario_atual

    username, role = usuario_atual()
    return jsonify({'username': username, 'role': role}), 200


@app.route('/status')
def status():
    return jsonify(build_status_payload())


@app.route('/ordens', methods=['GET'])
def listar_ordens():
    status_filtro = request.args.get('status')
    ordenar = request.args.get('ordenar', '').strip().lower()

    if status_filtro:
        from order_services import normalizar_status

        status_filtro = normalizar_status(status_filtro)
        if status_filtro not in ALLOWED_STATUSES:
            return jsonify({
                'erro': f'Status invalido. Use: {list(ALLOWED_STATUSES)}'
            }), 400

    order_by = priority_order_sql('o') if ordenar == 'prioridade' else 'o.id DESC'
    return jsonify(list_orders(status_filtro=status_filtro, order_by=order_by))


@app.route('/ordens/prioridade', methods=['GET'])
def listar_ordens_por_prioridade():
    return jsonify(list_orders(order_by=priority_order_sql('o')))


@app.route('/ordens/<int:ordem_id>', methods=['GET'])
def buscar_ordem(ordem_id):
    ordem = get_order_by_id(ordem_id)
    if ordem is None:
        return jsonify({'erro': f'Ordem {ordem_id} nao encontrada.'}), 404
    return jsonify(ordem), 200


@app.route('/ordens', methods=['POST'])
@requer_autenticacao
@requer_roles('admin')
def criar_ordem():
    try:
        return jsonify(create_order(request.get_json(silent=True))), 201
    except ServiceError as exc:
        return jsonify({'erro': exc.message}), exc.status_code


@app.route('/ordens/<int:ordem_id>', methods=['PUT'])
@requer_autenticacao
@requer_roles('admin', 'operador')
def atualizar_ordem(ordem_id):
    try:
        return jsonify(update_order_status(ordem_id, request.get_json(silent=True))), 200
    except ServiceError as exc:
        return jsonify({'erro': exc.message}), exc.status_code


@app.route('/ordens/<int:ordem_id>', methods=['DELETE'])
@requer_autenticacao
@requer_roles('admin')
def remover_ordem(ordem_id):
    try:
        return jsonify(delete_order(ordem_id)), 200
    except ServiceError as exc:
        return jsonify({'erro': exc.message}), exc.status_code


@app.route('/logs', methods=['GET'])
@requer_autenticacao
def listar_logs():
    try:
        limit = int(request.args.get('limit', 100))
    except ValueError:
        return jsonify({'erro': 'limit deve ser inteiro.'}), 400
    limit = max(1, min(limit, 500))
    return jsonify(load_logs(limit=limit)), 200


@app.route('/analytics/previsoes', methods=['GET'])
@requer_autenticacao
def analytics_previsoes():
    return jsonify(forecast_overview()), 200


@app.route('/analytics/gargalos', methods=['GET'])
@requer_autenticacao
def analytics_gargalos():
    return jsonify(detect_bottlenecks()), 200


@app.route('/ordens/exportar', methods=['GET'])
@requer_autenticacao
def exportar_ordens():
    formato = request.args.get('formato', '').strip().lower()
    if formato not in {'pdf', 'xlsx'}:
        return jsonify({'erro': 'Formato invalido. Use pdf ou xlsx.'}), 400

    ordens = list_orders(order_by=priority_order_sql('o'))
    try:
        if formato == 'xlsx':
            buffer = export_orders_xlsx(ordens)
            return send_file(
                buffer,
                as_attachment=True,
                download_name='ordens_producao.xlsx',
                mimetype=(
                    'application/vnd.openxmlformats-officedocument.'
                    'spreadsheetml.sheet'
                ),
            )

        buffer = export_orders_pdf(ordens)
        return send_file(
            buffer,
            as_attachment=True,
            download_name='ordens_producao.pdf',
            mimetype='application/pdf',
        )
    except ServiceError as exc:
        return jsonify({'erro': exc.message}), exc.status_code


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
