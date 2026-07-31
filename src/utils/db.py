import sqlite3
import os
import sys
from datetime import datetime

def get_db_path():
    # Use standard AppData folder for Windows to guarantee write access
    appdata = os.environ.get('APPDATA')
    if appdata:
        base_dir = os.path.join(appdata, 'RPA_Expedicao')
    else:
        # Fallback to user home directory
        base_dir = os.path.expanduser('~/.rpa_expedicao')
    
    os.makedirs(base_dir, exist_ok=True)
    new_db_path = os.path.join(base_dir, 'estado_estoque.db')
    
    # Check if an old database exists in the project root to migrate it
    if getattr(sys, 'frozen', False):
        old_base_dir = os.path.dirname(sys.executable)
    else:
        old_base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    old_db_path = os.path.join(old_base_dir, 'estado_estoque.db')
    
    if os.path.exists(old_db_path) and not os.path.exists(new_db_path):
        try:
            import shutil
            shutil.copy2(old_db_path, new_db_path)
        except Exception:
            pass # Fail silently and create a clean database if we can't copy
            
    return new_db_path


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
                inbound_gerada TEXT,
                status_etapa TEXT,
                FOREIGN KEY (lote_id) REFERENCES lote(id)
            )
        ''')
        # Adiciona a coluna inbound_gerada dinamicamente caso a tabela já exista sem ela
        cursor.execute("PRAGMA table_info(item)")
        colunas = [info[1] for info in cursor.fetchall()]
        if "inbound_gerada" not in colunas:
            cursor.execute("ALTER TABLE item ADD COLUMN inbound_gerada TEXT")
        if "tempo" not in colunas:
            cursor.execute("ALTER TABLE item ADD COLUMN tempo TEXT")
            
        # Tabela de multiplicadores para itens não-KG
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS multiplicador (
                material TEXT PRIMARY KEY,
                multiplo REAL NOT NULL
            )
        ''')
        cursor.execute("SELECT COUNT(*) FROM multiplicador")
        if cursor.fetchone()[0] == 0:
            valores_padrao = [
                ("HA2200", 27.8),
                ("HA2192", 69.32),
                ("HA2198", 29.06),
                ("HA2310", 30.0),
                ("HA2203", 26.8),
                ("HA2311", 32.15),
                ("HA2312", 27.4),
                ("HA2201", 28.15),
                ("HA2309", 31.25),
                ("HA2596", 24.475),
                ("HA2595", 27.24),
                ("HA2597", 30.36),
                ("HA2598", 28.4)
            ]
            cursor.executemany("INSERT INTO multiplicador (material, multiplo) VALUES (?, ?)", valores_padrao)

def obter_multiplicadores():
    inicializar_banco()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT material, multiplo FROM multiplicador ORDER BY material")
        rows = cursor.fetchall()
        return [{"material": r[0], "multiplo": r[1]} for r in rows]

def obter_multiplicador_por_material(material):
    inicializar_banco()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT multiplo FROM multiplicador WHERE material = ?", (material,))
        row = cursor.fetchone()
        return row[0] if row else None

def salvar_multiplicador(material, multiplo):
    inicializar_banco()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO multiplicador (material, multiplo) VALUES (?, ?) ON CONFLICT(material) DO UPDATE SET multiplo=excluded.multiplo",
            (material, multiplo)
        )

def deletar_multiplicador(material):
    inicializar_banco()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM multiplicador WHERE material = ?", (material,))

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

def atualizar_item(item_id, op=None, inbound=None, inbound_gerada=None, status_etapa=None, material=None, peso=None, tempo=None):
    query = "UPDATE item SET "
    params = []
    if op is not None:
        query += "op = ?, "
        params.append(op)
    if inbound is not None:
        query += "inbound = ?, "
        params.append(inbound)
    if inbound_gerada is not None:
        query += "inbound_gerada = ?, "
        params.append(inbound_gerada)
    if status_etapa is not None:
        query += "status_etapa = ?, "
        params.append(status_etapa)
    if material is not None:
        query += "material = ?, "
        params.append(material)
    if peso is not None:
        query += "peso = ?, "
        params.append(peso)
    if tempo is not None:
        query += "tempo = ?, "
        params.append(tempo)
    
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
            cursor.execute("SELECT id, material, peso, op, inbound, status_etapa, inbound_gerada, tempo FROM item WHERE lote_id = ?", (lote_id,))
            itens = cursor.fetchall()
            return {"lote_id": lote_id, "caminho_excel": caminho_excel, "itens": [
                {"id": r[0], "material": r[1], "peso": r[2], "op": r[3], "inbound": r[4], "status_etapa": r[5], "inbound_gerada": r[6], "tempo": r[7]} for r in itens
            ]}
    return None

def cancelar_lote_pendente():
    inicializar_banco()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE lote SET status = 'CANCELADO' WHERE status = 'EM_ANDAMENTO'")

def buscar_itens_por_lote(lote_id):
    inicializar_banco()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, material, peso, op, inbound, status_etapa, inbound_gerada, tempo FROM item WHERE lote_id = ?", (lote_id,))
        itens = cursor.fetchall()
        return [
            {"id": r[0], "material": r[1], "peso": r[2], "op": r[3], "inbound": r[4], "status_etapa": r[5], "inbound_gerada": r[6], "tempo": r[7]} for r in itens
        ]

def buscar_ultimo_lote():
    inicializar_banco()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, caminho_excel, status FROM lote ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            lote_id, caminho_excel, status = row
            cursor.execute("SELECT id, material, peso, op, inbound, status_etapa, inbound_gerada, tempo FROM item WHERE lote_id = ?", (lote_id,))
            itens = cursor.fetchall()
            return {"lote_id": lote_id, "caminho_excel": caminho_excel, "status": status, "itens": [
                {"id": r[0], "material": r[1], "peso": r[2], "op": r[3], "inbound": r[4], "status_etapa": r[5], "inbound_gerada": r[6], "tempo": r[7]} for r in itens
            ]}
    return None
