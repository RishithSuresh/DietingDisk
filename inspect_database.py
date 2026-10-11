
import sqlite3
from pathlib import Path

db_path = Path(
    r"C:\Users\rishi\AppData\Local\DietDisk\DietDisk.sqlite3"
)

if not db_path.exists():
    print(f"Database not found: {db_path}")
    raise SystemExit(1)

connection = sqlite3.connect(
    f"file:{db_path.as_posix()}?mode=ro",
    uri=True
)

connection.row_factory = sqlite3.Row

try:
    print("DATABASE:", db_path)
    print("INTEGRITY:", connection.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0])

    tables = connection.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """).fetchall()

    print("\nTABLE ROW COUNTS:")

    for (table_name,) in tables:
        safe_name = table_name.replace('"', '""')
        count = connection.execute(
            f'SELECT COUNT(*) FROM "{safe_name}"'
        ).fetchone()[0]

        print(f"\n{table_name}: {count} rows")

        if table_name == "scans":
            for scan in connection.execute("""
                SELECT id, started_at, finished_at, status,
                       roots_json, files_scanned, folders_scanned,
                       bytes_scanned, errors_count, exclusions_count,
                       message
                FROM scans
                ORDER BY id DESC
                LIMIT 5
            """):
                print(dict(scan))

finally:
    connection.close()
