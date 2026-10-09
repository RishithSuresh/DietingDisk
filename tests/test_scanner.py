import threading
from backend.database import connect, create_scan
from backend.scanner import scan_roots


def test_scanner_inventories_temp_tree_without_modifying_files(tmp_path):
    root = tmp_path / "sample-drive"
    (root / "project" / "node_modules").mkdir(parents=True)
    source = root / "project" / "main.py"
    source.write_text("print('hello')", encoding="utf-8")
    data = root / "project" / "weights.pt"
    data.write_bytes(b"model-data")
    before_source = source.read_bytes()
    db_path = str(tmp_path / "scan.sqlite3")
    conn = connect(db_path)
    scan_id = create_scan(conn, [str(root)])
    conn.close()

    result = scan_roots(scan_id, [str(root)], db_path, threading.Event())
    assert result["status"] == "completed"
    assert result["files_scanned"] == 2
    assert source.read_bytes() == before_source

    conn = connect(db_path)
    rows = conn.execute("SELECT name,classification FROM files WHERE scan_id=?", (scan_id,)).fetchall()
    conn.close()
    labels = {row["name"]: row["classification"] for row in rows}
    assert labels["main.py"].startswith("PROTECT - SOURCE")
    assert labels["weights.pt"].startswith("PROTECT - DATA / MODEL")
