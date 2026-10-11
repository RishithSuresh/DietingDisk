"""Conservative, explainable file classification. No category authorizes deletion."""
from __future__ import annotations
from pathlib import PureWindowsPath

SYSTEM_ROOTS = (
    "C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)",
    "C:\\ProgramData", "C:\\$Recycle.Bin", "C:\\System Volume Information",
)
DATA_EXTENSIONS = {
    ".pt", ".pth", ".onnx", ".safetensors", ".ckpt", ".h5", ".keras",
    ".pkl", ".pickle", ".parquet", ".feather", ".tfrecord", ".bin",
}
SOURCE_EXTENSIONS = {
    ".py", ".c", ".h", ".cpp", ".hpp", ".dart", ".js", ".ts", ".jsx",
    ".tsx", ".sql", ".html", ".css", ".java", ".ipynb", ".md", ".toml",
    ".yaml", ".yml", ".json", ".xml", ".sh", ".ps1",
}
ARCHIVE_EXTENSIONS = {".zip", ".7z", ".rar", ".iso", ".tar", ".gz", ".bz2", ".xz", ".bak", ".old", ".log", ".exe", ".msi", ".cab", ".dmg"}
CACHE_DIRS = {
    "node_modules", ".venv", "venv", "env", "__pycache__", ".gradle", ".npm",
    ".cache", "pip-cache", "temp", "tmp", "build", "dist", "cache",
}
DATA_DIR_HINTS = {
    "dataset", "datasets", "checkpoint", "checkpoints", "weights", "models",
    "model", "ff++", "ffpp", "dfdc", "celeb-df", "celebdv2", "asvspoof",
    "wavefake", "fakeavceleb", "deeperforensics",
}
GAME_DIR_HINTS = {"steamapps", "common", "epic games", "origin games", "ea games", "xboxgames", "program files"}
GAME_EXTENSIONS = {".cas", ".pak", ".vpk", ".bundle", ".assets", ".unity3d", ".wem", ".bnk"}
MEDIA_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".mp3", ".wav", ".flac", ".aac", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".raw"}
DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".rtf", ".odt", ".csv"}
DATABASE_EXTENSIONS = {".db", ".sqlite", ".sqlite3", ".mdb"}


def classify_path(path: str, is_directory: bool = False) -> tuple[str, str]:
    """Return (classification, explanation); advisory only, never a cleanup action."""
    p = PureWindowsPath(path)
    normalized = str(p).replace("/", "\\").casefold()
    parts_list = [part.casefold().rstrip("\\/") for part in p.parts]
    parts = set(parts_list)
    ext = p.suffix.casefold()
    protected_first_level = {"windows", "program files", "program files (x86)", "programdata", "$recycle.bin", "system volume information"}
    if any(normalized == root.casefold() or normalized.startswith(root.casefold() + "\\") for root in SYSTEM_ROOTS) or (len(parts_list) >= 2 and parts_list[1] in protected_first_level):
        return "PROTECTED - SYSTEM / APPLICATION", "Located in a Windows-managed or application system directory; do not manually remove. Confidence: high."

    if ext in DATABASE_EXTENSIONS:
        return "PROTECT - APPLICATION DATA", "Database file may contain application state or inventory history. Confirm ownership and backup before any change. Confidence: high."
    if parts & DATA_DIR_HINTS or ext in DATA_EXTENSIONS:
        return "PROTECT - DATA / MODEL CANDIDATE", "Path or file type resembles a dataset, model, checkpoint, or serialized data; verify purpose and backups. Confidence: high."
    if parts & {"steamapps", "epic games", "origin games", "ea games", "xboxgames"} or ext in GAME_EXTENSIONS:
        return "PROTECT - GAME / APPLICATION ASSET", "Likely game or application content required by installed software. Do not delete individual asset files; use the application's repair/uninstall tools. Confidence: medium-high."
    if ext in {".tmp", ".temp", ".part", ".download"} or (bool(p.drive) and parts & {"temp", "tmp"}):
        return "REVIEW - TEMPORARY FILE CANDIDATE", "Name or location resembles temporary or incomplete data, but the file may still be in use. Check age, owner process, and application state before considering cleanup. Confidence: low-medium."
    if parts & (CACHE_DIRS - {"temp", "tmp"}):
        return "REVIEW - POSSIBLE CACHE / REBUILD OUTPUT", "May be regenerable, but can contain active dependencies or build artifacts. Verify the owning project first. Confidence: medium."
    if ext in ARCHIVE_EXTENSIONS:
        return "REVIEW - ARCHIVE / INSTALLER / BACKUP / LOG", "May be redundant or re-downloadable, but could be an important installer, backup, or log. Verify contents and backup value. Confidence: medium."
    if ext in MEDIA_EXTENSIONS:
        return "PROTECT - MEDIA / PERSONAL FILE", "Recognized media format; treat as user content unless you have verified a duplicate or backup. Confidence: medium-high."
    if ext in DOCUMENT_EXTENSIONS:
        return "PROTECT - DOCUMENT / USER DATA", "Recognized document or tabular-data format; preserve unless you have verified another copy. Confidence: medium-high."
    if parts & {".git", "src", "source", "documents", "desktop", "downloads"} or ext in SOURCE_EXTENSIONS:
        return "PROTECT - SOURCE / USER DATA", "Likely source code, project metadata, or user data; preserve unless you have verified another copy. Confidence: medium-high."
    return "REVIEW - PURPOSE UNKNOWN", "DietingDisk cannot safely infer whether this item is disposable from its path alone. Confidence: low."
