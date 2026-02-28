from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class MemoryEntry:
    id: str
    category: str
    content: str
    created_at: str
    updated_at: str
    fingerprint: str
    facts: dict[str, str] = field(default_factory=dict)
    merge_count: int = 0
    access_count: int = 0
    last_accessed: str | None = None
    conflicts: list[str] = field(default_factory=list)
    superseded_by: str | None = None
    archived_at: str | None = None

    @classmethod
    def from_meta(cls, meta: dict[str, Any], content: str, fallback_category: str) -> "MemoryEntry":
        return cls(
            id=str(meta.get("id", "")),
            category=str(meta.get("category") or fallback_category),
            content=content.strip(),
            created_at=str(meta.get("created_at", "")),
            updated_at=str(meta.get("updated_at", "")),
            fingerprint=str(meta.get("fingerprint", "")),
            facts=dict(meta.get("facts") or {}),
            merge_count=int(meta.get("merge_count", 0)),
            access_count=int(meta.get("access_count", 0)),
            last_accessed=meta.get("last_accessed"),
            conflicts=list(meta.get("conflicts") or []),
            superseded_by=meta.get("superseded_by"),
            archived_at=meta.get("archived_at"),
        )

    def to_meta(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "fingerprint": self.fingerprint,
            "facts": self.facts,
            "merge_count": self.merge_count,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
            "conflicts": self.conflicts,
            "superseded_by": self.superseded_by,
            "archived_at": self.archived_at,
        }
