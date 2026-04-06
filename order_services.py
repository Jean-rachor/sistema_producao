import datetime
import html
import io
import json
import os
import threading
from collections import defaultdict
from urllib import error as urllib_error
from urllib import request as urllib_request

from auth_utils import usuario_atual
from database import get_connection


WEBHOOK_URLS = [
    url.strip()
    for url in os.environ.get('WEBHOOK_URLS', '').split(',')
    if url.strip()
]

ALLOWED_STATUSES = ('Pendente', 'Em andamento', 'Concluida')
ALLOWED_PRIORITIES = ('Alta', 'Media', 'Baixa')
FX_RATES = {
    'USD': 0.20,
    'EUR': 0.18,
    'JPY': 31.20,
    'RUB': 18.70,
    'GBP': 0.15,
    'CNY': 1.43,
}


class ServiceError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def now_local():
    return datetime.datetime.now()


def now_local_str():
    return now_local().strftime('%Y-%m-%d %H:%M:%S')


def parse_db_datetime(value):
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(str(value))
    except ValueError:
        return None


def parse_iso_date(value):
    if value in (None, ''):
        return None
    try:
        return datetime.date.fromisoformat(str(value))
    except ValueError:
        return None


def normalizar_status(value):
    if value is None:
        return None
    texto = str(value).strip().lower()
    mapa = {
        'pendente': 'Pendente',
        'em andamento': 'Em andamento',
        'concluida': 'Concluida',
        'concluída': 'Concluida',
    }
    return mapa.get(texto)


def normalizar_prioridade(value):
    if value is None or str(value).strip() == '':
        return 'Media'
    texto = str(value).strip().lower()
    mapa = {
        'alta': 'Alta',
        'media': 'Media',
        'média': 'Media',
        'baixa': 'Baixa',
    }
    return mapa.get(texto)


