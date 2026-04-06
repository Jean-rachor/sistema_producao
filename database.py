import os
import sqlite3

from werkzeug.security import generate_password_hash


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'ordens.db')

DEFAULT_USERS = (
    ('admin', 'admin123', 'admin'),
    ('operador', 'operador123', 'operador'),
    ('visualizador', 'visualizador123', 'visualizador'),
)

ORDER_COLUMNS = {
    'prioridade': "TEXT NOT NULL DEFAULT 'Media'",
    'valor_unitario': 'REAL NOT NULL DEFAULT 0',
    'data_prevista': 'TEXT',
    'ordem_pai_id': 'INTEGER',
    'atualizado_em': 'TEXT',
    'concluido_em': 'TEXT',
}


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def _table_columns(cursor, table_name):
    cursor.execute(f'PRAGMA table_info({table_name})')
    return {row[1] for row in cursor.fetchall()}


def _ensure_column(cursor, table_name, column_name, definition):
    columns = _table_columns(cursor, table_name)
    if column_name not in columns:
        cursor.execute(
            f'ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}'
        )


def _ensure_indexes(cursor):
    cursor.execute(
        'CREATE INDEX IF NOT EXISTS idx_ordens_status ON ordens(status)'
    )
    cursor.execute(
        'CREATE INDEX IF NOT EXISTS idx_ordens_prioridade ON ordens(prioridade)'
    )
    cursor.execute(
        'CREATE INDEX IF NOT EXISTS idx_ordens_produto ON ordens(produto)'
    )
    cursor.execute(
        'CREATE INDEX IF NOT EXISTS idx_ordens_pai ON ordens(ordem_pai_id)'
    )
    cursor.execute(
        'CREATE INDEX IF NOT EXISTS idx_logs_ordem ON log_acao(ordem_id)'
    )
    cursor.execute(
        'CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON log_acao(timestamp)'
    )


def _seed_default_users(cursor):
    for username, password, role in DEFAULT_USERS:
        cursor.execute(
            '''
            INSERT OR IGNORE INTO usuarios (username, senha_hash, role)
            VALUES (?, ?, ?)
            ''',
            (username, generate_password_hash(password), role)
        )


def init_db():
    print('Inicializando banco de dados...')
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS ordens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            status TEXT DEFAULT 'Pendente',
            prioridade TEXT NOT NULL DEFAULT 'Media',
            valor_unitario REAL NOT NULL DEFAULT 0,
            data_prevista TEXT,
            ordem_pai_id INTEGER,
            criado_em TEXT DEFAULT (datetime('now', 'localtime')),
            atualizado_em TEXT DEFAULT (datetime('now', 'localtime')),
            concluido_em TEXT,
            FOREIGN KEY (ordem_pai_id) REFERENCES ordens (id)
        )
        '''
    )

    for column_name, definition in ORDER_COLUMNS.items():
        _ensure_column(cursor, 'ordens', column_name, definition)

    cursor.execute(
        '''
        UPDATE ordens
        SET prioridade = COALESCE(NULLIF(prioridade, ''), 'Media')
        '''
    )
    cursor.execute(
        '''
        UPDATE ordens
        SET valor_unitario = COALESCE(valor_unitario, 0)
        '''
    )
    cursor.execute(
        '''
        UPDATE ordens
        SET atualizado_em = COALESCE(atualizado_em, criado_em)
        '''
    )
    cursor.execute(
        '''
        UPDATE ordens
        SET concluido_em = CASE
            WHEN status = 'Concluida' AND concluido_em IS NULL THEN atualizado_em
            ELSE concluido_em
        END
        '''
    )

    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            criado_em TEXT DEFAULT (datetime('now', 'localtime'))
        )
        '''
    )

    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS log_acao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            role TEXT,
            acao TEXT NOT NULL,
            ordem_id INTEGER,
            detalhe TEXT,
            timestamp TEXT DEFAULT (datetime('now', 'localtime'))
        )
        '''
    )

    _seed_default_users(cursor)
    _ensure_indexes(cursor)

    conn.commit()
    conn.close()

    print('Banco de dados pronto.')
