import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'ordens.db')

print("🔥 CAMINHO REAL DO BANCO:", DB_PATH)

def get_connection():
    print("👉 Conectando em:", DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ordens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        produto TEXT NOT NULL,
        quantidade INTEGER NOT NULL,
        status TEXT DEFAULT 'Pendente',
        criado_em TEXT DEFAULT (datetime('now', 'localtime'))
    )
    ''')

    conn.commit()
    conn.close()

    print("Banco de dados inicializado com sucesso.")