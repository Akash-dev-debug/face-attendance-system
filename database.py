import sqlite3
from datetime import datetime

DB_PATH = "attendance.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            reg_no TEXT UNIQUE NOT NULL,
            department TEXT,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            confidence REAL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    conn.commit()
    conn.close()


def add_user(name, reg_no, department):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (name, reg_no, department, created_at) VALUES (?, ?, ?, ?)",
        (name, reg_no, department, datetime.now().isoformat()),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return user_id


def get_all_users():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM users ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user(user_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_user(user_id):
    conn = get_connection()
    conn.execute("DELETE FROM attendance WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def clear_all():
    conn = get_connection()
    conn.execute("DELETE FROM attendance")
    conn.execute("DELETE FROM users")
    conn.commit()
    conn.close()


def has_marked_today(user_id, date_str):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM attendance WHERE user_id = ? AND date = ?",
        (user_id, date_str),
    ).fetchone()
    conn.close()
    return row is not None


def mark_attendance(user_id, date_str, time_str, confidence):
    conn = get_connection()
    conn.execute(
        "INSERT INTO attendance (user_id, date, time, confidence) VALUES (?, ?, ?, ?)",
        (user_id, date_str, time_str, confidence),
    )
    conn.commit()
    conn.close()


def get_records(date_filter=None, search=None):
    conn = get_connection()
    query = """
        SELECT attendance.id, users.name, users.reg_no, users.department,
               attendance.date, attendance.time, attendance.confidence
        FROM attendance
        JOIN users ON users.id = attendance.user_id
        WHERE 1=1
    """
    params = []
    if date_filter:
        query += " AND attendance.date = ?"
        params.append(date_filter)
    if search:
        query += " AND (users.name LIKE ? OR users.reg_no LIKE ?)"
        params.append(f"%{search}%")
        params.append(f"%{search}%")
    query += " ORDER BY attendance.date DESC, attendance.time DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_dashboard_stats():
    conn = get_connection()
    total_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    today = datetime.now().strftime("%Y-%m-%d")
    present_today = conn.execute("""
        SELECT COUNT(DISTINCT attendance.user_id) AS c
        FROM attendance
        JOIN users ON users.id = attendance.user_id
        WHERE attendance.date = ?
    """, (today,)).fetchone()["c"]
    last_7_days = conn.execute("""
        SELECT date, COUNT(DISTINCT user_id) AS count
        FROM attendance
        WHERE date >= date('now', '-6 days')
        GROUP BY date
        ORDER BY date
    """).fetchall()
    conn.close()
    return {
        "total_users": total_users,
        "present_today": present_today,
        "absent_today": max(total_users - present_today, 0),
        "last_7_days": [dict(r) for r in last_7_days],
    }