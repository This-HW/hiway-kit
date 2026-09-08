# MCP 서버 활용 가이드

> 이 문서는 Claude Code에서 사용 가능한 MCP 서버들의 용도와 올바른 선택 방법을 설명합니다.
>
> **정본(SSOT): `plugins/common/rules/mcp-usage.md`.** 충돌 시 정본이 우선한다. 핵심 원칙:
> **MCP는 스킬(main 컨텍스트)에서만 쓰고, 배포 에이전트 frontmatter/산문엔 MCP를 넣지 않는다**
> — 미설치 소비자에게 환각을 유발하기 때문(CC #13898). 아래 예시는 그 원칙에 맞춰 갱신됨.

---

## 1. MCP 서버 7개 상세 설명

| MCP 서버                | 주요 용도                            | 사용 시점                             | 장점                                  | 단점/주의사항              |
| ----------------------- | ------------------------------------ | ------------------------------------- | ------------------------------------- | -------------------------- |
| **Context7**            | 라이브러리·프레임워크 공식 문서 조회 | API 문법, 설정 방법, 버전별 차이 확인 | 최신 문서 보장, 훈련 데이터 오류 방지 | 버전을 반드시 명시해야 함  |
| **Exa**                 | 시맨틱 코드/기술 검색                | 특정 기술 구현 패턴, 코드 예시 탐색   | 코드 컨텍스트 이해, 정밀한 기술 검색  | 일반 검색보다 느릴 수 있음 |
| **Tavily**              | 종합 리서치, 팩트 체킹, 기술 비교    | 라이브러리 비교, 보안 취약점 조사     | 광범위한 정보 수집, 출처 다양         | 정확도 검증 필요           |
| **Playwright**          | 동적 페이지 스크래핑, E2E 테스트     | JS 렌더링 필요 페이지, UI 자동화      | JavaScript 실행 가능, 브라우저 제어   | 정적 페이지엔 오버킬       |
| **Sequential Thinking** | 복잡한 다단계 설계·문제 분해         | 아키텍처 설계, 복잡한 알고리즘 계획   | 단계적 추론, 논리 체계화              | 단순 작업엔 불필요         |
| **PostgreSQL**          | DB 쿼리, 스키마 탐색, 쿼리 최적화    | 데이터 분석, 스키마 확인, 성능 튜닝   | 직접 DB 접근, 실시간 데이터           | SSH 터널 선행 필요         |
| **Magic (21st.dev)**    | 자연어 → UI 컴포넌트 생성            | 빠른 UI 프로토타이핑, 컴포넌트 제안   | 빠른 컴포넌트 생성                    | 프로덕션 코드 검토 필요    |

---

## 2. MCP vs 기본 도구 선택 플로우차트

```
작업 유형은 무엇인가?
         │
         ├─ 라이브러리/API 문서 확인
         │        │
         │        └─ (스킬/main에서) Context7 우선, 없으면 WebFetch 폴백
         │
         ├─ 코드/기술 검색
         │        │
         │        ├─ 정밀한 기술 쿼리? → Exa 사용
         │        └─ 일반 검색? → WebSearch 사용
         │
         ├─ 웹 페이지 접근
         │        │
         │        ├─ JS 렌더링 필요? → Playwright 사용
         │        └─ 정적 HTML? → WebFetch 사용
         │
         ├─ 리서치/팩트 체킹
         │        │
         │        └─ Tavily 사용
         │
         ├─ DB 조회
         │        │
         │        └─ PostgreSQL MCP 사용
         │           (반드시 db-tunnel.sh start 먼저)
         │
         └─ 복잡한 설계 문제
                  │
                  └─ Sequential Thinking 사용
```

---

## 3. 작업 유형별 MCP 선택 가이드

| 작업                           | 잘못된 선택              | 올바른 선택         | 이유                            |
| ------------------------------ | ------------------------ | ------------------- | ------------------------------- |
| Next.js App Router API 확인    | WebFetch (공식 문서 URL) | Context7            | 훈련 데이터가 구 버전일 수 있음 |
| React Hook 사용법              | WebSearch                | Context7            | 공식 문서가 가장 정확           |
| "zustand vs jotai 비교" 리서치 | WebSearch                | Tavily              | 종합적인 비교 분석에 적합       |
| SPA 페이지 데이터 스크래핑     | WebFetch                 | Playwright          | WebFetch는 JS 미실행            |
| 정적 블로그 포스트 읽기        | Playwright               | WebFetch            | Playwright는 오버킬             |
| DB 스키마 확인                 | Bash (psql 명령)         | PostgreSQL MCP      | MCP가 더 편리하고 안전          |
| 마이크로서비스 아키텍처 설계   | 즉시 구현                | Sequential Thinking | 단계적 설계가 먼저              |

---

## 4. 에이전트 vs 스킬: MCP는 어디에 두는가

**배포 에이전트 frontmatter에 `mcp__*` 툴을 넣지 않는다.** 소비자마다 MCP 설치가 다르고,
미설치 project-scoped MCP가 allowlist에 있으면 에이전트가 환각/hard-fail한다(CC #13898).
따라서:

- **MCP 의존 리서치·문서조회 → `web-research` 스킬.** 스킬은 main 컨텍스트에서 설치된 MCP를
  안전 상속하고, 미설치 시 빌트인 WebSearch/WebFetch로 폴백한다.
- **배포 에이전트는 빌트인 WebSearch/WebFetch만** 사용한다. 라이브러리 문서가 필요하면
  `web-research` 스킬로 위임한다 — 에이전트 frontmatter에 MCP를 배선하지 않는다.

```yaml
# 배포 에이전트 — MCP 미배선 (빌트인만)
---
name: implement-code
model: sonnet
tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
disallowedTools:
  - Task
# mcp__* 없음. 최신 라이브러리 문서가 필요하면 web-research 스킬로 위임.
---

# MCP 리서치가 필요하면 — 에이전트가 아니라 스킬로
# skills/web-research/SKILL.md (main 컨텍스트에서 MCP 안전 사용 + 폴백)
```

> 정본 규칙: `plugins/common/rules/mcp-usage.md` → "Agent MCP Configuration".

---

## 5. Context7 사용 시 버전 명시 규칙

Context7는 버전별로 다른 문서를 반환합니다. 버전을 생략하면 잘못된 API가 반환될 수 있습니다.

```
# 잘못된 예 — 버전 없음
"use context7 for Next.js App Router"
→ 어떤 버전인지 모름, 잘못된 문서 반환 가능

# 올바른 예 — 버전 명시
"use context7 for Next.js 15 App Router"
"use context7 for React 18 Hooks"
"use context7 for Prisma 5 Schema"
"use context7 for TypeScript 5.4 satisfies operator"
```

**버전 확인 방법:**

```bash
# package.json에서 버전 확인
cat package.json | grep '"next"\|"react"\|"typescript"'
```

---

## 6. PostgreSQL MCP 사용 전 절차

PostgreSQL MCP가 터널/프록시를 필요로 하면(예: DB가 로컬이 아닐 때) 사용 전에 먼저 기동한다.
이는 **환경별 설정이며, kit은 터널 스크립트를 제공하지 않는다**(정본 mcp-usage.md와 일치).
터널 기동 방법은 각 사용자의 환경 설정을 따른다.

**터널 없이(원격 DB) PostgreSQL MCP 사용 시:** 연결 오류 발생.

---

## 7. Context Window 최적화 가이드

MCP 도구는 컨텍스트를 소비합니다. 아래 원칙으로 효율을 높입니다.

| 원칙                     | 방법                                              |
| ------------------------ | ------------------------------------------------- |
| 스킬에서만 MCP 사용      | 배포 에이전트엔 MCP 미배선(정본 규칙) — 스킬이 상속·폴백 |
| 필요한 문서만 조회       | Context7에서 전체 문서 대신 특정 API만 검색       |
| 검색 결과 캐시 활용      | 같은 라이브러리 문서를 세션 내 반복 조회 금지     |

---

**제거된 절 (D-19, 2026-09-07)**: 특정 MCP 서버(NotebookLM)의 수치 제한을 규정하던
절을 제거했다 — 이 문서가 스스로 세운 "서버별 상세는 규범이 아니다, 필요한 스킬의
몫이다" 원칙과 모순이었다. 그 서버를 쓰는 스킬이 있다면 거기서 다룬다.
