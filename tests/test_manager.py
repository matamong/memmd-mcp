from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from memmd_mcp.logic import MemoryManager
from memmd_mcp.storage import MemoryStore


def _new_manager(tmp_path: Path, stale_days: int = 120) -> tuple[MemoryManager, MemoryStore]:
    store = MemoryStore(tmp_path / "memory.md")
    return MemoryManager(store=store, stale_days=stale_days), store


def test_remember_merges_duplicate(tmp_path: Path) -> None:
    manager, store = _new_manager(tmp_path)
    first = manager.remember("repo: memmd-mcp", "Projects")
    second = manager.remember("repo = memmd-mcp", "Projects")

    assert first["status"] == "created"
    assert second["status"] in {"merged", "merged_conflict"}

    active, _ = store.load()
    assert len(active) == 1


def test_remember_resolves_conflict(tmp_path: Path) -> None:
    manager, store = _new_manager(tmp_path)
    manager.remember("api_url: https://a.example.com", "Projects")
    result = manager.remember("api_url: https://b.example.com", "Projects")

    assert result["status"] == "merged_conflict"
    active, _ = store.load()
    assert len(active) == 1
    assert active[0].facts.get("api_url") == "https://b.example.com"


def test_recall_with_section_filter(tmp_path: Path) -> None:
    manager, _ = _new_manager(tmp_path)
    proj = manager.remember("repo: memmd-mcp", "Projects")
    ctx = manager.remember("language: python", "Work Context")

    text = manager.recall("category:Projects repo")
    assert proj["id"] in text
    assert ctx["id"] not in text


def test_summarize_archives_stale_entries(tmp_path: Path) -> None:
    manager, store = _new_manager(tmp_path, stale_days=1)
    manager.remember("keep: recent", "Work Context")

    active, archive = store.load()
    assert len(active) == 1
    active[0].updated_at = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    store.save(active, archive)

    summary = manager.summarize()
    assert "cleaned this run: 1" in summary

    active, archive = store.load()
    assert len(active) == 0
    assert len(archive) == 1


def test_korean_category_alias_still_works(tmp_path: Path) -> None:
    manager, _ = _new_manager(tmp_path)
    result = manager.remember("editor: cursor", "개인 설정")
    assert result["category"] == "Personal Preferences"
