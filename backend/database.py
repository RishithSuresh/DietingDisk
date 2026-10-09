"""SQLite persistence for scans, files, folders, and scan issues."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from .config import DATABASE_PATH

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    roots_json TEXT NOT NULL,
    files_scanned INTEGER NOT NULL DEFAULT 0,
    folders_scanned INTEGER NOT NULL DEFAULT 0,
    bytes_scanned INTEGER NOT NULL DEFAULT 0,
    errors_count INTEGER NOT NULL DEFAULT 0,
    exclusions_count INTEGER NOT NULL DEFAULT 0,
    message TEXT
);
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER NOT NULL,
    path TEXT NOT NULL,
    parent_path TEXT NOT NULL,
    name TEXT NOT NULL,
    extension TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    modified_at TEXT,
    classification TEXT NOT NULL,
    reason TEXT NOT NULL,
    FOREIGN KEY(scan_id) REFERENCES scans(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_files_scan_size ON files(scan_id, size_bytes DESC);
CREATE INDEX IF NOT EXISTS idx_files_scan_class ON files(scan_id, classification);
CREATE INDEX IF NOT EXISTS idx_files_scan_path ON files(scan_id, path);
CREATE TABLE IF NOT EXISTS folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER NOT NULL,
    path TEXT NOT NULL,
    parent_path TEXT,
    name TEXT NOT NULL,
    total_bytes INTEGER NOT NULL DEFAULT 0,
    direct_bytes INTEGER NOT NULL DEFAULT 0,
    file_count INTEGER NOT NULL DEFAULT 0,
    child_folder_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(scan_id) REFERENCES scans(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_folders_scan_size ON folders(scan_id, total_bytes DESC);
CREATE INDEX IF NOT EXISTS idx_folders_scan_path ON folders(scan_id, path);
CREATE TABLE IF NOT EXISTS scan_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER NOT NULL,
    path TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    message TEXT NOT NULL,
    FOREIGN KEY(scan_id) REFERENCES scans(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_issues_scan ON scan_issues(scan_id);
"""


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path or DATABASE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    conn.executescript(SCHEMA)
    return conn


def create_scan(conn: sqlite3.Connection, roots: list[str]) -> int:
    from datetime import datetime, timezone
    import json
    cur = conn.execute(
        "INSERT INTO scans(started_at,status,roots_json) VALUES(?,?,?)",
        (datetime.now(timezone.utc).isoformat(), "running", json.dumps(roots)),
    )
    conn.commit()
    return int(cur.lastrowid)
