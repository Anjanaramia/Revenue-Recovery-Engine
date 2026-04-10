"""
client_manager.py
SQLite-backed multi-client (realtor) management for the CRM Lead Reactivation Engine.
"""

import sqlite3
import json
import os
import pandas as pd
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clients.db")


# ── Database Initialization ─────────────────────────────────────────────────────

def init_db(db_path: str = DB_PATH):
    """Create tables if they don't exist."""
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT UNIQUE NOT NULL,
            email       TEXT,
            phone       TEXT,
            agency      TEXT,
            created_at  TEXT DEFAULT (datetime('now')),
            updated_at  TEXT DEFAULT (datetime('now'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS client_runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id       INTEGER NOT NULL,
            run_date        TEXT NOT NULL,
            total_leads     INTEGER,
            hot_count       INTEGER,
            warm_count      INTEGER,
            cold_count      INTEGER,
            dormant_count   INTEGER,
            quality_score   INTEGER,
            notes           TEXT,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS monthly_tracking (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id           INTEGER NOT NULL,
            year_month          TEXT NOT NULL,
            outreach_sent       INTEGER DEFAULT 0,
            responses_received  INTEGER DEFAULT 0,
            notes               TEXT,
            updated_at          TEXT DEFAULT (datetime('now')),
            UNIQUE(client_id, year_month),
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
    """)

    con.commit()
    con.close()


# ── Client CRUD ─────────────────────────────────────────────────────────────────

def get_all_clients(db_path: str = DB_PATH) -> list[dict]:
    init_db(db_path)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT * FROM clients ORDER BY name").fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_client_names(db_path: str = DB_PATH) -> list[str]:
    return [c["name"] for c in get_all_clients(db_path)]


def add_client(name: str, email: str = "", phone: str = "", agency: str = "",
               db_path: str = DB_PATH) -> int:
    """Add a new realtor client. Returns the new client ID."""
    init_db(db_path)
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO clients (name, email, phone, agency) VALUES (?, ?, ?, ?)",
        (name.strip(), email.strip(), phone.strip(), agency.strip())
    )
    con.commit()
    row = con.execute("SELECT id FROM clients WHERE name = ?", (name.strip(),)).fetchone()
    con.close()
    return row[0] if row else -1


def update_client(client_id: int, name: str = None, email: str = None,
                  phone: str = None, agency: str = None, db_path: str = DB_PATH):
    init_db(db_path)
    con = sqlite3.connect(db_path)
    fields = []
    values = []
    if name is not None:
        fields.append("name = ?"); values.append(name)
    if email is not None:
        fields.append("email = ?"); values.append(email)
    if phone is not None:
        fields.append("phone = ?"); values.append(phone)
    if agency is not None:
        fields.append("agency = ?"); values.append(agency)
    if fields:
        fields.append("updated_at = datetime('now')")
        values.append(client_id)
        con.execute(f"UPDATE clients SET {', '.join(fields)} WHERE id = ?", values)
        con.commit()
    con.close()


def delete_client(client_id: int, db_path: str = DB_PATH):
    init_db(db_path)
    con = sqlite3.connect(db_path)
    con.execute("DELETE FROM monthly_tracking WHERE client_id = ?", (client_id,))
    con.execute("DELETE FROM client_runs WHERE client_id = ?", (client_id,))
    con.execute("DELETE FROM clients WHERE id = ?", (client_id,))
    con.commit()
    con.close()


def get_client_by_name(name: str, db_path: str = DB_PATH) -> dict | None:
    init_db(db_path)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT * FROM clients WHERE name = ?", (name.strip(),)).fetchone()
    con.close()
    return dict(row) if row else None


# ── Run History ─────────────────────────────────────────────────────────────────

def record_run(client_id: int, revenue: dict, quality_score: int = 0,
               notes: str = "", db_path: str = DB_PATH):
    """Save a processing run summary to history."""
    init_db(db_path)
    con = sqlite3.connect(db_path)
    con.execute("""
        INSERT INTO client_runs
            (client_id, run_date, total_leads, hot_count, warm_count,
             cold_count, dormant_count, quality_score, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        client_id,
        datetime.now().isoformat(),
        revenue.get("total_leads", 0),
        revenue.get("hot_count", 0),
        revenue.get("warm_count", 0),
        revenue.get("cold_count", 0),
        revenue.get("dormant_count", 0),
        quality_score,
        notes,
    ))
    con.commit()
    con.close()


def get_client_runs(client_id: int, limit: int = 12, db_path: str = DB_PATH) -> list[dict]:
    init_db(db_path)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT * FROM client_runs WHERE client_id = ? ORDER BY run_date DESC LIMIT ?",
        (client_id, limit)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_last_run(client_id: int, db_path: str = DB_PATH) -> dict | None:
    runs = get_client_runs(client_id, limit=1)
    return runs[0] if runs else None


# ── Monthly Tracking ─────────────────────────────────────────────────────────────

def get_year_month(dt: date = None) -> str:
    """Return 'YYYY-MM' string."""
    if dt is None:
        dt = datetime.now().date()
    return dt.strftime("%Y-%m")


def upsert_monthly_tracking(client_id: int, year_month: str, outreach_sent: int = None,
                             responses_received: int = None, notes: str = None,
                             db_path: str = DB_PATH):
    init_db(db_path)
    con = sqlite3.connect(db_path)
    # Ensure row exists
    con.execute("""
        INSERT OR IGNORE INTO monthly_tracking (client_id, year_month)
        VALUES (?, ?)
    """, (client_id, year_month))

    fields = ["updated_at = datetime('now')"]
    values = []
    if outreach_sent is not None:
        fields.append("outreach_sent = ?"); values.append(outreach_sent)
    if responses_received is not None:
        fields.append("responses_received = ?"); values.append(responses_received)
    if notes is not None:
        fields.append("notes = ?"); values.append(notes)

    if fields:
        values.extend([client_id, year_month])
        con.execute(
            f"UPDATE monthly_tracking SET {', '.join(fields)} WHERE client_id = ? AND year_month = ?",
            values
        )
    con.commit()
    con.close()


def get_monthly_tracking(client_id: int, year_month: str = None,
                          db_path: str = DB_PATH) -> list[dict]:
    init_db(db_path)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    if year_month:
        rows = con.execute(
            "SELECT * FROM monthly_tracking WHERE client_id = ? AND year_month = ?",
            (client_id, year_month)
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT * FROM monthly_tracking WHERE client_id = ? ORDER BY year_month DESC",
            (client_id,)
        ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_or_create_monthly(client_id: int, year_month: str = None,
                           db_path: str = DB_PATH) -> dict:
    if year_month is None:
        year_month = get_year_month()
    upsert_monthly_tracking(client_id, year_month, db_path=db_path)
    rows = get_monthly_tracking(client_id, year_month, db_path)
    return rows[0] if rows else {}


# ── Client Dashboard Summary ────────────────────────────────────────────────────

def get_client_summary(client_id: int, db_path: str = DB_PATH) -> dict:
    """Build a summary dict for the client dashboard."""
    client_rows = get_all_clients(db_path)
    client = next((c for c in client_rows if c["id"] == client_id), None)
    if not client:
        return {}

    last_run = get_last_run(client_id, db_path)
    runs = get_client_runs(client_id, limit=6, db_path=db_path)
    monthly = get_or_create_monthly(client_id, db_path=db_path)

    return {
        "client": client,
        "last_run": last_run,
        "history": runs,
        "current_month": monthly,
    }
