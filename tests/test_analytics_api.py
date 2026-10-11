from backend import api
from backend.database import connect, create_scan


def _seeded_database(tmp_path, monkeypatch):
    db_path = tmp_path / "analytics.sqlite3"
    conn = connect(db_path)
    scan_id = create_scan(conn, ["D:\\"])
    conn.execute("UPDATE scans SET status='completed', files_scanned=1, folders_scanned=2, bytes_scanned=1234 WHERE id=?", (scan_id,))
    conn.execute("INSERT INTO folders(scan_id,path,parent_path,name,total_bytes,direct_bytes,file_count,child_folder_count) VALUES(?,?,?,?,?,?,?,?)", (scan_id, "D:\\", "D:\\", "D:\\", 1234, 0, 1, 1))
    conn.execute("INSERT INTO folders(scan_id,path,parent_path,name,total_bytes,direct_bytes,file_count,child_folder_count) VALUES(?,?,?,?,?,?,?,?)", (scan_id, r"D:\Music", "D:\\", "Music", 1234, 1234, 1, 0))
    conn.execute("INSERT INTO files(scan_id,path,parent_path,name,extension,size_bytes,modified_at,classification,reason) VALUES(?,?,?,?,?,?,?,?,?)", (scan_id, r"D:\Music\song.mp3", r"D:\Music", "song.mp3", ".mp3", 1234, None, "PROTECT - MEDIA / PERSONAL FILE", "Recognized media"))
    conn.commit()
    conn.close()
    monkeypatch.setattr(api, "connect", lambda: connect(db_path))
    return scan_id


def test_analytics_reports_extensions_and_largest_folders(tmp_path, monkeypatch):
    scan_id = _seeded_database(tmp_path, monkeypatch)
    data = api.analytics(scan_id)
    assert data["scan"]["id"] == scan_id
    assert data["extensions"][0]["extension"] == ".mp3"
    assert data["extensions"][0]["bytes"] == 1234
    assert data["largest_folders"][0]["total_bytes"] == 1234


def test_treemap_returns_only_direct_children(tmp_path, monkeypatch):
    scan_id = _seeded_database(tmp_path, monkeypatch)
    root = api.treemap(scan_id, "D:\\", 120)
    assert any(item["type"] == "folder" and item["name"] == "Music" for item in root["items"])
    inside = api.treemap(scan_id, r"D:\Music", 120)
    assert len(inside["items"]) == 1
    assert inside["items"][0]["name"] == "song.mp3"
