# DiskSense — Windows Storage Auditor

DiskSense is a Windows desktop application with an embedded web-style interface for understanding disk usage. Phase 1 provides a read-only inventory of selected drive roots, explainable file labels, folder-size summaries, access-error/exclusion reporting, and CSV export.

## Safety boundary

- Phase 1 has no delete, move, rename, or cleanup endpoint.
- Scanned file contents are not opened; the scanner reads filesystem metadata only.
- Symbolic links, junctions, and Windows-managed `$Recycle.Bin` / `System Volume Information` directories are skipped and logged as exclusions.
- Access errors are recorded; therefore the inventory can be incomplete.
- Classification is advisory. Even “cache” or “rebuild output” labels are not permission to delete.
- The local API binds to `127.0.0.1` only. Do not change this to `0.0.0.0`.

## Requirements

- Windows 10/11
- Python 3.10 or 3.11 recommended (the project uses syntax compatible with Python 3.10+)
- A working Windows WebView2 Runtime for the embedded window (commonly already present on Windows 11)

## Setup (PowerShell)

```powershell
cd D:\Programming
mkdir DiskSense
# If you extracted the project elsewhere, use that extracted path instead.
cd .\DiskSense
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, run this for the current terminal only, then activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

If Python 3.10 is not registered with the Windows Python launcher, check installed versions with `py -0p` and substitute an installed Python 3.10 or 3.11 version. The project has also been written to avoid requiring a preview Python release. Avoid installing a preview Python release for this beginner project.

## Run the application

```powershell
python main.py
```

The app opens a desktop window. Select C: and D: and press **Start full scan**. The first full-drive scan may take a long time. Keep the app open until the scan finishes or cancellation completes.

## Run tests

```powershell
python -m pytest -q
```

## Data location

By default, the SQLite database and CSV reports are stored under `%LOCALAPPDATA%\DiskSense\` (typically `C:\Users\<you>\AppData\Local\DiskSense\`). If C: is low on free space, set a data directory on a drive with more space before launching, for example:

```powershell
$env:DISKSENSE_DATA_DIR = "D:\DiskSenseData"
python main.py
```

This override is the full data directory; the database and reports will be stored there. Keep this directory outside the source repository.

## Phase 1 API endpoints

- `GET /api/health`
- `GET /api/drives`
- `POST /api/scan/start`
- `POST /api/scan/cancel`
- `GET /api/scan/status`
- `GET /api/scans`
- `GET /api/summary`
- `GET /api/files`
- `GET /api/folders`
- `GET /api/issues`
- `GET /api/export/csv`

## Current limitations

- This is an initial Phase 1 implementation, not a certified cleanup tool.
- A scan records accessible files and folders, not filesystem slack, NTFS metadata, or every hidden/protected allocation.
- Directory size totals are computed from files the scanner can inventory; compare with Windows storage reports.
- Drive root detection and WebView2 behavior should be tested on the target Windows PC.
- File classification is heuristic and intentionally errs toward preserving data.
- Duplicate detection, cleanup recommendations with approval, Recycle Bin integration, scheduled scans, and packaging are future phases.
