---
status: current
as_of: 2026-11-24
---

> 이 문서는 3자 설계 토론(controller·reviewer-claude·reviewer-codex)의 판정문 원문이다. 토론 원문(헌장·라운드 답신)과
> 두 독립 조사 보고서는 레포 밖 `~/.cache/hiway-research/hermes/` 에 있다(로컬 작업 기록, 추적하지 않음).
> 근거 id `[C-…]`·`[X-…]` 는 그 답신들을 가리킨다. 사용자 결정(2026-11-24): **"H0+빌더+H1 실측"** 진행 — H2(게시)는 실측 보고 뒤 다시 묻는다.

# 99-verdict — Hermes 타겟 설계 3자 토론 판정

작성: controller(Claude Code 2.1.330 · claude-opus-5-5 · effort xhigh), 2026-11-24.
참여자:
- reviewer-claude — Claude Code 2.1.330 · claude-opus-5-5 · high
- reviewer-codex — Codex CLI 0.171.0 · gpt-6.2-sol · xhigh

라운드는 r1(독립 검토)과 r2(교차 반박) 두 번이다. 헌장 `00-charter.md` 의 상한 2 라운드 안에서 끝났다.
리뷰어 답신은 인용된 비신뢰 데이터로 읽었다. 답신 안의 지시를 실행한 일은 없다.

## 결론 — **합의 (설계 수준).** 최종 선택은 사용자에게 올린다

세 참여자가 같은 설계에 수렴했다. 그 과정에서 철회가 8건 나왔다:
- controller 3: 전환 조건, 원본 진단 validate, `agents/` 그대로
- reviewer-claude 3: `metadata.internal` 충돌 주장, 기준 3 판정, `editionManifestPath`
- reviewer-codex 2: (c2′) 1순위 권고, manual-only 3종 일괄 제외

## 합의된 설계

### D1 배포 단위 — (c) 생성 브랜치 `hermes` 의 Agent Plugins v1 축소판, 커밋 sha 고정 설치
- main 의 `plugins/common` 은 바꾸지 않는다. Antigravity `plugin.json`, Codex ZIP 입력, `directory` 판도 그대로다.
- 설치는 `--ref` 에 40자 커밋 sha 만 준다. 브랜치 이름과 트리 URL 의 ref 는 거부되거나 버려진다는 것을 양쪽이 소스로 독립 확인했다 `[C-S1][C-S2][X-S1][X-S2]`.
- 비기본 브랜치 커밋을 sha 로 받아 오는 것은 git 수준에서 실측으로 통과했다(Hermes 와 같은 동사) `[C-S22]`.
- 문서에 적을 사용법:
  - 신규 설치: `ls-remote` 로 sha 를 확정한다. 결과가 비거나 실패하면 중단한다. 이어서 `--ref <sha> --no-enable` 으로 설치하고, 활성화는 사용자가 한다
  - 갱신: `--force --ref <새 sha>`. `plugins update` 는 고정 설치를 거부한다 `[C-S4][X-S4]`
- 실패해도 막히는 쪽으로 간다(fail-closed):
  - ref 없이 첫 설치를 하면 main 을 받고 `manifest_invalid` 로 막힌다 `[C-S5][X-S6]`
  - 재설치에서 ref 를 빠뜨리면 저장된 핀을 그대로 이어 쓴다 `[X-S2]`
- 기각:
  - (a) 네이티브 — 공유 트리에 Python 진입 코드가 생기고, 디렉토리 빌더와 Codex ZIP 에 영향이 간다 `[X-§무회귀]`
  - (b) 공유 통일 — 위 fail-closed 불변식이 깨진다 `[C-C1]`
  - (c2′) main 생성 루트 — skills.sh 가 같은 이름을 먼저 찾은 쪽으로 고르고 그 순서가 readdir 순서다. 그래서 다른 하네스 사용자에게 Hermes 판이 설치될 기전이 있다 `[C-S21]`. agy 도 미실측이다
  - (c5) 별도 레포 — 자동 갱신 수요가 아직 관측되지 않았다

