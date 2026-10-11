"""Local-only API consumed by the embedded DietDisk interface."""
from __future__ import annotations
import json
import threading
from pathlib import Path
from typing import Any

import psutil
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import APP_DATA_DIR, DATABASE_PATH, DEFAULT_DRIVES, REPORTS_DIR
from .database import connect, create_scan
from .scanner import scan_roots

app = FastAPI(title="DietDisk Local API", docs_url=None, redoc_url=None)
_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/frontend", StaticFiles(directory=str(_FRONTEND_DIR)), name="frontend")


@app.get("/")
def home():
    return FileResponse(_FRONTEND_DIR / "index.html", media_type="text/html")
_state_lock = threading.Lock()
_scan_thread: threading.Thread | None = None
_stop_event = threading.Event()
_current: dict[str, Any] = {"status": "idle", "scan_id": None, "files_scanned": 0,
                            "folders_scanned": 0, "bytes_scanned": 0, "errors_count": 0,
                            "exclusions_count": 0, "current_path": ""}


class ScanRequest(BaseModel):
    roots: list[str] = Field(default_factory=lambda: DEFAULT_DRIVES, min_length=1, max_length=8)


def _update_progress(data: dict) -> None:
    with _state_lock:
        _current.update(data)


def _run_scan(scan_id: int, roots: list[str]) -> None:
    global _current
    try:
        result = scan_roots(scan_id, roots, str(DATABASE_PATH), _stop_event, _update_progress)
        with _state_lock:
            _current.update(result)
            _current["current_path"] = ""
    except Exception as exc:
        with _state_lock:
            _current.update({"status": "failed", "message": str(exc), "current_path": ""})


def _valid_roots(roots: list[str]) -> list[str]:
    cleaned = []
    for raw in roots:
        path = str(Path(raw))
        # Only drive roots are accepted in Phase 1, avoiding arbitrary path submission.
        if len(path) < 2 or path[1] != ":" or path[0].upper() not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            raise HTTPException(status_code=400, detail=f"Invalid drive root: {raw}")
        root = path[:2].upper() + "\\"
        if root not in cleaned:
            cleaned.append(root)
    return cleaned


@app.get("/api/health")
def health():
    return {"app": "DietDisk", "status": "ok", "mode": "read-only inventory"}


@app.get("/api/drives")
def drives():
    items = []
    for part in psutil.disk_partitions(all=False):
        if not part.device or not part.device[0].isalpha():
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
            items.append({"device": part.device, "mountpoint": part.mountpoint,
                          "filesystem": part.fstype, "total_bytes": usage.total,
                          "used_bytes": usage.used, "free_bytes": usage.free,
                          "percent": usage.percent})
        except OSError:
            items.append({"device": part.device, "mountpoint": part.mountpoint,
                          "filesystem": part.fstype, "total_bytes": 0, "used_bytes": 0,
                          "free_bytes": 0, "percent": 0})
    return {"drives": items}


@app.post("/api/scan/start")
def start_scan(request: ScanRequest):
    global _scan_thread, _stop_event, _current
    roots = _valid_roots(request.roots)
    with _state_lock:
        if _scan_thread is not None and _scan_thread.is_alive():
            raise HTTPException(status_code=409, detail="A scan is already running.")
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        conn = connect()
        scan_id = create_scan(conn, roots)
        conn.close()
        _stop_event = threading.Event()
        _current = {"status": "running", "scan_id": scan_id, "files_scanned": 0,
                    "folders_scanned": 0, "bytes_scanned": 0, "errors_count": 0,
                    "exclusions_count": 0, "current_path": "", "roots": roots}
        _scan_thread = threading.Thread(target=_run_scan, args=(scan_id, roots), daemon=True)
        _scan_thread.start()
    return {"scan_id": scan_id, "status": "running", "roots": roots}


@app.post("/api/scan/cancel")
def cancel_scan():
    with _state_lock:
        if _current.get("status") != "running":
            return {"status": _current.get("status", "idle"), "message": "No active scan."}
        _stop_event.set()
    return {"status": "cancelling", "message": "Cancellation requested; the scanner will stop at its next safe checkpoint."}


@app.get("/api/scan/status")
def scan_status():
    with _state_lock:
        return dict(_current)


@app.get("/api/scans")
def scans(limit: int = Query(default=20, ge=1, le=100)):
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM scans ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return {"scans": [dict(row) for row in rows]}
    finally:
        conn.close()


