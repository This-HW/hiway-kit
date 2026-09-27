---
name: mcp-builder
description: Build and configure MCP servers. Use when scaffolding a new Model Context Protocol server or adding tools to an existing one.
---

# MCP Server Builder

> Model Context Protocol 서버 개발 및 구성

MCP 서버를 생성하고 Claude Code에 통합합니다.

---

## 사용법

### 신규 MCP 서버 생성

```
/mcp-builder "파일 시스템 접근" filesystem
/mcp-builder "데이터베이스 조회" database-query
/mcp-builder "API 통합" external-api
```

### 기존 MCP 서버 설정

```
/mcp-builder setup postgres
/mcp-builder configure playwright
```

---

## MCP 서버 유형

### 1. Tools 서버

외부 도구 및 API 접근:

- 데이터베이스 쿼리
- 파일 시스템 조작
- 외부 API 호출
- 시스템 명령 실행

### 2. Resources 서버

정적 리소스 제공:

- 문서 검색
- 설정 파일 읽기
- 템플릿 제공

### 3. Prompts 서버

사전 정의된 프롬프트:

- 재사용 가능한 질의
- 템플릿 프롬프트

---

## 개발 워크플로우

### 1. 프로젝트 초기화

```bash
# Python MCP 서버
mkdir mcp-server-myproject
cd mcp-server-myproject
python -m venv venv
source venv/bin/activate
pip install mcp
```

### 2. 서버 구조 생성

```
mcp-server-myproject/
├── src/
│   ├── __init__.py
│   └── server.py           # MCP 서버 구현
├── pyproject.toml          # 의존성
└── README.md               # 사용법
```

### 3. Tools 정의

```python
from mcp import Server, Tool

server = Server("myproject-server")

@server.tool()
async def my_tool(arg1: str, arg2: int) -> str:
    """도구 설명"""
    # 구현
    return result
```

### 4. 서버 실행

```python
if __name__ == "__main__":
    server.run()
```

---

## Claude Code 통합

### 1. 서버 등록

`claude mcp add` 로 등록한다 — 사용자 범위는 `~/.claude.json`, 프로젝트 범위는 `.mcp.json` 에 기록된다
(플래그는 버전마다 다르니 `claude mcp add --help` 로 확인).

```bash
claude mcp add myproject -- python -m mcp_server_myproject
```

서버가 비밀값을 필요로 하면 사용자가 직접 넣게 한다 — 플러그인·스킬이 사용자 머신의 자격증명을 읽어
대신 넘기지 않는다. 플러그인으로 배포할 때는 `user_config` 의 `sensitive: true` 옵션으로 받는다.

### 2. 서버 시작

```bash
claude mcp list           # MCP 서버 목록 확인
claude mcp --help         # 가용 서브커맨드 확인(버전마다 달라질 수 있음)
```

---

## 템플릿

### Python MCP Tools 서버

```python
from mcp import Server
from typing import Any

server = Server("example-server")

@server.tool()
async def example_tool(
    param1: str,
    param2: int = 10
) -> dict[str, Any]:
    """
    Example tool description.

    Args:
        param1: First parameter
        param2: Second parameter (default: 10)

    Returns:
        Result dictionary
    """
    return {
        "result": f"Processed {param1} with {param2}",
        "status": "success"
    }

if __name__ == "__main__":
    server.run()
```

### Python MCP Resources 서버

```python
from mcp import Server

server = Server("docs-server")

@server.resource("docs://guide")
async def get_guide() -> str:
    """Return user guide"""
    return "User guide content..."

if __name__ == "__main__":
    server.run()
```

---

## 베스트 프랙티스

### 에러 처리

```python
@server.tool()
async def safe_tool(param: str) -> dict:
    try:
        result = await risky_operation(param)
        return {"result": result, "error": None}
    except Exception as e:
        return {"result": None, "error": str(e)}
```

### 설정값

서버 설정은 시작 시 한 번 읽고, 필수 값이 없으면 **바로 실패**시킨다(도구 호출 도중에 발견하지 않도록).
값의 이름은 서비스에 맞춰 짓고, 비밀값은 위 "서버 등록" 절처럼 사용자가 넣게 한다.

---

## 디버깅

### 서버 로그 확인

```bash
# 가용 서브커맨드 확인(상태 확인 방법은 버전마다 다르다)
claude mcp --help

# 수동 테스트
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python -m mcp_server_myproject
```

---

## 관련 리소스

- MCP 명세·SDK 는 버전이 빠르게 바뀐다 — 최신 문서는 설치된 문서 MCP(Context7 등)나 웹 검색으로 확인한다
  (공식 SDK 저장소: `modelcontextprotocol/python-sdk`, `modelcontextprotocol/typescript-sdk`)
