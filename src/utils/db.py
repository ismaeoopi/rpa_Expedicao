import sqlite3
import os
import sys
from datetime import datetime

def get_db_path():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, 'estado_estoque.db')

def get_connection():
    return sqlite3.connect(get_db_path(), isolation_level=None)

def inicializar_banco():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lote (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                caminho_excel TEXT NOT NULL,
                data_inicio TEXT NOT NULL,
                status TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS item (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lote_id INTEGER,
                material TEXT,
                peso REAL,
                op TEXT,
                inbound TEXT,
                status_etapa TEXT,
                FOREIGN KEY (lote_id) REFERENCES lote(id)
            )
        ''')

def criar_novo_lote(caminho_excel):
    inicializar_banco()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO lote (caminho_excel, data_inicio, status) VALUES (?, ?, ?)",
            (caminho_excel, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'EM_ANDAMENTO')
        )
        return cursor.lastrowid

def inserir_item(lote_id, material, peso):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO item (lote_id, material, peso, status_etapa) VALUES (?, ?, ?, ?)",
            (lote_id, material, peso, 'PENDENTE')
        )
        return cursor.lastrowid

def atualizar_item(item_id, op=None, inbound=None, status_etapa=None):
    query = "UPDATE item SET "
    params = []
    if op is not None:
        query += "op = ?, "
        params.append(op)
    if inbound is not None:
        query += "inbound = ?, "
        params.append(inbound)
    if status_etapa is not None:
        query += "status_etapa = ?, "
        params.append(status_etapa)
    
    if not params:
        return
        
    query = query.rstrip(', ') + " WHERE id = ?"
    params.append(item_id)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))

def concluir_lote(lote_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE lote SET status = 'CONCLUIDO' WHERE id = ?", (lote_id,))

def buscar_lote_pendente():
    inicializar_banco()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, caminho_excel FROM lote WHERE status = 'EM_ANDAMENTO' ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            lote_id, caminho_excel = row
            cursor.execute("SELECT id, material, peso, op, inbound, status_etapa FROM item WHERE lote_id = ?", (lote_id,))
            itens = cursor.fetchall()
            return {"lote_id": lote_id, "caminho_excel": caminho_excel, "itens": [
                {"id": r[0], "material": r[1], "peso": r[2], "op": r[3], "inbound": r[4], "status_etapa": r[5]} for r in itens
            ]}
    return None

def cancelar_lote_pendente():
    inicializar_banco()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE lote SET status = 'CANCELADO' WHERE status = 'EM_ANDAMENTO'")
