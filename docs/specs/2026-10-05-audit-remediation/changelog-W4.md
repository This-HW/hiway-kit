---
status: historical
as_of: 2026-10-05
---

W4(게이트) CHANGELOG 조각 — 컨트롤이 5.4.0 항목으로 조립한다(이 파일은 조립 재료이며 릴리스 노트가 아니다).

### Added — 문서 정합 게이트 3종 (전수 감사 A·B·C 후속, 스펙 D13)

- **`scripts/check_doc_refs.py` (`verify-done.sh §27` + CI)** — 문서가 가리키는 대상이 **실제로 있는가**.
  마크다운 링크·`@import`·슬래시 든 백틱 경로·백틱 `*.sh`/`*.py` 이름·`snake_case()`/`def` 함수명을
  추적 파일 트리와 코드 정의에 대조한다. 감사가 33/0 green 인 채로 낸 P0 급 사실 오류(B-P0-4 지워진
  `db-tunnel.sh`, 옮겨진 `hooks/checklist.py` 계열 …)가 전부 이 구멍이었다. 펜스 코드블록도 **이 레포
  소유로 보이는 경로·`.sh` 이름**은 본다(트리 그림 안의 죽은 스크립트 — `docs/architecture/rules/mcp-usage.md`).
  제외는 대상을 나열하지 않고 **제외를 나열**한다: `status: historical|superseded`·CHANGELOG·eval 픽스처·
  자리표시자·소비자 쪽 경로·gitignore 산출 디렉토리·줄 단위 `doc-ref-ok`·(파일, 참조) 쌍 `ALLOWED_REFS`
  (이유 필수, 안 쓰이면 노랑으로 알린다).
- **`scripts/check_doc_status.py` (`verify-done.sh §28` + CI)** — ① 모든 `docs/**/*.md` 의 frontmatter 가
  `status`(`current|historical|proposal|superseded`)·`as_of`(`YYYY-MM-DD`)·(`superseded` 면)
  `superseded_by`(추적 파일, 레포 안) 스키마를 따르는가(스펙 D0-2). ② `current` 문서와 `docs/` 밖 살아있는
  문서에 **제거된 이름**(`agents/(dev|meta|planning)/`·`hooks/(checklist|feedback_ledger|export_harness)`·
  `docs/works`·`work.sh`·`W-0xx`·구 플러그인 이름)이 없고, **GFM 표의 열 수**가 헤더와 같은가
  (이스케이프하지 않은 `|` 는 코드 스팬 안에서도 구분자다 — 감사 B-P2-1).
- **`check_injection_budget.py` 다섯째 축 (§16, CI 이미 호출)** — 하네스가 파일째 읽는 진입점
  (`AGENTS.md`·`GEMINI.md`)이 `export_harness.ENTRYPOINT_SOFT_CAP`(24 KiB) 안인가. 목록과 상한 모두
  `export_harness.py` 가 소유하고 게이트는 그것을 읽는다. `§15` 는 `AGENTS.md` 만 봤다 — `GEMINI.md`
  는 "내용이 같으니 크기도 같을 것"이라는 가정이었다(감사 C-M2).
- 세 게이트 모두 red 메시지에 **고치는 법 한 줄**(→)을 싣는다(감사 C-M3), 각 위반 종류마다 의도적 위반
  픽스처 → red / 고친 픽스처 → green 테스트를 `scripts/tests/` 에 둔다.

### Fixed — 구 이름 검사가 CHANGELOG 머리말을 가렸다 (감사 B-P2-3)

- `packaging/name-targets.json` 의 `oldNameScanExclude` 가 `CHANGELOG.md` 를 **통째로** 빼서, 머리말
  3행("All notable changes to <구 이름>")이 현재형으로 구 이름을 말해도 `§20` 이 못 잡았다. 이제 새 키
  `oldNameScanExcludeFrom` 으로 **첫 항목(`## [`) 앞의 머리말은 검사하고 항목 본문만** 제외한다.
  마커가 파일에 없으면 파일 전체를 검사한다. (`scripts/check_old_names.py` 가 키를 읽는다.)

### Changed — 낡은 주석 정정 (감사 B-P3-8)

- `verify-done.sh` §18 주석의 "§17 은 D-22 몫으로 예약"(§17 은 이미 사용 중)과 `sync-rule-mirror.sh` 의
  "(9개)"(실제와 다름 — 개수는 `MIRROR.sha256` 이 소유한다)를 고쳤다.
