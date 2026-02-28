# memmd-mcp (KOR)

한국어 요약 문서입니다. 기본 문서는 영어입니다.

- English README: [README.md](../README.md)

## 한 줄 설명

로컬 `memory.md`를 관리하는 Python MCP stdio 서버입니다.

## 주요 기능

- 중복 메모 자동 병합
- 모순(fact 충돌) 감지 및 정리
- 카테고리 구조화 (`Work Context`, `Projects`, `Personal Preferences`)
- 섹션/카테고리 필터 검색
- 오래된 정보 `Archive` 이동

## 툴

- `remember(content, category)`
- `recall(query)`
- `forget(id)`
- `summarize()`

## 빠른 실행

```bash
uvx memmd-mcp
```

## 설정 예시

```json
{
  "mcpServers": {
    "memmd": {
      "command": "uvx",
      "args": ["memmd-mcp"],
      "env": {
        "MEMMD_MEMORY_PATH": "/Users/you/memory.md",
        "MEMMD_STALE_DAYS": "120"
      }
    }
  }
}
```

자세한 설명, Claude Desktop/Cursor/Claude Code 예시는 영어 README를 참고하세요.