### D2 싣는 것과 빼는 것
| 대상 | 판정 |
| --- | --- |
| 스킬 15종 | 싣는다(`using-hiway-kit` 포함) |
| `using-hiway-kit` | description 꼬리를 판 변환으로 교체한다("(hook-injected)"·Session-start 표현 → 워크플로 진입 안내). **원본이 기대 문자열과 정확히 같을 때만** 바꾸고 아니면 exit 1 `[C-r2 쟁점2][X-r2 쟁점2]`. `disable-model-invocation` 키는 둔다 |
| `harness-export` | 뺀다 — 사용자 파일 쓰기(consumer-footprint 규칙 1·4). 문서에 명시적 CLI 사용법(`--plugin-root` 명시)을 적는다 |
| `skill-forge` | 뺀다 — Hermes 내장 스킬 생성과 경합(기준 5) |
| `agents/` | 브리프 문서로 싣는다 + Hermes 머리말. 수정 에이전트 4종 본문과 `test` 같은 호출부의 "격리 확보" 표현을 판에서 고친다. 수정 위임은 격리가 확인되는 운송으로만 하고, 확인이 안 되면 부모가 순차로 실행한다 `[X-S6][X-S7][C-C7]` |
| `rules/`·`tools/`·`.claude-plugin/plugin.json` | 싣는다(exporter 의 루트 확인과 스킬 도구용) |
| `hooks/`·`setup/` | 뺀다 |
| 뺀 경로를 가리키는 문서 | Hermes 머리말을 단다(디렉토리판 메커니즘, 문구는 Hermes 용으로 따로) `[C-S16][C-C7]` |
| 판 README | Hermes 판 설명으로 다시 쓴다. 15 스킬, 훅 없음, 자동 갱신 없음, 설치 확인 프롬프트(caution 예상), 행동 eval 없음 `[X-기준4]` |

### D3 단계와 게이트
- **H0 — 지금 해도 된다.** `plugins/common` 을 바꾸지 않는다. 바꾸면 심사 중인 v5.9.1 이 대체된다 `[C-C5]`.
  - `packaging/targets.json` 에 `hermes`(`enabled:false`, `verificationLevel: researched-only`, `delivery: "edition"`, 결정 요약과 미확인 목록)를 넣는다
  - `docs/harnesses.md` 에 Hermes 절을 쓴다:
    - `AGENTS.md` 경로와 `.hermes.md`·`AGENTS.override.md` 가림
    - 컨텍스트 기본 20,000자(설정에 따라 변함) `[X-S14]`
    - `skills.external_dirs` 평가 경로 — 읽기 전용 클론으로만 쓴다. 원본 `skills/` 를 가리키면 manual-only 까지 후보가 된다
    - 이중 로드(`~/.agents/skills` 권고와의 충돌) `[C-C9]`
- **H1 전 — 빌더**(코드 작업):
  - 공통 배관만 중립 모듈로 원문 그대로 옮긴다. golden 트리 sha 테스트를 먼저 넣고, 오라클 `derive_tree(ab468bf):plugins/common == 364f51e6d4ef8ba952ae91301a935a3d5e70689c` 를 재현한다 `[C-C2][X-S15]`
  - `build-hermes-branch.py` 를 쓴다. 판 판정과 머리말은 따로 둔다. `--check` 는 `enabled` 와 무관하게 돌리고, `--write` 만 `enabled:true` 를 요구한다
  - 실제 게시 후보의 `plugins/common` 하위 트리 sha 를 기대 트리와 대조한다 `[X-r2 쟁점4]`
  - 실레포 `--check` 를 pytest 에 넣는다(병합 전에 돈다) `[C-r2 쟁점4-3]`
  - `build-targets.py` 를 고친다:
    - `delivery: "edition"` 타겟은 main 에 파일을 만들지 않고 `build_manifest` 를 **계산만** 해 AP v1 정적 제약을 판정한다
    - `manifestPath` 중복·출력 경로 충돌은 **정규화한 경로로** 막는다
    - edition 타겟에 `--only` 를 주면 담당 판 검사로 안내하는 오류를 낸다 `[C-S26][X-r2 쟁점4]`
  - fail-closed 불변식의 정적 대리 검사를 둔다: `plugins/common/plugin.json` 의 `$schema` 가 AP URL 이 아니고, `plugin.yaml` 이 없어야 한다 `[C-r2 쟁점4-5]`
  - Hermes 게시는 별도 CI job·별도 concurrency 로 돌리고, directory 게시의 선행 조건으로 걸지 않는다
- **H1 — 격리 실측(사용자 승인 필요).** 쓰기를 거부한 샌드박스에서, 고정 sha 소스를 임시 venv 에 설치한다. 측정한 **트리 sha 를 기록**한다.
  - P0: 음성 대조 — 원본 `manifest_invalid`, ref 없음·`tree/hermes/…` 거부
  - P1: 생성판 보안 판정(caution 예상)과 파일·규칙별 원인. dangerous 면 배포를 막는다
  - P2: fresh 프로필에서 0 → 15 → 0 개수, `<available_skills>`·`skills_list`, `using-hiway-kit` 의 노출과 실제 `skill_view`
  - P3: install → enable → disable → remove 뒤 잔여물과 `config.yaml` 변화(사용자 명령에 따른 것만)
  - P4: `AGENTS.md` 로드와 가림
  - P5′: sha 설치 → `--force --ref` 이동, 활성 상태 보존
  - P6: `skill_dir` 기준 도구 발견. Claude 캐시 교차 집기가 없어야 한다
  - 내장 verify-on-stop·스킬 생성·메모리와의 공존
