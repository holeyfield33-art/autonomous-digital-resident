from pathlib import Path

import pytest

from agent.tools.filesystem import FilesystemTools


@pytest.mark.parametrize("method", ["snapshot", "summary"])
def test_inventory_tolerates_teammate_removing_enumerated_file(tmp_path, monkeypatch, method):
    fs = FilesystemTools(tmp_path)
    stable = tmp_path / "stable.txt"
    stable.write_text("kept")
    removed = tmp_path / "removed.txt"
    removed.write_text("gone")

    def changing_walk(root):
        yield stable
        removed.unlink()
        yield removed

    monkeypatch.setattr(fs, "_walk", changing_walk)
    result = getattr(fs, method)()
    if method == "snapshot":
        assert set(result) == {"stable.txt"}
    else:
        assert result["files"] == 1
        assert result["bytes"] == 4
        assert result["disappeared_during_scan"] == 1
        assert result["recently_modified"][0]["path"] == "stable.txt"


def test_summary_uses_one_metadata_read_per_file(tmp_path, monkeypatch):
    fs = FilesystemTools(tmp_path)
    path = tmp_path / "once.txt"
    path.write_text("kept")
    real_stat = Path.stat
    reads = 0

    def stat_once(self, *args, **kwargs):
        nonlocal reads
        if self == path:
            reads += 1
            if reads > 1:
                raise FileNotFoundError(str(path))
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat_once)
    result = fs.summary()
    assert result["bytes"] == 4
    assert result["recently_modified"][0]["path"] == "once.txt"


@pytest.mark.parametrize("method", ["snapshot", "summary"])
def test_inventory_does_not_hide_permission_errors(tmp_path, monkeypatch, method):
    fs = FilesystemTools(tmp_path)
    path = tmp_path / "denied.txt"
    path.write_text("data")
    real_stat = Path.stat

    def denied(self, *args, **kwargs):
        if self == path:
            raise PermissionError("denied")
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", denied)
    with pytest.raises(PermissionError):
        getattr(fs, method)()
