from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .models import MemoryEntry

WORK_CONTEXT = "Work Context"
PROJECT = "Projects"
PERSONAL = "Personal Preferences"
ARCHIVE = "Archive"

CANONICAL_CATEGORIES = [WORK_CONTEXT, PROJECT, PERSONAL]

_CATEGORY_ALIASES = {
    "workcontext": WORK_CONTEXT,
    "work_context": WORK_CONTEXT,
    "work": WORK_CONTEXT,
    "context": WORK_CONTEXT,
    "task": WORK_CONTEXT,
    "work-context": WORK_CONTEXT,
    "work context": WORK_CONTEXT,
    "작업컨텍스트": WORK_CONTEXT,
    "작업": WORK_CONTEXT,
    "컨텍스트": WORK_CONTEXT,
    "작업 컨텍스트": WORK_CONTEXT,
    "project": PROJECT,
    "projects": PROJECT,
    "proj": PROJECT,
    "프로젝트": PROJECT,
    "personal": PERSONAL,
    "preferences": PERSONAL,
    "personal-preferences": PERSONAL,
    "personal preferences": PERSONAL,
    "prefs": PERSONAL,
    "pref": PERSONAL,
    "setting": PERSONAL,
    "settings": PERSONAL,
    "preference": PERSONAL,
    "persona": PERSONAL,
    "개인설정": PERSONAL,
    "개인": PERSONAL,
    "개인 설정": PERSONAL,
    "archive": ARCHIVE,
    "archived": ARCHIVE,
    "아카이브": ARCHIVE,
}

_ENTRY_PREFIX = "<!-- memmd-entry "
_ENTRY_SUFFIX = " -->"


def _normalize_key(text: str) -> str:
    return "".join(ch for ch in text.strip().lower() if not ch.isspace())


def normalize_category(category: str | None) -> str:
    if not category:
        return WORK_CONTEXT
    normalized = _CATEGORY_ALIASES.get(_normalize_key(category))
    if normalized:
        return normalized
    stripped = category.strip()
    if stripped in CANONICAL_CATEGORIES:
        return stripped
    return WORK_CONTEXT


class MemoryStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> tuple[list[MemoryEntry], list[MemoryEntry]]:
        if not self.path.exists():
            self.save([], [])
            return [], []

        text = self.path.read_text(encoding="utf-8")
        lines = text.splitlines()
        active: list[MemoryEntry] = []
        archive: list[MemoryEntry] = []

        current_section = WORK_CONTEXT
        current_meta: dict | None = None
        current_content: list[str] = []

        def flush() -> None:
            nonlocal current_meta, current_content
            if not current_meta:
                return
            content = "\n".join(current_content).strip()
            entry = MemoryEntry.from_meta(
                meta=current_meta,
                content=content,
                fallback_category=normalize_category(current_meta.get("category") or current_section),
            )
            if not entry.id:
                current_meta = None
                current_content = []
                return
            if current_section == ARCHIVE or entry.archived_at:
                archive.append(entry)
            else:
                entry.category = normalize_category(entry.category)
                active.append(entry)
            current_meta = None
            current_content = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("## "):
                flush()
                current_section = stripped.removeprefix("## ").strip()
                continue

            if stripped.startswith(_ENTRY_PREFIX) and stripped.endswith(_ENTRY_SUFFIX):
                flush()
                payload = stripped[len(_ENTRY_PREFIX) : -len(_ENTRY_SUFFIX)].strip()
                try:
                    current_meta = json.loads(payload)
                except json.JSONDecodeError:
                    current_meta = None
                current_content = []
                continue

            if current_meta is not None:
                current_content.append(line)

        flush()
        return active, archive

    def save(self, active: list[MemoryEntry], archive: list[MemoryEntry]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

        by_category: dict[str, list[MemoryEntry]] = defaultdict(list)
        for entry in active:
            entry.category = normalize_category(entry.category)
            by_category[entry.category].append(entry)

        lines: list[str] = [
            "# memory.md",
            "",
            "<!-- memmd:version=1 -->",
            "",
        ]

        ordered_categories = list(CANONICAL_CATEGORIES)
        extra_categories = sorted(cat for cat in by_category if cat not in CANONICAL_CATEGORIES)
        ordered_categories.extend(extra_categories)

        for category in ordered_categories:
            lines.append(f"## {category}")
            lines.append("")
            entries = sorted(
                by_category.get(category, []),
                key=lambda item: (item.updated_at, item.created_at),
                reverse=True,
            )
            for entry in entries:
                lines.extend(self._serialize_entry(entry, category))
            lines.append("")

        lines.append(f"## {ARCHIVE}")
        lines.append("")
        archived = sorted(
            archive,
            key=lambda item: (item.archived_at or "", item.updated_at, item.created_at),
            reverse=True,
        )
        for entry in archived:
            lines.extend(self._serialize_entry(entry, ARCHIVE))
        lines.append("")

        content = "\n".join(lines).rstrip() + "\n"
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        temp_path.write_text(content, encoding="utf-8")
        temp_path.replace(self.path)

    @staticmethod
    def _serialize_entry(entry: MemoryEntry, category: str) -> list[str]:
        entry.category = category
        meta = entry.to_meta()
        payload = json.dumps(meta, ensure_ascii=False, sort_keys=True)
        body_lines = entry.content.splitlines() if entry.content else ["(empty)"]
        result = [f"{_ENTRY_PREFIX}{payload}{_ENTRY_SUFFIX}", *body_lines, ""]
        return result
