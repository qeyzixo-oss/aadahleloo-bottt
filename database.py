import sqlite3
from config import DB_FILE


def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY,
            username      TEXT,
            wallet        TEXT DEFAULT NULL,
            spent_usdt    REAL DEFAULT 0,
            received_usdt REAL DEFAULT 0,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            asset      TEXT,
            amount     REAL,
            paid_ton   REAL,
            memo       TEXT,
            status     TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            text       TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


# ---------- USERS ----------

def get_user(user_id):
    conn = get_conn()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return user


def create_user(user_id, username):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
        (user_id, username)
    )
    conn.commit()
    conn.close()


def set_wallet(user_id, wallet):
    conn = get_conn()
    conn.execute("UPDATE users SET wallet = ? WHERE user_id = ?", (wallet, user_id))
    conn.commit()
    conn.close()


def get_wallet(user_id):
    conn = get_conn()
    row = conn.execute("SELECT wallet FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row["wallet"] if row else None


# ---------- TRANSACTIONS ----------

def create_transaction(user_id, asset, amount, paid_ton, memo):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO transactions (user_id, asset, amount, paid_ton, memo) VALUES (?, ?, ?, ?, ?)",
        (user_id, asset, amount, paid_ton, memo)
    )
    tx_id = c.lastrowid
    conn.commit()
    conn.close()
    return tx_id


def get_transaction(tx_id):
    conn = get_conn()
    tx = conn.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()
    conn.close()
    return tx


def approve_transaction(tx_id):
    conn = get_conn()
    tx = conn.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()
    if tx:
        conn.execute("UPDATE transactions SET status = 'approved' WHERE id = ?", (tx_id,))
        conn.execute(
            "UPDATE users SET spent_usdt = spent_usdt + ?, received_usdt = received_usdt + ? WHERE user_id = ?",
            (tx["paid_ton"], tx["amount"], tx["user_id"])
        )
    conn.commit()
    conn.close()
    return tx


def reject_transaction(tx_id):
    conn = get_conn()
    tx = conn.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()
    if tx:
        conn.execute("UPDATE transactions SET status = 'rejected' WHERE id = ?", (tx_id,))
    conn.commit()
    conn.close()
    return tx


def get_user_history(user_id, limit=10):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return rows


# ---------- NOTIFICATIONS ----------

def add_notification(text):
    conn = get_conn()
    conn.execute("INSERT INTO notifications (text) VALUES (?)", (text,))
    conn.commit()
    conn.close()


def get_notifications(limit=5):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM notifications ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return rows


def get_all_user_ids():
    conn = get_conn()
    rows = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    return [r["user_id"] for r in rows]
