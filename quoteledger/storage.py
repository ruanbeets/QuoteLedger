"""SQLite persistence. Keep SQL out of the HTTP and calculation layers."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "instance" / "quoteledger.sqlite3"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path=DB_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            specification TEXT NOT NULL DEFAULT '',
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS quotes (
            id INTEGER PRIMARY KEY,
            request_id INTEGER NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
            filename TEXT NOT NULL DEFAULT '',
            original_text TEXT NOT NULL DEFAULT '',
            original_pdf BLOB,
            fields_json TEXT NOT NULL,
            evidence_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'needs_review',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)
    return db


def request_dict(row):
    return dict(row)


def quote_dict(row):
    result = dict(row)
    result["fields"] = json.loads(result.pop("fields_json"))
    result["evidence"] = json.loads(result.pop("evidence_json"))
    result.pop("original_pdf", None)
    return result


def list_requests(db):
    return [request_dict(r) for r in db.execute("SELECT * FROM requests ORDER BY created_at DESC, id DESC")]


def get_request(db, request_id):
    row = db.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
    return request_dict(row) if row else None


def create_request(db, name, specification, quantity):
    cur = db.execute("INSERT INTO requests(name,specification,quantity,created_at) VALUES(?,?,?,?)",
                     (name, specification, quantity, now()))
    db.commit()
    return get_request(db, cur.lastrowid)


def list_quotes(db, request_id):
    rows = db.execute("SELECT * FROM quotes WHERE request_id=? ORDER BY id", (request_id,))
    return [quote_dict(r) for r in rows]


def get_quote(db, quote_id):
    row = db.execute("SELECT * FROM quotes WHERE id=?", (quote_id,)).fetchone()
    return quote_dict(row) if row else None


def get_pdf(db, quote_id):
    row = db.execute("SELECT original_pdf FROM quotes WHERE id=?", (quote_id,)).fetchone()
    return row[0] if row else None


def create_quote(db, request_id, filename, original_text, pdf, fields, evidence):
    stamp = now()
    cur = db.execute("""INSERT INTO quotes
        (request_id,filename,original_text,original_pdf,fields_json,evidence_json,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?)""",
        (request_id, filename, original_text, pdf, json.dumps(fields), json.dumps(evidence), stamp, stamp))
    db.commit()
    return get_quote(db, cur.lastrowid)


def update_quote(db, quote_id, fields, status):
    db.execute("UPDATE quotes SET fields_json=?,status=?,updated_at=? WHERE id=?",
               (json.dumps(fields), status, now(), quote_id))
    db.commit()
    return get_quote(db, quote_id)
