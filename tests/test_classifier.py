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
