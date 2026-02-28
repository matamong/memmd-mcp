from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .logic import MemoryManager
from .storage import MemoryStore

app = FastMCP("memmd-mcp")


def _memory_path() -> Path:
    raw = os.getenv("MEMMD_MEMORY_PATH", "memory.md")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _stale_days() -> int:
    raw = os.getenv("MEMMD_STALE_DAYS", "120")
    try:
        return max(7, int(raw))
    except ValueError:
        return 120


def _manager() -> MemoryManager:
    return MemoryManager(store=MemoryStore(_memory_path()), stale_days=_stale_days())


@app.tool()
def remember(content: str, category: str = "Work Context") -> str:
    """Add memory content with automatic dedupe/contradiction merge."""
    result = _manager().remember(content=content, category=category)
    status = result.get("status", "unknown")
    if status == "error":
        return f"error: {result.get('message', '')}"
    return (
        f"{status}: {result.get('message', '')}"
        f" | id={result.get('id', '-')}"
        f" | category={result.get('category', '-')}"
    )


@app.tool()
def recall(query: str) -> str:
    """Search memory entries with optional section/category filters."""
    return _manager().recall(query=query)


@app.tool()
def forget(id: str) -> str:
    """Delete a memory entry by ID."""
    result = _manager().forget(memory_id=id)
    return f"{result.get('status')}: {result.get('message')}"


@app.tool()
def summarize() -> str:
    """Summarize memory by category and archive stale entries."""
    return _manager().summarize()


def main() -> None:
    app.run(transport="stdio")


if __name__ == "__main__":
    main()
