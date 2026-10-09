from backend.database import connect, create_scan


def test_scan_can_be_created_in_temporary_database(tmp_path):
    db = tmp_path / "test.sqlite3"
    conn = connect(db)
    scan_id = create_scan(conn, ["C:\\", "D:\\"])
    row = conn.execute("SELECT status, roots_json FROM scans WHERE id=?", (scan_id,)).fetchone()
    assert row["status"] == "running"
    assert "C:" in row["roots_json"]
    conn.close()
