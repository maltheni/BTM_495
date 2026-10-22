"""Database service: SQLite file created from schema.sql."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("spinelli_kia.db")
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(path=DB_PATH):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path=DB_PATH):
    """Create all tables (safe to run more than once)."""
    with connect(path) as conn:
        conn.executescript(SCHEMA_PATH.read_text())
    return path
