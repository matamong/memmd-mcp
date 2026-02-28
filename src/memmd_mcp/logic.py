from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from .models import MemoryEntry
from .storage import ARCHIVE, CANONICAL_CATEGORIES, MemoryStore, normalize_category

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "was",
    "were",
    "with",
    "그리고",
    "그",
    "이",
    "저",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "에",
    "의",
}

_FACT_PATTERNS = [
    re.compile(r"^\s*([A-Za-z0-9가-힣 _/\-]{2,60})\s*[:=]\s*(.+?)\s*$"),
    re.compile(r"^\s*([A-Za-z0-9가-힣 _/\-]{2,60})\s*(?:는|은)\s+(.+?)\s*$"),
    re.compile(r"^\s*([A-Za-z0-9 _/\-]{2,60})\s+is\s+(.+?)\s*$", re.IGNORECASE),
]

_SECTION_FILTER_PATTERNS = [
    re.compile(r"(?:section|category)\s*:\s*\"([^\"]+)\"", re.IGNORECASE),
    re.compile(r"(?:section|category)\s*:\s*([^\s]+)", re.IGNORECASE),
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _normalize_text(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"[^\w가-힣\s:/=-]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def _tokenize(text: str) -> set[str]:
    raw_tokens = re.findall(r"[a-z0-9가-힣]+", text.lower())
    tokens = {token for token in raw_tokens if len(token) > 1 and token not in _STOPWORDS}
    return tokens


def _sentence_chunks(text: str) -> list[str]:
    chunks: list[str] = []
    for line in text.splitlines():
        for chunk in re.split(r"[;]+", line):
            stripped = chunk.strip()
            if stripped:
                chunks.append(stripped)
    return chunks


def _jaccard_similarity(a: str, b: str) -> float:
    a_tokens = _tokenize(a)
    b_tokens = _tokenize(b)
    if not a_tokens and not b_tokens:
        return 1.0 if _normalize_text(a) == _normalize_text(b) else 0.0
    if not a_tokens or not b_tokens:
        return 0.0
    inter = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    return inter / union if union else 0.0


def _build_fingerprint(text: str) -> str:
    tokens = sorted(_tokenize(text))
    digest = hashlib.sha1((" ".join(tokens)).encode("utf-8")).hexdigest()[:16]
    return digest


def _merge_contents(existing: str, incoming: str) -> str:
    if not existing.strip():
        return incoming.strip()
    if not incoming.strip():
        return existing.strip()

    merged: list[str] = []
    seen: set[str] = set()
    for sentence in _sentence_chunks(existing) + _sentence_chunks(incoming):
        key = _normalize_text(sentence)
        if key in seen:
            continue
        seen.add(key)
        merged.append(sentence)
    return "\n".join(merged).strip()


def _extract_facts(text: str) -> dict[str, str]:
    facts: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        for pattern in _FACT_PATTERNS:
            matched = pattern.match(stripped)
            if not matched:
                continue
            key = _normalize_text(matched.group(1))
            value = matched.group(2).strip().rstrip(".")
            if len(key) < 2 or len(value) < 1:
                continue
            facts[key] = value
            break
    return facts


def _snippet(text: str, limit: int = 160) -> str:
    one_line = " ".join(text.split())
    if len(one_line) <= limit:
        return one_line
    return one_line[: limit - 1].rstrip() + "…"


def _make_memory_id() -> str:
    return "mem_" + uuid.uuid4().hex[:12]


@dataclass(slots=True)
class _Conflict:
    entry: MemoryEntry
    key: str
    old_value: str
    new_value: str


class MemoryManager:
    def __init__(self, store: MemoryStore, stale_days: int = 120):
        self.store = store
        self.stale_days = max(7, stale_days)

    def remember(self, content: str, category: str | None) -> dict[str, str]:
        clean_content = (content or "").strip()
        if not clean_content:
            return {"status": "error", "message": "content is empty"}

        canonical_category = normalize_category(category)
        active, archive = self.store.load()
        now = _utc_now()

        new_facts = _extract_facts(clean_content)
        same_category = [entry for entry in active if entry.category == canonical_category]
        duplicate = self._find_best_duplicate(clean_content, same_category)
        if duplicate is None:
            duplicate = self._find_best_duplicate(clean_content, active)

        if duplicate is not None:
            inline_conflicts: list[str] = []
            for key, new_value in new_facts.items():
                old_value = duplicate.facts.get(key)
                if old_value and _normalize_text(old_value) != _normalize_text(new_value):
                    inline_conflicts.append(f"{key}: '{old_value}' -> '{new_value}' (inline)")

            duplicate.content = _merge_contents(duplicate.content, clean_content)
            duplicate.updated_at = now
            duplicate.merge_count += 1
            duplicate.facts = {**duplicate.facts, **new_facts}
            conflict_notes = self._resolve_conflicts(
                active=active,
                archive=archive,
                target=duplicate,
                facts=new_facts,
                now=now,
            )
            if inline_conflicts:
                duplicate.conflicts = list(dict.fromkeys([*duplicate.conflicts, *inline_conflicts]))
            self.store.save(active, archive)
            all_conflicts = len(conflict_notes) + len(inline_conflicts)
            note_msg = f", conflict: {all_conflicts}" if all_conflicts else ""
            status = "merged_conflict" if all_conflicts else "merged"
            return {
                "status": status,
                "message": f"merged into {duplicate.id}{note_msg}",
                "id": duplicate.id,
                "category": duplicate.category,
            }

        conflicts = self._collect_conflicts(active, new_facts)
        if conflicts:
            target = self._select_conflict_target(conflicts, canonical_category)
            target.content = _merge_contents(target.content, clean_content)
            target.updated_at = now
            target.merge_count += 1
            target.facts = {**target.facts, **new_facts}
            conflict_notes = self._apply_conflict_resolution(
                active=active,
                archive=archive,
                target=target,
                conflicts=conflicts,
                now=now,
            )
            self.store.save(active, archive)
            return {
                "status": "merged_conflict",
                "message": f"resolved contradictions into {target.id} ({len(conflict_notes)} changes)",
                "id": target.id,
                "category": target.category,
            }

        entry = MemoryEntry(
            id=_make_memory_id(),
            category=canonical_category,
            content=clean_content,
            created_at=now,
            updated_at=now,
            fingerprint=_build_fingerprint(clean_content),
            facts=new_facts,
        )
        active.append(entry)
        self.store.save(active, archive)
        return {
            "status": "created",
            "message": f"created {entry.id}",
            "id": entry.id,
            "category": canonical_category,
        }

    def recall(self, query: str) -> str:
        raw_query = (query or "").strip()
        section_filters, search_query = self._parse_filters(raw_query)

        active, archive = self.store.load()
        scored: list[tuple[float, MemoryEntry]] = []
        query_tokens = _tokenize(search_query)
        query_norm = _normalize_text(search_query)

        for entry in active:
            if section_filters and entry.category not in section_filters:
                continue
            score = self._score_entry(entry, query_norm, query_tokens)
            if search_query and score <= 0:
                continue
            scored.append((score, entry))

        scored.sort(
            key=lambda item: (
                item[0],
                _parse_iso(item[1].updated_at) or datetime.min.replace(tzinfo=timezone.utc),
            ),
            reverse=True,
        )
        top = [entry for _, entry in scored[:8]]

        if top:
            now = _utc_now()
            for entry in top:
                entry.access_count += 1
                entry.last_accessed = now
            self.store.save(active, archive)

        if not top:
            if section_filters:
                section_text = ", ".join(section_filters)
                return f"No results found. (section filter: {section_text})"
            return "No results found."

        grouped: dict[str, list[MemoryEntry]] = {cat: [] for cat in CANONICAL_CATEGORIES}
        for entry in top:
            grouped.setdefault(entry.category, []).append(entry)

        lines = [f"Found {len(top)} result(s)"]
        for category in list(CANONICAL_CATEGORIES) + sorted(set(grouped) - set(CANONICAL_CATEGORIES)):
            entries = grouped.get(category, [])
            if not entries:
                continue
            lines.append(f"### {category}")
            for entry in entries:
                lines.append(
                    f"- {entry.id} | updated {entry.updated_at} | {_snippet(entry.content)}"
                )
            lines.append("")
        return "\n".join(lines).strip()

    def forget(self, memory_id: str) -> dict[str, str]:
        target_id = (memory_id or "").strip()
        if not target_id:
            return {"status": "error", "message": "id is empty"}

        active, archive = self.store.load()
        before_active = len(active)
        before_archive = len(archive)
        active = [entry for entry in active if entry.id != target_id]
        archive = [entry for entry in archive if entry.id != target_id]
        removed = (before_active - len(active)) + (before_archive - len(archive))

        if removed == 0:
            return {"status": "not_found", "message": f"{target_id} not found"}

        self.store.save(active, archive)
        return {"status": "deleted", "message": f"{target_id} removed"}

    def summarize(self) -> str:
        active, archive = self.store.load()
        moved = self._cleanup_stale(active, archive)
        self.store.save(active, archive)

        lines = [
            "memory.md summary",
            f"- active: {len(active)}",
            f"- archive: {len(archive)}",
            f"- cleaned this run: {moved}",
            "",
        ]

        for category in CANONICAL_CATEGORIES:
            entries = [entry for entry in active if entry.category == category]
            entries.sort(
                key=lambda item: _parse_iso(item.updated_at)
                or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True,
            )
            lines.append(f"## {category} ({len(entries)})")
            if not entries:
                lines.append("- (empty)")
            else:
                for entry in entries[:3]:
                    lines.append(f"- {entry.id}: {_snippet(entry.content, 120)}")
            lines.append("")

        return "\n".join(lines).strip()

    def _score_entry(self, entry: MemoryEntry, query_norm: str, query_tokens: set[str]) -> float:
        if not query_norm:
            return 1.0

        content_norm = _normalize_text(entry.content)
        facts_norm = _normalize_text(" ".join(entry.facts.values()))
        score = 0.0
        if query_norm in content_norm:
            score += 8.0
        if query_norm and query_norm in facts_norm:
            score += 3.0

        entry_tokens = _tokenize(entry.content + " " + " ".join(entry.facts.values()))
        overlap = len(query_tokens & entry_tokens)
        score += overlap * 2.0

        category_tokens = _tokenize(entry.category)
        score += len(query_tokens & category_tokens) * 1.5
        return score

    def _parse_filters(self, query: str) -> tuple[set[str], str]:
        filters: set[str] = set()
        cleaned = query
        for pattern in _SECTION_FILTER_PATTERNS:
            for matched in pattern.findall(query):
                filters.add(normalize_category(matched))
            cleaned = pattern.sub("", cleaned)

        for category in CANONICAL_CATEGORIES:
            if category in query:
                filters.add(category)
        return filters, cleaned.strip()

    def _find_best_duplicate(self, content: str, entries: list[MemoryEntry]) -> MemoryEntry | None:
        best: tuple[float, MemoryEntry] | None = None
        new_fp = _build_fingerprint(content)
        new_norm = _normalize_text(content)

        for entry in entries:
            if not entry.fingerprint:
                entry.fingerprint = _build_fingerprint(entry.content)
            if entry.fingerprint == new_fp:
                return entry

            sim = _jaccard_similarity(content, entry.content)
            if sim > 0.82:
                if best is None or sim > best[0]:
                    best = (sim, entry)
                continue

            existing_norm = _normalize_text(entry.content)
            if len(new_norm) > 24 and (new_norm in existing_norm or existing_norm in new_norm):
                if best is None:
                    best = (0.83, entry)

        return best[1] if best else None

    def _collect_conflicts(self, active: list[MemoryEntry], facts: dict[str, str]) -> list[_Conflict]:
        if not facts:
            return []

        conflicts: list[_Conflict] = []
        for entry in active:
            if not entry.facts:
                entry.facts = _extract_facts(entry.content)
            for key, new_value in facts.items():
                old_value = entry.facts.get(key)
                if not old_value:
                    continue
                if _normalize_text(old_value) == _normalize_text(new_value):
                    continue
                conflicts.append(
                    _Conflict(entry=entry, key=key, old_value=old_value, new_value=new_value)
                )
        return conflicts

    def _select_conflict_target(self, conflicts: list[_Conflict], preferred_category: str) -> MemoryEntry:
        preferred = [conf.entry for conf in conflicts if conf.entry.category == preferred_category]
        pool = preferred or [conf.entry for conf in conflicts]
        unique: dict[str, MemoryEntry] = {entry.id: entry for entry in pool}
        return max(
            unique.values(),
            key=lambda entry: _parse_iso(entry.updated_at)
            or datetime.min.replace(tzinfo=timezone.utc),
        )

    def _resolve_conflicts(
        self,
        active: list[MemoryEntry],
        archive: list[MemoryEntry],
        target: MemoryEntry,
        facts: dict[str, str],
        now: str,
    ) -> list[str]:
        conflicts = [conf for conf in self._collect_conflicts(active, facts) if conf.entry.id != target.id]
        return self._apply_conflict_resolution(active, archive, target, conflicts, now)

    def _apply_conflict_resolution(
        self,
        active: list[MemoryEntry],
        archive: list[MemoryEntry],
        target: MemoryEntry,
        conflicts: list[_Conflict],
        now: str,
    ) -> list[str]:
        if not conflicts:
            return []

        notes: list[str] = []
        seen_entries: set[str] = set()
        keep_ids = {target.id}

        for conflict in conflicts:
            note = (
                f"{conflict.key}: '{conflict.old_value}' -> '{conflict.new_value}' "
                f"(source {conflict.entry.id})"
            )
            notes.append(note)
            target.facts[conflict.key] = conflict.new_value

            if conflict.entry.id in keep_ids or conflict.entry.id in seen_entries:
                continue

            conflict.entry.superseded_by = target.id
            conflict.entry.archived_at = now
            seen_entries.add(conflict.entry.id)

        if notes:
            unique_notes = list(dict.fromkeys(notes))
            target.conflicts = list(dict.fromkeys([*target.conflicts, *unique_notes]))
            target.updated_at = now

        if seen_entries:
            moved = [entry for entry in active if entry.id in seen_entries]
            active[:] = [entry for entry in active if entry.id not in seen_entries]
            archive.extend(moved)

        return notes

    def _cleanup_stale(self, active: list[MemoryEntry], archive: list[MemoryEntry]) -> int:
        now = datetime.now(timezone.utc)
        now_text = now.replace(microsecond=0).isoformat()
        moved: list[MemoryEntry] = []

        for entry in active:
            if self._is_stale(entry, now):
                entry.archived_at = entry.archived_at or now_text
                if not entry.category:
                    entry.category = ARCHIVE
                moved.append(entry)

        if not moved:
            return 0

        moved_ids = {entry.id for entry in moved}
        active[:] = [entry for entry in active if entry.id not in moved_ids]
        archive.extend(moved)
        return len(moved)

    def _is_stale(self, entry: MemoryEntry, now: datetime) -> bool:
        if entry.superseded_by:
            return True

        updated = _parse_iso(entry.updated_at)
        if not updated:
            return False
        age_days = (now - updated).days
        if age_days <= self.stale_days:
            return False

        if entry.access_count >= 3:
            return False

        last_accessed = _parse_iso(entry.last_accessed)
        if last_accessed and (now - last_accessed).days <= max(7, self.stale_days // 2):
            return False
        return True
