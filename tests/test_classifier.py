from backend.classifier import classify_path


def test_model_checkpoint_is_protected():
    label, reason = classify_path(r"D:\Programming\deepfake\model\checkpoints\best.pt")
    assert label.startswith("PROTECT - DATA / MODEL")
    assert "checkpoint" in reason or "model" in reason


def test_source_code_is_protected():
    label, _ = classify_path(r"D:\Programming\DiskSense\backend\scanner.py")
    assert label.startswith("PROTECT - SOURCE")


def test_node_modules_is_review_only():
    label, reason = classify_path(r"D:\Programming\webapp\node_modules\react\index.js")
    assert label.startswith("REVIEW - POSSIBLE CACHE")
    assert "Verify" in reason


def test_unknown_file_is_not_assumed_deletable():
    label, _ = classify_path(r"D:\misc\large.unknownext")
    assert label == "REVIEW - PURPOSE UNKNOWN"


def test_game_asset_is_protected():
    label, reason = classify_path(r"D:\Steam\steamapps\common\FC 26\Data\install.cas")
    assert label.startswith("PROTECT - GAME / APPLICATION")
    assert "application" in reason.lower() or "game" in reason.lower()


def test_database_file_is_protected_as_application_data():
    label, reason = classify_path(r"D:\DietingDiskData\disksense.sqlite3")
    assert label.startswith("PROTECT - APPLICATION DATA")
    assert "database" in reason.lower()


def test_temporary_file_is_review_only():
    label, reason = classify_path(r"D:\temp\extract.tmp")
    assert label.startswith("REVIEW - TEMPORARY FILE")
    assert "in use" in reason.lower()