@app.get("/api/files")
def files(scan_id: int | None = None, search: str = "", classification: str = "", sort: str = "size", order: str = "desc", limit: int = Query(200, ge=1, le=2000), offset: int = Query(0, ge=0)):
    conn = connect()
    try:
        if scan_id is None:
            row = conn.execute("SELECT id FROM scans WHERE status IN ('completed','cancelled') ORDER BY id DESC LIMIT 1").fetchone()
            if not row:
                return {"files": [], "total": 0, "scan_id": None}
            scan_id = int(row[0])
        clauses = ["scan_id=?"]
        params: list[Any] = [scan_id]
        if search.strip():
            clauses.append("(path LIKE ? OR name LIKE ?)")
            pattern = f"%{search.strip()}%"
            params.extend([pattern, pattern])
        if classification:
            clauses.append("classification=?")
            params.append(classification)
        where = " AND ".join(clauses)
        order_by = {"size": "size_bytes", "name": "name COLLATE NOCASE", "modified": "modified_at", "path": "path COLLATE NOCASE"}.get(sort, "size_bytes")
        direction = "ASC" if order.lower() == "asc" else "DESC"
        total = conn.execute(f"SELECT COUNT(*) FROM files WHERE {where}", params).fetchone()[0]
        rows = conn.execute(f"SELECT * FROM files WHERE {where} ORDER BY {order_by} {direction} LIMIT ? OFFSET ?", (*params, limit, offset)).fetchall()
        return {"files": [dict(row) for row in rows], "total": total, "scan_id": scan_id}
    finally:
        conn.close()


@app.get("/api/folders")
def folders(scan_id: int | None = None, limit: int = Query(200, ge=1, le=2000), offset: int = Query(0, ge=0)):
    conn = connect()
    try:
        if scan_id is None:
            row = conn.execute("SELECT id FROM scans WHERE status IN ('completed','cancelled') ORDER BY id DESC LIMIT 1").fetchone()
            if not row:
                return {"folders": [], "total": 0, "scan_id": None}
            scan_id = int(row[0])
        total = conn.execute("SELECT COUNT(*) FROM folders WHERE scan_id=?", (scan_id,)).fetchone()[0]
        rows = conn.execute("SELECT * FROM folders WHERE scan_id=? ORDER BY total_bytes DESC LIMIT ? OFFSET ?", (scan_id, limit, offset)).fetchall()
        return {"folders": [dict(row) for row in rows], "total": total, "scan_id": scan_id}
    finally:
        conn.close()


@app.get("/api/issues")
def issues(scan_id: int | None = None, issue_type: str = "", limit: int = Query(500, ge=1, le=5000), offset: int = Query(0, ge=0)):
    conn = connect()
    try:
        if scan_id is None:
            row = conn.execute("SELECT id FROM scans ORDER BY id DESC LIMIT 1").fetchone()
            if not row:
                return {"issues": [], "total": 0}
            scan_id = int(row[0])
        clauses = ["scan_id=?"]
        params: list[Any] = [scan_id]
        if issue_type:
            clauses.append("issue_type=?"); params.append(issue_type)
        where = " AND ".join(clauses)
        total = conn.execute(f"SELECT COUNT(*) FROM scan_issues WHERE {where}", params).fetchone()[0]
        rows = conn.execute(f"SELECT * FROM scan_issues WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?", (*params, limit, offset)).fetchall()
        return {"issues": [dict(row) for row in rows], "total": total, "scan_id": scan_id}
    finally:
        conn.close()


@app.get("/api/summary")
def summary(scan_id: int | None = None):
    conn = connect()
    try:
        if scan_id is None:
            row = conn.execute("SELECT id FROM scans WHERE status IN ('completed','cancelled','failed') ORDER BY id DESC LIMIT 1").fetchone()
            if not row:
                return {"scan": None, "categories": [], "largest_files": [], "largest_folders": []}
            scan_id = int(row[0])
        scan = conn.execute("SELECT * FROM scans WHERE id=?", (scan_id,)).fetchone()
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        categories = conn.execute("SELECT classification,COUNT(*) AS file_count,SUM(size_bytes) AS bytes FROM files WHERE scan_id=? GROUP BY classification ORDER BY bytes DESC", (scan_id,)).fetchall()
        largest_files = conn.execute("SELECT path,name,size_bytes,classification FROM files WHERE scan_id=? ORDER BY size_bytes DESC LIMIT 10", (scan_id,)).fetchall()
        largest_folders = conn.execute("SELECT path,total_bytes,file_count FROM folders WHERE scan_id=? ORDER BY total_bytes DESC LIMIT 10", (scan_id,)).fetchall()
        return {"scan": dict(scan), "categories": [dict(r) for r in categories],
                "largest_files": [dict(r) for r in largest_files],
                "largest_folders": [dict(r) for r in largest_folders]}
    finally:
        conn.close()


@app.get("/api/export/csv")
def export_csv(scan_id: int | None = None):
    """Export the latest scan's file inventory to a CSV in app-data reports."""
    import csv
    from fastapi.responses import FileResponse
    conn = connect()
    try:
        if scan_id is None:
            row = conn.execute("SELECT id FROM scans ORDER BY id DESC LIMIT 1").fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="No scan available to export")
            scan_id = int(row[0])
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out = REPORTS_DIR / f"DietDisk_scan_{scan_id}_files.csv"
        rows = conn.execute("SELECT path,parent_path,name,extension,size_bytes,modified_at,classification,reason FROM files WHERE scan_id=? ORDER BY size_bytes DESC", (scan_id,)).fetchall()
        with out.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["Path", "ParentPath", "Name", "Extension", "SizeBytes", "ModifiedUTC", "Classification", "Reason"])
            writer.writerows([tuple(r) for r in rows])
        return FileResponse(out, filename=out.name, media_type="text/csv")
    finally:
        conn.close()