def formatar_duracao_horas(hours):
    horas = float(hours or 0)
    if horas <= 0:
        return 'Sem historico'
    if horas < 24:
        return f'{horas:.1f} h'
    dias = int(horas // 24)
    horas_restantes = int(round(horas % 24))
    return f'{dias} d {horas_restantes} h' if horas_restantes else f'{dias} d'


def converter_valor_total(valor_brl):
    valor = round(float(valor_brl or 0), 2)
    return {
        moeda: round(valor * taxa, 2)
        for moeda, taxa in FX_RATES.items()
    }


def heuristic_hours_for_order(quantidade):
    qty = max(int(quantidade or 1), 1)
    return max(6.0, min(qty * 0.20, 240.0))


def priority_order_sql(alias='o'):
    return (
        f"CASE {alias}.prioridade "
        "WHEN 'Alta' THEN 1 "
        "WHEN 'Media' THEN 2 "
        "ELSE 3 END, "
        f"{alias}.data_prevista IS NULL, {alias}.data_prevista ASC, {alias}.id DESC"
    )


def _post_webhooks(payload):
    data = json.dumps(payload, ensure_ascii=False, default=str).encode('utf-8')
    for url in WEBHOOK_URLS:
        req = urllib_request.Request(
            url,
            data=data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        try:
            with urllib_request.urlopen(req, timeout=5):
                pass
        except (urllib_error.URLError, ValueError) as exc:
            print(f'Webhook falhou para {url}: {exc}')


def disparar_webhooks(evento, ordem_data):
    if not WEBHOOK_URLS:
        return
    username, role = usuario_atual()
    payload = {
        'evento': evento,
        'timestamp': now_local_str(),
        'usuario': username,
        'role': role,
        'ordem': ordem_data,
    }
    threading.Thread(target=_post_webhooks, args=(payload,), daemon=True).start()


def registrar_log_acao(acao, ordem_id=None, detalhe=None):
    username, role = usuario_atual()
    detalhe_texto = (
        json.dumps(detalhe, ensure_ascii=False, default=str)
        if isinstance(detalhe, (dict, list))
        else detalhe
    )
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO log_acao (usuario, role, acao, ordem_id, detalhe, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (username, role, acao, ordem_id, detalhe_texto, now_local_str())
        )
        conn.commit()
    finally:
        conn.close()


def carregar_estatisticas_producao(conn):
    cursor = conn.cursor()
    cursor.execute(
        '''
        SELECT produto, quantidade, criado_em,
               COALESCE(concluido_em, atualizado_em, criado_em) AS finalizado_em
        FROM ordens
        WHERE status = 'Concluida'
        '''
    )
    bruto = defaultdict(lambda: {'duracoes': [], 'quantidades': []})
    duracoes_globais = []
    for row in cursor.fetchall():
        inicio = parse_db_datetime(row['criado_em'])
        fim = parse_db_datetime(row['finalizado_em'])
        if not inicio or not fim:
            continue
        duracao_horas = max((fim - inicio).total_seconds() / 3600, 1.0)
        bruto[row['produto']]['duracoes'].append(duracao_horas)
        bruto[row['produto']]['quantidades'].append(int(row['quantidade'] or 0))
        duracoes_globais.append(duracao_horas)

    estatisticas = {}
    for produto, info in bruto.items():
        estatisticas[produto] = {
            'media_horas': sum(info['duracoes']) / len(info['duracoes']),
            'amostras': len(info['duracoes']),
            'media_quantidade': (
                sum(info['quantidades']) / len(info['quantidades'])
                if info['quantidades'] else 0
            ),
        }

    media_global = (
        sum(duracoes_globais) / len(duracoes_globais)
        if duracoes_globais else 24.0
    )
    return estatisticas, media_global


def estimar_horas_producao(ordem, estatisticas, media_global):
    produto = ordem.get('produto')
    quantidade = int(ordem.get('quantidade') or 0)
    if produto in estatisticas:
        info = estatisticas[produto]
        media_quantidade = max(info['media_quantidade'], 1)
        fator = quantidade / media_quantidade if media_quantidade else 1
        return max(2.0, info['media_horas'] * min(max(fator, 0.5), 1.8))
    if media_global > 0:
        return max(4.0, media_global * min(max(quantidade / 100, 0.4), 1.7))
    return heuristic_hours_for_order(quantidade)


def enriquecer_ordem(row, estatisticas, media_global):
    ordem = dict(row)
    quantidade = int(ordem.get('quantidade') or 0)
    valor_unitario = round(float(ordem.get('valor_unitario') or 0), 2)
    valor_total = round(quantidade * valor_unitario, 2)
    prazo = parse_iso_date(ordem.get('data_prevista'))
    dias_restantes = None
    faixa_prazo = 'indefinido'
    if prazo:
        dias_restantes = (prazo - datetime.date.today()).days
        faixa_prazo = 'vermelho' if dias_restantes <= 7 else 'amarelo' if dias_restantes <= 14 else 'verde'

    horas_previstas = estimar_horas_producao(ordem, estatisticas, media_global)
    inicio = parse_db_datetime(ordem.get('criado_em'))
    previsao_fim = inicio + datetime.timedelta(hours=horas_previstas) if inicio else None
    bloqueada = bool(ordem.get('ordem_pai_id') and ordem.get('ordem_pai_status') != 'Concluida')
    prazo_em_risco = False
    if prazo and previsao_fim and ordem.get('status') != 'Concluida':
        limite = datetime.datetime.combine(prazo, datetime.time(23, 59, 59))
        prazo_em_risco = previsao_fim > limite

    ordem['valor_unitario'] = valor_unitario
    ordem['valor_total'] = valor_total
    ordem['conversoes_total'] = converter_valor_total(valor_total)
    ordem['dias_restantes'] = dias_restantes
    ordem['faixa_prazo'] = faixa_prazo
    ordem['tempo_previsto_producao_horas'] = round(horas_previstas, 2)
    ordem['tempo_previsto_producao_texto'] = formatar_duracao_horas(horas_previstas)
    ordem['previsao_conclusao'] = previsao_fim.strftime('%Y-%m-%d %H:%M:%S') if previsao_fim else None
    ordem['prazo_em_risco'] = prazo_em_risco
    ordem['bloqueada_por_dependencia'] = bloqueada
    ordem['ordem_pai'] = {
        'id': ordem.get('ordem_pai_id'),
        'status': ordem.get('ordem_pai_status'),
        'produto': ordem.get('ordem_pai_produto'),
    } if ordem.get('ordem_pai_id') else None
    ordem['prioridade_rank'] = {'Alta': 1, 'Media': 2, 'Baixa': 3}.get(ordem.get('prioridade'), 99)
    return ordem


def list_orders(status_filtro=None, order_by=None):
    conn = get_connection()
    try:
        estatisticas, media_global = carregar_estatisticas_producao(conn)
        cursor = conn.cursor()
        query = '''
            SELECT o.*, p.status AS ordem_pai_status, p.produto AS ordem_pai_produto
            FROM ordens o
            LEFT JOIN ordens p ON p.id = o.ordem_pai_id
        '''
        params = []
        if status_filtro:
            query += ' WHERE o.status = ?'
            params.append(status_filtro)
        query += f' ORDER BY {order_by or "o.id DESC"}'
        cursor.execute(query, params)
        return [enriquecer_ordem(row, estatisticas, media_global) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_order_by_id(ordem_id):
    conn = get_connection()
    try:
        estatisticas, media_global = carregar_estatisticas_producao(conn)
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT o.*, p.status AS ordem_pai_status, p.produto AS ordem_pai_produto
            FROM ordens o
            LEFT JOIN ordens p ON p.id = o.ordem_pai_id
            WHERE o.id = ?
            ''',
            (ordem_id,)
        )
        row = cursor.fetchone()
        return enriquecer_ordem(row, estatisticas, media_global) if row else None
    finally:
        conn.close()


def validate_money(value):
    if value in (None, ''):
        return 0.0
    try:
        valor = float(value)
    except (TypeError, ValueError) as exc:
        raise ServiceError('Valor unitario invalido.') from exc
    if valor < 0 or valor > 100000000:
        raise ServiceError('Valor unitario deve estar entre 0 e 100000000.')
    return round(valor, 2)


def validate_new_order_payload(dados, conn):
    if not dados:
        raise ServiceError('Body ausente ou invalido.')

    produto = html.escape(str(dados.get('produto', '')).strip())
    if not produto:
        raise ServiceError('Campo produto e obrigatorio.')
    if len(produto) > 200:
        raise ServiceError('Produto: max 200 caracteres.')

    quantidade = dados.get('quantidade')
    if quantidade is None:
        raise ServiceError('Campo quantidade e obrigatorio.')
    try:
        quantidade = int(quantidade)
        if quantidade <= 0 or quantidade > 999999:
            raise ValueError()
    except (TypeError, ValueError):
        raise ServiceError('quantidade: inteiro entre 1 e 999999.')

    status = normalizar_status(dados.get('status', 'Pendente'))
    if status not in ALLOWED_STATUSES:
        raise ServiceError(f'Status invalido. Use: {list(ALLOWED_STATUSES)}')

    prioridade = normalizar_prioridade(dados.get('prioridade', dados.get('priority')))
    if prioridade not in ALLOWED_PRIORITIES:
        raise ServiceError(f'Prioridade invalida. Use: {list(ALLOWED_PRIORITIES)}')

    valor_unitario = validate_money(dados.get('valorUnitario', dados.get('valor_unitario')))

    data_prevista_raw = dados.get('dataPrevista', dados.get('data_prevista'))
    data_prevista = parse_iso_date(data_prevista_raw)
    if data_prevista_raw not in (None, '') and data_prevista is None:
        raise ServiceError('dataPrevista deve estar no formato YYYY-MM-DD.')

    ordem_pai_id_raw = dados.get('ordemPaiId', dados.get('ordem_pai_id'))
    ordem_pai_id = None
    if ordem_pai_id_raw not in (None, '', 0, '0'):
        try:
            ordem_pai_id = int(ordem_pai_id_raw)
            if ordem_pai_id <= 0:
                raise ValueError()
        except (TypeError, ValueError):
            raise ServiceError('ordemPaiId deve ser um inteiro positivo.')

        cursor = conn.cursor()
        cursor.execute('SELECT id, status FROM ordens WHERE id = ?', (ordem_pai_id,))
        ordem_pai = cursor.fetchone()
        if ordem_pai is None:
            raise ServiceError('Ordem pai informada nao existe.')
        if status != 'Pendente' and ordem_pai['status'] != 'Concluida':
            raise ServiceError(
                'Ordem filha bloqueada: conclua a ordem pai antes de iniciar.',
                409
            )

    return {
        'produto': produto,
        'quantidade': quantidade,
        'status': status,
        'prioridade': prioridade,
        'valor_unitario': valor_unitario,
        'data_prevista': data_prevista.isoformat() if data_prevista else None,
        'ordem_pai_id': ordem_pai_id,
        'atualizado_em': now_local_str(),
        'concluido_em': now_local_str() if status == 'Concluida' else None,
    }


def create_order(dados):
    conn = get_connection()
    try:
        payload = validate_new_order_payload(dados, conn)
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO ordens (
                produto, quantidade, status, prioridade, valor_unitario,
                data_prevista, ordem_pai_id, criado_em, atualizado_em, concluido_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                payload['produto'], payload['quantidade'], payload['status'],
                payload['prioridade'], payload['valor_unitario'], payload['data_prevista'],
                payload['ordem_pai_id'], now_local_str(), payload['atualizado_em'],
                payload['concluido_em']
            )
        )
        conn.commit()
        ordem_id = cursor.lastrowid
    finally:
        conn.close()

    ordem = get_order_by_id(ordem_id)
    registrar_log_acao('criou_ordem', ordem_id, {
        'produto': payload['produto'],
        'prioridade': payload['prioridade'],
        'ordem_pai_id': payload['ordem_pai_id'],
    })
    disparar_webhooks('ordem_criada', ordem)
    return ordem


def update_order_status(ordem_id, dados):
    if not dados:
        raise ServiceError('Body ausente ou invalido.')
    novo_status = normalizar_status(dados.get('status'))
    if not novo_status:
        raise ServiceError('Campo status e obrigatorio.')
    if novo_status not in ALLOWED_STATUSES:
        raise ServiceError(f'Status invalido. Use: {list(ALLOWED_STATUSES)}')

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, status FROM ordens WHERE id = ?', (ordem_id,))
        atual = cursor.fetchone()
        if atual is None:
            raise ServiceError(f'Ordem {ordem_id} nao encontrada.', 404)

        cursor.execute(
            '''
            SELECT o.ordem_pai_id, p.status AS ordem_pai_status
            FROM ordens o
            LEFT JOIN ordens p ON p.id = o.ordem_pai_id
            WHERE o.id = ?
            ''',
            (ordem_id,)
        )
        dependencia = cursor.fetchone()
        if (
            dependencia['ordem_pai_id']
            and dependencia['ordem_pai_status'] != 'Concluida'
            and novo_status in ('Em andamento', 'Concluida')
        ):
            raise ServiceError(
                'Ordem filha bloqueada: conclua a ordem pai antes de iniciar.',
                409
            )

        concluido_em = now_local_str() if novo_status == 'Concluida' else None
        cursor.execute(
            '''
            UPDATE ordens
            SET status = ?, atualizado_em = ?, concluido_em = ?
            WHERE id = ?
            ''',
            (novo_status, now_local_str(), concluido_em, ordem_id)
        )
        conn.commit()
        status_anterior = atual['status']
    finally:
        conn.close()

    ordem = get_order_by_id(ordem_id)
    registrar_log_acao('atualizou_ordem', ordem_id, {
        'status_anterior': status_anterior,
        'status_novo': novo_status,
    })
    if status_anterior != 'Concluida' and novo_status == 'Concluida':
        disparar_webhooks('ordem_concluida', ordem)
    return ordem


def delete_order(ordem_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, produto FROM ordens WHERE id = ?', (ordem_id,))
        ordem = cursor.fetchone()
        if ordem is None:
            raise ServiceError(f'Ordem {ordem_id} nao encontrada.', 404)

        cursor.execute('SELECT COUNT(*) AS total FROM ordens WHERE ordem_pai_id = ?', (ordem_id,))
        if cursor.fetchone()['total'] > 0:
            raise ServiceError(
                'Nao e possivel excluir: existem ordens filhas vinculadas.',
                409
            )

        cursor.execute('DELETE FROM ordens WHERE id = ?', (ordem_id,))
        cursor.execute('SELECT COUNT(*) AS total FROM ordens')
        if cursor.fetchone()['total'] == 0:
            cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'ordens'")
        conn.commit()
        payload = {'id': ordem_id, 'produto': ordem['produto']}
    finally:
        conn.close()

    registrar_log_acao('removeu_ordem', ordem_id, payload)
    disparar_webhooks('ordem_deletada', payload)
    return {
        'mensagem': f"Ordem {ordem_id} ({payload['produto']}) removida.",
        'id_removido': ordem_id,
    }


def load_logs(limit=100):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT id, usuario, role, acao, ordem_id, detalhe, timestamp
            FROM log_acao
            ORDER BY id DESC
            LIMIT ?
            ''',
            (limit,)
        )
        logs = []
        for row in cursor.fetchall():
            item = dict(row)
            if item.get('detalhe'):
                try:
                    item['detalhe'] = json.loads(item['detalhe'])
                except (TypeError, ValueError, json.JSONDecodeError):
                    pass
            logs.append(item)
        return logs
    finally:
        conn.close()


def forecast_overview():
    conn = get_connection()
    try:
        estatisticas, media_global = carregar_estatisticas_producao(conn)
    finally:
        conn.close()

    produtos = [{
        'produto': produto,
        'media_horas': round(info['media_horas'], 2),
        'tempo_texto': formatar_duracao_horas(info['media_horas']),
        'amostras': info['amostras'],
        'media_quantidade': round(info['media_quantidade'], 2),
    } for produto, info in estatisticas.items()]
    produtos.sort(key=lambda item: item['media_horas'], reverse=True)
    return {
        'media_global_horas': round(media_global, 2),
        'produtos': produtos,
    }


def detect_bottlenecks():
    ordens = list_orders(order_by=priority_order_sql('o'))
    agrupado = defaultdict(lambda: {
        'produto': '',
        'ordens_ativas': 0,
        'ordens_em_risco': 0,
        'ordens_bloqueadas': 0,
        'horas_previstas': [],
    })
    for ordem in ordens:
        item = agrupado[ordem['produto']]
        item['produto'] = ordem['produto']
        if ordem['status'] != 'Concluida':
            item['ordens_ativas'] += 1
        if ordem.get('prazo_em_risco'):
            item['ordens_em_risco'] += 1
        if ordem.get('bloqueada_por_dependencia'):
            item['ordens_bloqueadas'] += 1
        item['horas_previstas'].append(float(ordem.get('tempo_previsto_producao_horas') or 0))

    gargalos = []
    for item in agrupado.values():
        media_horas = sum(item['horas_previstas']) / len(item['horas_previstas']) if item['horas_previstas'] else 0
        score = media_horas + (item['ordens_em_risco'] * 24) + (item['ordens_bloqueadas'] * 12)
        if score <= 0:
            continue
        gargalos.append({
            'produto': item['produto'],
            'ordens_ativas': item['ordens_ativas'],
            'ordens_em_risco': item['ordens_em_risco'],
            'ordens_bloqueadas': item['ordens_bloqueadas'],
            'media_horas_previstas': round(media_horas, 2),
            'score_gargalo': round(score, 2),
        })

    gargalos.sort(key=lambda item: item['score_gargalo'], reverse=True)
    return gargalos


def build_status_payload():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) AS total FROM ordens')
        total_ordens = cursor.fetchone()['total']
        cursor.execute('SELECT status, COUNT(*) AS total FROM ordens GROUP BY status')
        resumo = {row['status']: row['total'] for row in cursor.fetchall()}
    finally:
        conn.close()

    return {
        'status': 'online',
        'sistema': 'Sistema de Ordens de Producao',
        'versao': '3.0.0',
        'timestamp': now_local_str(),
        'total_ordens': total_ordens,
        'resumo_status': resumo,
        'banco': {'status': 'online', 'total_ordens': total_ordens},
    }


def _export_rows(ordens):
    return [[
        ordem['id'], ordem['produto'], ordem['quantidade'], ordem['status'],
        ordem['prioridade'], ordem.get('data_prevista') or '-',
        ordem.get('valor_unitario', 0), ordem.get('valor_total', 0),
        ordem.get('tempo_previsto_producao_texto', '-'),
        'Sim' if ordem.get('prazo_em_risco') else 'Nao',
        'Sim' if ordem.get('bloqueada_por_dependencia') else 'Nao',
    ] for ordem in ordens]


def export_orders_xlsx(ordens):
    try:
        from openpyxl import Workbook
    except ImportError as exc:
        raise ServiceError('Dependencia openpyxl nao instalada.', 500) from exc

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Ordens'
    sheet.append([
        'ID', 'Produto', 'Quantidade', 'Status', 'Prioridade',
        'Data prevista', 'Valor unitario (BRL)', 'Valor total (BRL)',
        'Tempo previsto', 'Prazo em risco', 'Bloqueada'
    ])
    for row in _export_rows(ordens):
        sheet.append(row)

    for col in ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K'):
        sheet.column_dimensions[col].width = 18
    sheet.column_dimensions['B'].width = 28

    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


def export_orders_pdf(ordens):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise ServiceError('Dependencia reportlab nao instalada.', 500) from exc

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    data = [[
        'ID', 'Produto', 'Qtd', 'Status', 'Prioridade',
        'Prevista', 'Valor Total', 'Tempo Previsto', 'Risco'
    ]]
    for ordem in ordens:
        data.append([
            str(ordem['id']), ordem['produto'], str(ordem['quantidade']),
            ordem['status'], ordem['prioridade'], ordem.get('data_prevista') or '-',
            f"R$ {ordem.get('valor_total', 0):.2f}",
            ordem.get('tempo_previsto_producao_texto', '-'),
            'Sim' if ordem.get('prazo_em_risco') else 'Nao'
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0c6ddf')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#8fb9df')),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fbff')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f8fbff'), colors.HexColor('#eef5fc')]),
    ]))

    doc.build([
        Paragraph('Relatorio de Ordens de Producao', styles['Title']),
        Spacer(1, 12),
        table,
    ])
    buffer.seek(0)
    return buffer
