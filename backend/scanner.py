"""Read-only inventory scanner for Windows drives."""
from __future__ import annotations
import os
import stat
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .classifier import classify_path
from .config import EXCLUDED_DIRECTORY_NAMES
from .database import connect

ProgressCallback = Callable[[dict], None]


def _is_reparse_or_link(entry: os.DirEntry) -> bool:
    try:
        if entry.is_symlink():
            return True
        st = entry.stat(follow_symlinks=False)
        # Windows FILE_ATTRIBUTE_REPARSE_POINT. getattr keeps this portable for tests.
        attrs = getattr(st, "st_file_attributes", 0)
        return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    except OSError:
        return False


def scan_roots(scan_id: int, roots: list[str], db_path: str, stop_event, progress: ProgressCallback | None = None) -> dict:
    """Inventory accessible files. Never opens file contents or changes scanned items."""
    conn = connect(db_path)
    files_count = folders_count = bytes_count = errors_count = exclusions_count = 0
    last_progress = time.monotonic()
    batch_count = 0

    def issue(path: str, kind: str, message: str) -> None:
        nonlocal errors_count, exclusions_count
        conn.execute("INSERT INTO scan_issues(scan_id,path,issue_type,message) VALUES(?,?,?,?)",
                     (scan_id, path, kind, message[:1000]))
        if kind == "excluded":
            exclusions_count += 1
        else:
            errors_count += 1

    def emit(current_path: str = "") -> None:
        nonlocal last_progress
        now = time.monotonic()
        if progress and now - last_progress >= 0.4:
            progress({"scan_id": scan_id, "status": "running", "files_scanned": files_count,
                      "folders_scanned": folders_count, "bytes_scanned": bytes_count,
                      "errors_count": errors_count, "exclusions_count": exclusions_count,
                      "current_path": current_path})
            last_progress = now

    try:
        for root_text in roots:
            if stop_event.is_set():
                break
            root = Path(root_text)
            if not root.exists():
                issue(str(root), "unavailable", "Drive root is unavailable or does not exist.")
                conn.commit()
                continue
            # Iterative post-order traversal: avoids recursion depth limits and follows no links.
            stack: list[tuple[str, bool, list[str] | None]] = [(str(root), False, None)]
            direct_bytes: dict[str, int] = {}
            direct_files: dict[str, int] = {}
            child_dirs: dict[str, list[str]] = {}
            totals: dict[str, int] = {}
            file_counts: dict[str, int] = {}

            while stack and not stop_event.is_set():
                folder, visited, children = stack.pop()
                if not visited:
                    folders_count += 1
                    direct_bytes[folder] = 0
                    direct_files[folder] = 0
                    child_dirs[folder] = []
                    try:
                        with os.scandir(folder) as entries:
                            entries_list = list(entries)
                    except (PermissionError, OSError) as exc:
                        issue(folder, "access_error", f"Cannot list directory: {exc}")
                        totals[folder] = 0
                        file_counts[folder] = 0
                        conn.execute(
                            "INSERT INTO folders(scan_id,path,parent_path,name,total_bytes,direct_bytes,file_count,child_folder_count) VALUES(?,?,?,?,?,?,?,?)",
                            (scan_id, folder, str(Path(folder).parent), Path(folder).name or folder, 0, 0, 0, 0))
                        batch_count += 1
                        if batch_count >= 500:
                            conn.commit(); batch_count = 0
                        continue

                    child_paths: list[str] = []
                    for entry in entries_list:
                        if stop_event.is_set():
                            break
                        try:
                            if _is_reparse_or_link(entry):
                                issue(entry.path, "excluded", "Skipped symbolic link/junction/reparse point to avoid loops or leaving the selected tree.")
                                continue
                            if entry.is_dir(follow_symlinks=False):
                                if entry.name in EXCLUDED_DIRECTORY_NAMES:
                                    issue(entry.path, "excluded", "Skipped Windows-managed metadata directory by policy.")
                                    continue
                                child_paths.append(entry.path)
                            elif entry.is_file(follow_symlinks=False):
                                st = entry.stat(follow_symlinks=False)
                                size = int(st.st_size)
                                modified = datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat()
                                classification, reason = classify_path(entry.path)
                                path_obj = Path(entry.path)
                                conn.execute(
                                    "INSERT INTO files(scan_id,path,parent_path,name,extension,size_bytes,modified_at,classification,reason) VALUES(?,?,?,?,?,?,?,?,?)",
                                    (scan_id, entry.path, folder, entry.name, path_obj.suffix.lower(), size, modified, classification, reason))
                                direct_bytes[folder] += size
                                direct_files[folder] += 1
                                files_count += 1
                                bytes_count += size
                                batch_count += 1
                                if batch_count >= 500:
                                    conn.commit(); batch_count = 0
                        except (PermissionError, OSError) as exc:
                            issue(entry.path, "access_error", f"Cannot inspect entry: {exc}")
                    child_dirs[folder] = child_paths
                    stack.append((folder, True, child_paths))
                    for child in reversed(child_paths):
                        stack.append((child, False, None))
                    emit(folder)
                else:
                    total = direct_bytes.get(folder, 0) + sum(totals.get(child, 0) for child in child_dirs.get(folder, []))
                    count = direct_files.get(folder, 0) + sum(file_counts.get(child, 0) for child in child_dirs.get(folder, []))
                    totals[folder] = total
                    file_counts[folder] = count
                    parent = str(Path(folder).parent)
                    conn.execute(
                        "INSERT INTO folders(scan_id,path,parent_path,name,total_bytes,direct_bytes,file_count,child_folder_count) VALUES(?,?,?,?,?,?,?,?)",
                        (scan_id, folder, parent, Path(folder).name or folder, total,
                         direct_bytes.get(folder, 0), count, len(child_dirs.get(folder, [])))
                    )
                    batch_count += 1
                    if batch_count >= 500:
                        conn.commit(); batch_count = 0
                    emit(folder)
            conn.commit()

        status = "cancelled" if stop_event.is_set() else "completed"
        message = "Scan stopped by user." if status == "cancelled" else "Scan finished. Review exclusions and access errors before treating the inventory as complete."
        conn.execute(
            "UPDATE scans SET finished_at=?,status=?,files_scanned=?,folders_scanned=?,bytes_scanned=?,errors_count=?,exclusions_count=?,message=? WHERE id=?",
            (datetime.now(timezone.utc).isoformat(), status, files_count, folders_count, bytes_count,
             errors_count, exclusions_count, message, scan_id))
        conn.commit()
        result = {"scan_id": scan_id, "status": status, "files_scanned": files_count,
                  "folders_scanned": folders_count, "bytes_scanned": bytes_count,
                  "errors_count": errors_count, "exclusions_count": exclusions_count, "message": message}
        if progress:
            progress(result)
        return result
    except Exception as exc:
        conn.rollback()
        conn.execute("UPDATE scans SET finished_at=?,status='failed',message=? WHERE id=?",
                     (datetime.now(timezone.utc).isoformat(), str(exc)[:1000], scan_id))
        conn.commit()
        raise
    finally:
        conn.close()
