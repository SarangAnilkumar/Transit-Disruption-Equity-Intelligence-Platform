"""Path and directory behavior tests."""

from pathlib import Path

from ingestion.utils import ensure_dir


def test_ensure_dir_creates_required_folders(tmp_path: Path) -> None:
    target = tmp_path / "data" / "raw" / "gtfs_realtime"
    created = ensure_dir(target)
    assert created.exists()
    assert created.is_dir()
