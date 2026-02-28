# memmd-mcp

[English](../README.md) | [한국어](README.ko.md)

[![PyPI](https://img.shields.io/pypi/v/memmd_mcp)](https://pypi.org/project/memmd-mcp/)
[![License](https://img.shields.io/pypi/l/memmd_mcp)](https://pypi.org/project/memmd-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/memmd_mcp)](https://pypi.org/project/memmd-mcp/)

<p align="center">
  <img src="../assets/memmd-mcp.webp" alt="memmd-mcp" width="600">
</p>

AI 에이전트를 위한 공유 메모리 레이어 — 하나의 `memory.md`를 Claude Desktop, Cursor, Claude Code, OpenAI Codex 등 모든 MCP 클라이언트에서 공유합니다. 자동 중복 제거, 모순 해결, 오래된 항목 정리를 포함합니다.

> [!TIP]
> **왜 memmd?**
> - **하나의 기억, 모든 클라이언트** — Claude Desktop, Cursor, Claude Code, OpenAI Codex가 같은 `memory.md`를 공유
> - `mcp` 외 외부 의존성 제로 — 임베딩 없음, API 키 없음, 완전 오프라인
> - 결정론적, 규칙 기반 — 메모리 관리에 LLM 호출 없음
> - 사람이 읽을 수 있는 `memory.md` — 언제든 직접 확인하고 편집 가능

## 기능

- **중복 제거** — 핑거프린트 + Jaccard 유사도로 거의 동일한 항목 병합
- **모순 해결** — 충돌하는 사실 감지, 최신 값 유지, 이전 항목 아카이브
- **구조화된 카테고리** — Work Context · Projects · Personal Preferences · Archive
- **섹션 기반 검색** — 카테고리 필터, 키워드 점수 기반 검색
- **오래된 항목 정리** — `summarize()` 시 오래되고 사용되지 않는 항목 자동 아카이브
- **한국어 지원** — 카테고리 별명, 사실 패턴 (`~는 ~`), 불용어

## 빠른 시작

### 설치 및 실행

```bash
uvx memmd-mcp
```

### MCP 클라이언트에 추가

```json
{
  "mcpServers": {
    "memmd": {
      "command": "uvx",
      "args": ["memmd-mcp"],
      "env": {
        "MEMMD_MEMORY_PATH": "/absolute/path/to/memory.md"
      }
    }
  }
}
```

> [!NOTE]
> 클라이언트별 설정 파일 위치:
> - **Claude Desktop** — `~/Library/Application Support/Claude/claude_desktop_config.json`
> - **Claude Code** — `.claude/settings.json` 또는 사용자 설정
> - **Cursor** — `~/.cursor/mcp.json`
> - **OpenAI Codex** — `~/.codex/config.toml`

## 도구

| 도구 | 설명 |
|---|---|
| `remember(content, category?)` | 자동 중복 제거 및 모순 병합으로 저장 |
| `recall(query)` | 키워드 점수 및 카테고리 필터로 검색 |
| `forget(id)` | ID로 삭제 |
| `summarize()` | 카테고리 요약 + 오래된 항목 정리 |

## 작동 방식

### `remember`
- SHA-1 핑거프린트와 Jaccard 유사도(>0.82)로 중복 제거
- `key: value`, `key = value`, `key is value`, `key는 value` 패턴에서 사실 추출
- 충돌 시: 최신 값 적용, 이전 항목은 이력과 함께 아카이브

### `recall`
- 토큰 겹침 기반 키워드 검색
- 필터: `category:Projects API token`, `section:"Work Context" deploy`
- 한국어 별명 지원 (`category:프로젝트`)

### `summarize`
- 카테고리별 최근 항목 요약
- 오래된 항목 아카이브 (기본: 120일 초과, 접근 3회 미만, 최근 recall 없음)

## `memory.md` 형식

```md
# memory.md

<!-- memmd:version=1 -->

## Work Context
<!-- memmd-entry {...json...} -->
메모리 내용

## Projects
...

## Personal Preferences
...

## Archive
...
```

## 환경 변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `MEMMD_MEMORY_PATH` | `./memory.md` | 메모리 파일 경로 |
| `MEMMD_STALE_DAYS` | `120` | 오래된 항목 정리 기준 일수 (최소: 7) |

## 라이선스

MIT
