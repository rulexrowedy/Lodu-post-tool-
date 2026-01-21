import psycopg2
import os

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_connection():
    return psycopg2.connect(DATABASE_URL)

def create_tables():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            status TEXT,
            comment_count INTEGER
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

def create_session(sid, status, count):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('INSERT INTO sessions (id, status, comment_count) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING', (sid, status, count))
    conn.commit()
    cur.close()
    conn.close()

def update_session(sid, count):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('UPDATE sessions SET comment_count = %s WHERE id = %s', (count, sid))
    conn.commit()
    cur.close()
    conn.close()
