import base64
import hashlib
import hmac
import json
import os
import time
from functools import wraps

from flask import g, jsonify, request


API_KEY = os.environ.get('API_KEY', 'senai-cibersistemas-2026-chave-segura')
JWT_SECRET = os.environ.get('JWT_SECRET', 'jwt-dev-secret-2026')
JWT_EXP_SECONDS = int(os.environ.get('JWT_EXP_SECONDS', '28800'))


def _b64url_encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _b64url_decode(data):
    padding = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def gerar_token_jwt(username, role):
    issued_at = int(time.time())
    payload = {
        'sub': username,
        'role': role,
        'iat': issued_at,
        'exp': issued_at + JWT_EXP_SECONDS,
    }
    header = {'alg': 'HS256', 'typ': 'JWT'}

    header_b64 = _b64url_encode(
        json.dumps(header, separators=(',', ':')).encode('utf-8')
    )
    payload_b64 = _b64url_encode(
        json.dumps(payload, separators=(',', ':')).encode('utf-8')
    )
    signing_input = f'{header_b64}.{payload_b64}'.encode('utf-8')
    signature = hmac.new(
        JWT_SECRET.encode('utf-8'),
        signing_input,
        hashlib.sha256
    ).digest()
    return f'{header_b64}.{payload_b64}.{_b64url_encode(signature)}'


def validar_token_jwt(token):
    try:
        header_b64, payload_b64, signature_b64 = token.split('.')
    except ValueError as exc:
        raise ValueError('Token JWT malformado.') from exc

    signing_input = f'{header_b64}.{payload_b64}'.encode('utf-8')
    expected_signature = hmac.new(
        JWT_SECRET.encode('utf-8'),
        signing_input,
        hashlib.sha256
    ).digest()
    received_signature = _b64url_decode(signature_b64)

    if not hmac.compare_digest(received_signature, expected_signature):
        raise ValueError('Token JWT invalido.')

    payload = json.loads(_b64url_decode(payload_b64).decode('utf-8'))
    if payload.get('exp', 0) < int(time.time()):
        raise ValueError('Token JWT expirado.')

    return payload


def usuario_atual():
    current = getattr(g, 'current_user', None) or {}
    return current.get('username', 'sistema'), current.get('role', 'sistema')


def requer_autenticacao(f):
    @wraps(f)
    def decorador(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1].strip()
            try:
                payload = validar_token_jwt(token)
            except ValueError as exc:
                return jsonify({'erro': str(exc)}), 401

            g.current_user = {
                'username': payload.get('sub'),
                'role': payload.get('role'),
                'auth': 'jwt',
            }
            return f(*args, **kwargs)

        chave = request.headers.get('X-API-Key')
        if chave:
            if chave != API_KEY:
                return jsonify({'erro': 'Chave de API invalida.'}), 403

            g.current_user = {
                'username': 'legacy-api-key',
                'role': 'admin',
                'auth': 'api_key',
            }
            return f(*args, **kwargs)

        return jsonify({'erro': 'Autenticacao necessaria.'}), 401

    return decorador


def requer_roles(*roles_permitidos):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            current = getattr(g, 'current_user', None) or {}
            role = current.get('role')
            if role not in roles_permitidos:
                return jsonify({
                    'erro': 'Acesso negado.',
                    'roles_permitidos': list(roles_permitidos),
                }), 403
            return f(*args, **kwargs)

        return wrapper

    return decorator
