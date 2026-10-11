
import sqlite3
from pathlib import Path

DB = Path(
    r"C:\Users\rishi\AppData\Local\DietDisk\DietDisk.sqlite3"
)

if not DB.exists():
    raise SystemExit(f"Database not found: {DB}")

conn = sqlite3.connect(
    f"file:{DB.as_posix()}?mode=ro",
    uri=True,
)
conn.row_factory = sqlite3.Row

try:
    print("=== DIETINGDISK INVENTORY VALIDATION ===")
    print("Database integrity:", conn.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0])

    scan = conn.execute("""
        SELECT *
        FROM scans
        ORDER BY id DESC
        LIMIT 1
    """).fetchone()

    if scan is None:
        raise SystemExit("No scan records found.")

    scan_id = scan["id"]

    print("\n=== LATEST SCAN ===")
    for key in scan.keys():
        print(f"{key}: {scan[key]}")

    file_stats = conn.execute("""
        SELECT
            COUNT(*) AS row_count,
            COALESCE(SUM(size_bytes), 0) AS total_bytes,
            COALESCE(SUM(CASE WHEN size_bytes < 0
                THEN 1 ELSE 0 END), 0) AS negative_sizes,
            COALESCE(SUM(CASE WHEN path IS NULL OR path = ''
                THEN 1 ELSE 0 END), 0) AS empty_paths
        FROM files
        WHERE scan_id = ?
    """, (scan_id,)).fetchone()

    folder_stats = conn.execute("""
        SELECT
            COUNT(*) AS row_count,
            COALESCE(SUM(CASE WHEN total_bytes < 0
                THEN 1 ELSE 0 END), 0) AS negative_sizes,
            COALESCE(SUM(CASE WHEN path IS NULL OR path = ''
                THEN 1 ELSE 0 END), 0) AS empty_paths
        FROM folders
        WHERE scan_id = ?
    """, (scan_id,)).fetchone()

    issue_stats = conn.execute("""
        SELECT issue_type, COUNT(*) AS count
        FROM scan_issues
        WHERE scan_id = ?
        GROUP BY issue_type
        ORDER BY issue_type
    """, (scan_id,)).fetchall()

    print("\n=== FILE VALIDATION ===")
    print("Actual file rows:", file_stats["row_count"])
    print("Scan summary files:", scan["files_scanned"])
    print("Sum of file sizes (bytes):", file_stats["total_bytes"])
    print("Sum of file sizes (GB):",
          round(file_stats["total_bytes"] / 1_000_000_000, 3))
    print("Negative file sizes:", file_stats["negative_sizes"])
    print("Empty file paths:", file_stats["empty_paths"])

    print("\n=== FOLDER VALIDATION ===")
    print("Actual folder rows:", folder_stats["row_count"])
    print("Scan summary folders:", scan["folders_scanned"])
    print("Negative folder sizes:", folder_stats["negative_sizes"])
    print("Empty folder paths:", folder_stats["empty_paths"])

    print("\n=== ISSUE BREAKDOWN ===")
    for issue in issue_stats:
        print(f'{issue["issue_type"]}: {issue["count"]}')

    print("\n=== LARGEST RECORDED FILES ===")
    for row in conn.execute("""
        SELECT path, size_bytes, classification
        FROM files
        WHERE scan_id = ?
        ORDER BY size_bytes DESC
        LIMIT 10
    """, (scan_id,)):
        print(
            f'{row["size_bytes"] / 1_000_000_000:9.3f} GB | '
            f'{row["classification"]} | {row["path"]}'
        )

    print("\n=== RESULT ===")
    checks = {
        "Scan status completed": scan["status"] == "completed",
        "File counts match": file_stats["row_count"] == scan["files_scanned"],
        "Folder counts match": folder_stats["row_count"] == scan["folders_scanned"],
        "No negative file sizes": file_stats["negative_sizes"] == 0,
        "No empty file paths": file_stats["empty_paths"] == 0,
    }

    for name, passed in checks.items():
        print(f'{"PASS" if passed else "CHECK"}: {name}')

finally:
    conn.close()
