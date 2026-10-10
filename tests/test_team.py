"""Tests for the shared team broadcast channel."""

import pytest

from agent.runtime.team import TeamChannel
from agent.tools.registry import build_default_registry


def _bus(tmp_path, member):
    return TeamChannel(tmp_path / "team.sqlite", member)


def test_member_registers_on_init(tmp_path):
    a = _bus(tmp_path, "k1a")
    _bus(tmp_path, "k1b")
    assert set(a.members()) == {"k1a", "k1b"}


def test_broadcast_is_seen_by_others_not_self(tmp_path):
    a = _bus(tmp_path, "k1a")
    b = _bus(tmp_path, "k1b")
    a.post("claiming stability", "I'll take spectral stability")
    # b sees a's message; a does not see its own
    seen_b = b.unseen()
    assert [m["sender"] for m in seen_b] == ["k1a"]
    assert a.unseen() == []


def test_cursor_advances_so_each_message_shown_once(tmp_path):
    a = _bus(tmp_path, "k1a")
    b = _bus(tmp_path, "k1b")
    a.post("first", "")
    assert len(b.unseen()) == 1
    assert b.unseen() == []  # already consumed
    a.post("second", "")
    assert [m["summary"] for m in b.unseen()] == ["second"]


def test_unseen_is_chronological_and_capped(tmp_path):
    a = _bus(tmp_path, "k1a")
    b = _bus(tmp_path, "k1b")
    for i in range(25):
        a.post(f"m{i}", "")
    seen = b.unseen(limit=20)
    assert len(seen) == 20
    # newest 20, returned oldest-first
    assert seen[0]["summary"] == "m5"
    assert seen[-1]["summary"] == "m24"
    assert b.unseen() == []  # cursor advanced past everything


def test_recent_returns_history_newest_first(tmp_path):
    a = _bus(tmp_path, "k1a")
    a.post("one", "")
    a.post("two", "")
    recent = a.recent()
    assert [m["summary"] for m in recent] == ["two", "one"]


def test_empty_summary_rejected(tmp_path):
    a = _bus(tmp_path, "k1a")
    with pytest.raises(ValueError):
        a.post("   ", "body")


def test_missing_member_rejected(tmp_path):
    with pytest.raises(ValueError):
        TeamChannel(tmp_path / "team.sqlite", "")


def test_registry_exposes_team_tools_only_with_channel(tmp_path):
    a = _bus(tmp_path, "k1a")
    with_team = build_default_registry(tmp_path, team_channel=a)
    assert "message_team" in with_team
    assert "read_team" in with_team
    without = build_default_registry(tmp_path)
    assert "message_team" not in without
