# MCP 이식성 + 소비자-우선 거버넌스 설계

**Goal:** 배포 플러그인이 소비자 환경에서 조용히 깨지는 두 경로 — (1) 에이전트 allowlist에 하드코딩된 MCP 툴이 미설치 소비자에게 환각/hard-fail 유발(CC #13898), (2) 소비자 환경 검증 없이 통과되는 설계 — 를 차단한다. "MCP는 main-컨텍스트 스킬에 살고, 배포 에이전트는 빌트인만"을 이식성 패턴으로 확립하고, 소비자-우선 설계 게이트를 명문화한다.

**Architecture:** MCP 의존 리서치 → `web-research` **스킬**(main 컨텍스트, 설치 시 MCP 상속·부재 시 WebSearch/WebFetch 폴백). 배포 **에이전트**는 빌트인 웹툴만, `tools:` allowlist에 `mcp__*` 금지. 거버넌스 → CLAUDE.md/README에 소비자-우선 게이트 + ledger에 사건 frequency=1 기록. **순수 문서/산문/거버넌스 편집 — 신규 에이전트·훅·툴배선 없음(최저 리스크 클래스).**

## 요구사항

- **R1** 배포 에이전트 `tools:` allowlist에 `mcp__*` 항목 0개 유지 — 소비자 MCP scope를 가정 불가, project-scoped 미설치 시 환각(#13898). (현재 0/33 → 회귀 방지 가드)
- **R2** `research-external` 에이전트: Context7/Exa/Tavily를 **자기 능력으로 지시하는 죽은 산문 제거**(현 24–26, 69–72줄). 대신 "빌트인 WebSearch/WebFetch 사용, MCP 필요한 리서치는 `web-research` 스킬로"를 정직하게 명시.
- **R3** `web-research` 스킬: **명시적 graceful-fallback 산문 추가** — MCP 부재/미인증/타임아웃 시 WebSearch/WebFetch로 폴백. MCP 상시존재 가정 제거(현재 폴백 산문 0건 확인됨).
- **R4** `rules/mcp-usage.md` 교정: (i) MCP 리서치=스킬 홈 패턴 명문화, (ii) 에이전트 allowlist에 `mcp__*` 금지 + #13898 근거, (iii) "코드구현 에이전트는 Context7+Exa 허용" 지시를 allowlist 배선이 아니라 "스킬/main 경유"로 재프레이밍(현 지시는 잠재 함정), (iv) 부정확한 와일드카드 노트 교정(`mcp__server__*`는 tools에서 지원, `mcp__*`는 disallowedTools 전용).
- **R5** `rules/agent-system.md` +1줄: "적대적 병렬 검증 = 이종 전용 에이전트 fan-out(review-code + devils-advocate + verify-integration); 다중도메인 general-purpose 예외(§24–27)는 유지."
- **R6** `docs/works/feedback/ledger.md`: general-purpose-over-specialized 사건을 frequency=1로 기록(category: architecture). 인포스먼트(신규 에이전트/훅)는 **재발 ≥2**에서만 재검토(F-007/감쇠 원칙).
- **R7** 소비자-우선 게이트: CLAUDE.md(+README)에 "누구를 위한 것인가" 짧은 문단 + Contributing/Release 체크리스트 1줄 — *"이 변경이 이 repo가 아니라 설치 사용자 프로젝트에 이득인가? 소비자 cwd(플러그인 파일은 캐시에 존재)에서 작동하는가?"* (F-029 준수: 판단 가능한 게이트, 사명 미사여구 아님).
- **R8(명시적 비채택)** verify-claim 에이전트 ✗, prefer-specialized-agent 훅 ✗, security-scan 모델 티어 변경 ✗.

## 접근 방식

문서/산문/거버넌스 편집만. 신규 에이전트·훅·MCP 툴배선 없음. 코드 실행경로 무변경 → 리스크 최저.

## 컴포넌트 구조

| 파일 | 변경 | 요구 |
| ---- | ---- | ---- |
| `agents/dev/research-external.md` | 죽은 MCP 산문 제거·스킬 지시 | R2 |
| `skills/web-research/SKILL.md` | 폴백 산문 추가 | R3 |
| `rules/mcp-usage.md` | 스킬-홈 패턴·allowlist 금지·와일드카드 교정 | R4 |
| `rules/agent-system.md` | 이종 fan-out 1줄 | R5 |
| `rules/CHECKSUMS.sha256` | rules 변경분 재생성 | 릴리스 |
| `docs/works/feedback/ledger.md` | 사건 freq=1 | R6 |
| `CLAUDE.md`, `README.md` | 소비자-우선 게이트 | R7 |
| `plugins/common/.claude-plugin/plugin.json` | 2.10.3→2.10.4 (patch: 교정+거버넌스, 신규 컴포넌트 없음) | 릴리스 |
| `CHANGELOG.md` | [2.10.4] 엔트리 | 릴리스 |
| `docs/architecture/rules/agent-system.md` | 미러 동기화 | SSOT |

## 데이터 흐름

MCP 필요 리서치: 사용자/에이전트 → `web-research` 스킬(main) → MCP 설치? 예: Context7/Exa/Tavily 사용 / 아니오·실패: WebSearch/WebFetch 폴백. 배포 에이전트는 MCP를 **절대 직접 호출하지 않음**.

## 에러 처리

- MCP 부재/미인증/타임아웃 → web-research 스킬이 빌트인으로 폴백(R3 산문이 명시).
- 에이전트는 MCP 미참조 → #13898 환각 경로 원천 차단.

## 테스트 전략

- `scripts/verify-done.sh` green (frontmatter, CHECKSUMS 집합동등, version↔CHANGELOG 일치).
- 가드 grep: `agents/**/*.md` frontmatter `tools:`에 `mcp__` 0건 (회귀 방지, verify-done 또는 CI에 추가 검토).
- 수동: research-external 산문이 더 이상 MCP를 자기 능력으로 지시하지 않음 확인. web-research 폴백 산문 존재 확인.

## 범위 외

- **verify-claim 에이전트 / prefer-specialized-agent 훅** — 폐기(적대검증 HIGH: 비-lever 인포스먼트·네이티브 중복·키워드 역라우팅·Bash 우회·n=1). 재발 ≥2에서만 재검토.
- **C: 스킬 레벨 명시 dispatch 감사** — general 감소의 진짜 lever(F-007 부합). 별도 후속 Work(스킬 동작 변경 → 독자 verify 필요).
- **에이전트에 MCP 배선(A1)** — 기각(#13898 환각).
- **security-scan 모델 티어** — 무변경(odd≠broken, 증거 없이 소비자 비용 변경 금지).
