import sqlite3

NOME_BANCO = "ordens.db"

def get_connection():
    conn = sqlite3.connect(NOME_BANCO)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # IF NOT EXISTS garante que o comando não falha se a tabela já existir
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

# 👇 chama a função
init_db()