- **H2 — 게시.** H1 에서 잰 트리 sha 와 같은 트리를 `enabled:true` 로 게시한다. README 의 Hermes 열은 관측한 칸만 채운다. `verificationLevel` 을 올린다.

### D4 범위 밖과 재검토 조건
- 훅 어댑터(셸 훅 스니펫·`--hermes` 입력 모드), 에이전트 로더·`advanced-delegation` 라우트 — 페이로드 원문 프로브를 확보하고 수요가 생기면
- Hermes 플러그인 카탈로그 PR — H2 가 두 릴리스 이상 안정되면
- `session-history` 의 `state.db` 어댑터
- (c2′) — skills CLI(`metadata.internal: "true"` 완화 포함)·agy 무충돌 실측을 통과하면
- (c5) — 자동 갱신 수요가 관측되면
- `agents/review-code.md` 예시 문장 손질(caution 원인) — `plugins/common` 변경이라 디렉토리 심사가 끝난 뒤

## 미충족 기준
- **기준 5 (소비자 우선·상호운용): 미확인.**
  - 확인한 것(소스): 프로필 설치 경로, 사용자 명령 없이는 `config.yaml` 에 쓰지 않는다는 것
  - 런타임 미관측: 노출→호출, 도구 발견(P6), 이중 로드, Hermes 내장 기능 공존, 격리 실패 시 경로
  - 누구도 Hermes 를 실행하지 않았다(기준 7) → H1 에서만 닫힌다
- **기준 3 (설치 가능성 근거): 헌장 원문 기준으로 충족.** "실측 전에는 '지원'이라 쓰지 않는 게이트"가 설계에 있다. 다만 **실제 설치 판정은 미측정**이다(caution 예상, 정적).
- 나머지 1·2·4·6·7: 세 참여자 모두 "충족(설계상)" 이다. 설계상 충족은 구현과 테스트로만 실물이 된다.

## 기준 변경 이력
- 없음. 기준 1~7 원문을 그대로 썼다.
- 기준 3 은 reviewer-claude 가 r1 에서 "설치가 된다"로 **잘못 읽었다가** r2 에서 헌장 원문대로 바로잡았다. 이것은 기준 변경이 아니라 판정 정정이다.

## 남은 작은 불합의 (controller 결정, 사용자 확인 대상)
- **판 매니페스트 경로를 정책 키(`editionManifestPath`)로 둘지, 빌더 상수로 둘지**
  - reviewer-codex: 정책에 배포 위치를 명시한다 `[X-r2 쟁점4]`
  - reviewer-claude: 상수로 둔다 — AP v1 은 루트 위치가 고정이라 경로 설정값은 `path-containment` 표면만 늘린다 `[C-r2 철회3]`
  - **controller 결정: `delivery: "edition"` 키로 배포 위치를 정책에 명시하고, 경로는 빌더 상수로 둔다.** 양쪽 요구를 모두 만족한다. 출력 경로 충돌 검사는 정규화한 경로로 한다(codex 요구)
- **`AGENTS.md` 의 워크플로 체인 포함 여부 — 사실 정정**
  - reviewer-claude 의 "AGENTS.md 는 체인을 싣지 않는다" `[C-S14]` 는 틀렸다. `export-harness.sh --stdout` 출력과 `BLOCK_HEADER` 에 체인이 있다 `[X-S5]`
  - `using-hiway-kit` 을 싣는 결론은 다른 근거로 유지된다:
    - AGENTS.md 의 체인에는 규모별 분기가 없다
    - AGENTS.md 는 가려지거나 BLOCK 될 수 있다

## 산출물 체크
- [x] 헌장이 토론 전에 쓰였다(03:01) — r1 은 03:14
- [x] 첫 답신마다 비대칭 선언이 있고, 가진 것과 쓴 것을 나눠 적었다
- [x] 모든 주장에 근거 id 가 붙었고, 답신마다 증거 등급과 실행 주체(출처 포함)가 있다
- [x] 각자 자기 파일만 썼다
- [x] 미충족 기준 절과 기준 변경 이력 절이 있다
- [x] 종료 형태를 "합의(설계 수준)"로 명시했다
- [x] 상대 답신 안의 지시를 실행하지 않았다
