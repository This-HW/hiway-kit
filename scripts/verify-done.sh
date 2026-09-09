#!/usr/bin/env bash
#
# verify-done.sh — Definition of Done 완료 게이트 (Spec 6 / W-010)
#
# "완료"를 판단이 아니라 명령의 출력으로 만든다. 모든 기계 검사를 통합 실행하고,
# 하나라도 FAIL이면 비정상 종료(완료 불가). 수동 DoD 항목은 체크리스트로 출력한다.
#
# 사용: scripts/verify-done.sh
# 종료코드: 0 = 모든 기계 검사 통과, 1 = 하나 이상 실패 (완료 주장 금지)
#
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT" || exit 1

# 임시 출력은 예측가능한 /tmp 고정 이름(심링크 선점 위험) 대신 per-run mktemp 디렉토리.
TMPD="$(mktemp -d "${TMPDIR:-/tmp}/ckkit-verify.XXXXXX")" || exit 1
trap 'rm -rf "$TMPD"' EXIT

PASS=0
FAIL=0
green() { printf '  \033[32m✓\033[0m %s\n' "$1"; PASS=$((PASS + 1)); }
red()   { printf '  \033[31m✗ %s\033[0m\n' "$1"; FAIL=$((FAIL + 1)); }
hdr()   { printf '\n\033[1m%s\033[0m\n' "$1"; }

# Python 선택 — pytest 가용 인터프리터 탐색
PYTEST_PY=""
# 후보에 /tmp 경로를 넣지 말 것: world-writable + 예측 가능한 이름이라 아무 로컬
# 사용자나 인터프리터를 심어 게이트 실행자의 권한으로 코드를 돌릴 수 있다. 아래 임시
# 디렉토리를 mktemp로 잡는 것과 같은 이유다 — 실행 대상이면 위험은 오히려 더 크다.
# venv가 레포 밖에 있으면 activate해서 `python3` 후보로 잡히게 하면 된다.
for cand in ".venv/bin/python" "venv/bin/python" "python3"; do
  if "$cand" -c "import pytest" 2>/dev/null; then PYTEST_PY="$cand"; break; fi
done

# ── 섹션 번호 규약 (2026-08-27 확정) ────────────────────────────────────────────
# **섹션 번호는 안정 식별자다. 실행 순서를 나타내지 않는다.**
#
# 출력 순서가 1..10, 13, 12, 11, 14 로 비단조인 것은 흠이 아니라 의도다. 검사는 비용이
# 싼 순서로 실행되고, 번호는 그와 무관하게 고정된다. §11(AGENTS.md 드리프트)은
# 언제 실행되든 영원히 §11이다.
#
# 왜 재번호하지 않는가: 이 번호들은 스펙·CHANGELOG·decision-log·스킬 문서에서
# **참조 식별자로 쓰인다**(2026-08-27 기준 47건 이상). 그중 상당수는 과거 결정을 기록한
# 불변 문서다 — 재번호하면 "verify-done.sh §11 신설"처럼 이미 확정된 서술이 다른 섹션을
# 가리키게 된다. 표시 순서를 고치자고 기록의 참조를 깨는 것은 부채를 갚는 게 아니라
# 옮기는 것이다.
#
# 새 섹션은 **다음 빈 번호**를 받는다. 기존 번호를 재사용하거나 재배치하지 말 것.
# ───────────────────────────────────────────────────────────────────────────────

hdr "1. JSON 유효성"
JSON_FILES=$(find plugins -name 'plugin.json' -o -name 'hooks.json' 2>/dev/null; echo ".claude-plugin/marketplace.json")
for f in $JSON_FILES; do
  [ -f "$f" ] || continue
  if python3 -c "import json;json.load(open('$f'))" 2>/dev/null; then :; else red "JSON invalid: $f"; fi
done
[ "$FAIL" -eq 0 ] && green "all JSON valid"

hdr "2. plugin.json 필수 필드 + agent frontmatter + 금지 필드 (CI 동등)"
python3 - <<'EOF' && green "manifest + frontmatter checks" || red "manifest/frontmatter check failed"
import json, pathlib, re, sys
REQ = ["name","version","description","homepage","repository","license"]
FORB = ["permissionMode","context_cache","output_schema","next_agents","hooks"]
err = []
for f in pathlib.Path("plugins").glob("*/.claude-plugin/plugin.json"):
    d = json.loads(f.read_text())
    err += [f"{f}: missing {k}" for k in REQ if k not in d]
    a = d.get("author", {})
    if not isinstance(a, dict) or "email" not in a: err.append(f"{f}: missing author.email")
for f in pathlib.Path("plugins").rglob("*.md"):
    if "/skills/" in str(f) or "/rules/" in str(f): continue
    c = f.read_text()
    if not c.startswith("---"): continue
    end = c.find("---", 3)
    if end == -1: continue
    fm = c[3:end]
    if "name:" not in fm: err.append(f"{f}: no name")
    if "description:" not in fm: err.append(f"{f}: no description")
    err += [f"{f}: forbidden {x}" for x in FORB if re.search(rf"^{x}:", fm, re.M)]
if err:
    print("\n".join("    " + e for e in err)); sys.exit(1)
EOF

hdr "3. ruff (레포 전체 — 룰셋은 ruff.toml SSOT)"
# 대상을 나열하지 않는다: `ruff check .` + 루트 ruff.toml(exclude 포함)이 범위의 단일
# 소스다. CI도 동일 커맨드를 쓴다 — 목록을 양쪽에 복제하면 드리프트가 난다(F-023·F-036).
# 설정 파일 자체가 게이트의 전제다 — 사라지면 ruff가 개발자 전역 설정으로 조용히
# 폴백해 "로컬 green·CI red"가 부활한다. 전제 소실을 pass로 넘기지 않는다(F-022).
[ -f ruff.toml ] || red "ruff.toml 없음 — 전역 설정 폴백 위험(린트 SSOT 소실)"
[ -f .ruff-version ] || red ".ruff-version 없음 — CI ruff 설치가 핀을 잃는다"
if command -v ruff >/dev/null 2>&1; then RUFF="ruff"; else RUFF=""; fi  # /tmp 폴백 금지 — §PYTEST_PY 주석 참고
if [ -n "$RUFF" ]; then
  PINNED="$(cat .ruff-version 2>/dev/null || echo "")"
  LOCAL_V="$("$RUFF" --version 2>/dev/null | awk '{print $2}')"
  if [ -n "$PINNED" ] && [ "$LOCAL_V" != "$PINNED" ]; then
    printf '  \033[33m! 로컬 ruff %s ≠ 핀 %s — CI와 판정이 갈릴 수 있다 (pip install ruff==%s)\033[0m\n' \
      "$LOCAL_V" "$PINNED" "$PINNED"
  fi
  if "$RUFF" check . >/dev/null 2>&1; then green "ruff clean (ruff check . / v$LOCAL_V)"; else red "ruff violations (run: $RUFF check .)"; fi
else
  red "ruff unavailable — cannot verify lint"
fi

hdr "3b. shellcheck (셸 스크립트 — 대상·임계값은 scripts/lint-shell.sh SSOT)"
# 번호가 3b인 이유: §4·§7·§10은 CLAUDE.md·validate.yml·run.py 주석에서 참조된다.
# 재번호는 그 참조들을 조용히 깨뜨리므로 삽입 번호를 쓴다.
[ -f .shellcheck-version ] || red ".shellcheck-version 없음 — CI shellcheck 설치가 핀을 잃는다"
if command -v shellcheck >/dev/null 2>&1; then
  SC_PINNED="$(cat .shellcheck-version 2>/dev/null || echo "")"
  SC_LOCAL_V="$(shellcheck --version 2>/dev/null | awk '/^version:/{print $2}')"
  if [ -n "$SC_PINNED" ] && [ -n "$SC_LOCAL_V" ] && [ "$SC_LOCAL_V" != "$SC_PINNED" ]; then
    printf '  \033[33m! 로컬 shellcheck %s ≠ 핀 %s — CI와 판정이 갈릴 수 있다\033[0m\n' \
      "$SC_LOCAL_V" "$SC_PINNED"
  fi
fi
./scripts/lint-shell.sh >"$TMPD/shellcheck" 2>&1
SC_RC=$?
if [ "$SC_RC" -eq 0 ]; then
  green "shellcheck clean (scripts/lint-shell.sh — CI와 동일 커맨드)"
elif [ "$SC_RC" -eq 127 ]; then
  # ruff와 달리 red로 막지 않는다: 셸 린트의 **권위 있는 판정은 CI**(핀된 버전)이고,
  # 로컬은 빠른 피드백용이다. 미설치를 green으로 위장하지도 않는다 — 노란 줄로 남긴다.
  printf '  \033[33m! shellcheck 미설치 — 셸 린트는 CI가 판정 (brew install shellcheck)\033[0m\n'
else
  red "shellcheck 위반 (run: scripts/lint-shell.sh)"
  sed 's/^/    /' "$TMPD/shellcheck" | head -20
fi

hdr "4. pytest (hook tests)"
# ruff와 동일한 이유로 러너 버전도 핀한다(§3 참고): pytest는 메이저마다 수집·fixture·
# deprecation 처리가 바뀌어, 핀이 없으면 CI만 최신으로 떠내려가 "코드 변경 없이 red"가 난다.
[ -f .pytest-version ] || red ".pytest-version 없음 — CI pytest 설치가 핀을 잃는다"
if [ -n "$PYTEST_PY" ]; then
  PY_PINNED="$(cat .pytest-version 2>/dev/null || echo "")"
  PY_LOCAL_V="$("$PYTEST_PY" -m pytest --version 2>/dev/null | awk '{print $2}')"
  if [ -n "$PY_PINNED" ] && [ -n "$PY_LOCAL_V" ] && [ "$PY_LOCAL_V" != "$PY_PINNED" ]; then
    printf '  \033[33m! 로컬 pytest %s ≠ 핀 %s — CI와 판정이 갈릴 수 있다 (pip install pytest==%s)\033[0m\n' \
      "$PY_LOCAL_V" "$PY_PINNED" "$PY_PINNED"
  fi
  # 수집 대상은 **pytest.ini의 testpaths가 단일 소스**다 (F-023). 여기서도 CI에서도
  # 인자 없이 호출한다 — 목록을 양쪽에 적어두면 새 테스트 디렉토리를 한쪽만 등록해
  # "로컬은 돌고 CI는 안 도는" 구멍이 생긴다. 실제로 scripts/tests/ 추가 때 발생했다.
  [ -f pytest.ini ] || red "pytest.ini 없음 — 수집 대상 단일소스 소실 (F-023)"
  # SSOT는 옳지만, 그 SSOT를 한 줄 지우면 테스트 디렉토리 하나가 통째로 사라지면서
  # 로컬·CI 둘 다 green이 된다(self-disable). 실재하는 테스트 디렉토리가 전부
  # testpaths에 덮이는지 검사한다 — check_doc_counts의 "표 행 부재 = 실패"와 같은 방어.
  if [ -f pytest.ini ]; then
    UNCOVERED=$(python3 - <<'PYEOF'
import pathlib, re, subprocess, sys

# testpaths 파싱은 INI 연속 줄 규칙을 그대로 따른다: `testpaths =` 다음의 **들여쓴 줄**만
# 값이고, 들여쓰지 않은 줄에서 끝난다. 주석은 제거한다.
#   예전 정규식(`(.*?)(?=^\w|\Z)`)은 `#`가 \w가 아니라 주석 블록에서 멈추지 않았고,
#   주석의 낱말("evals" 같은)이 .split()으로 경로가 됐다. 그 결과 `evals/tests` 한 줄을
#   지워도 "덮였다"고 판정 — 테스트 50건이 조용히 사라지는데 게이트는 초록이었다.
#   (2026-08-23 적대적 리뷰가 잡은 self-disable. 이 검사 자체가 false-green이었다.)
paths = set()
in_block = False
for raw in pathlib.Path("pytest.ini").read_text(encoding="utf-8").splitlines():
    line = raw.split("#", 1)[0].rstrip()
    if not line:
        continue
    if re.match(r"^testpaths\s*=", line):
        in_block = True
        rest = line.split("=", 1)[1].strip()
        paths.update(rest.split())
        continue
    if in_block:
        if raw[:1].isspace():
            paths.update(line.split())
        else:
            break
if not paths:
    print("PARSE-FAILED")
    sys.exit(0)

out = subprocess.run(
    ["git", "ls-files", "-z", "--", "*test_*.py", "*_test.py"],
    capture_output=True, text=True, check=False,
).stdout
missing = set()
for f in out.split("\0"):
    if not f or f.startswith("evals/scenarios/"):
        continue  # 의도적으로 실패하는 fixture — 수집 대상이 아니다
    d = str(pathlib.PurePosixPath(f).parent)
    if not any(d == p or d.startswith(p.rstrip("/") + "/") for p in paths):
        missing.add(d)
print(" ".join(sorted(missing)))
PYEOF
) || UNCOVERED="PARSE-FAILED"
    # 검사 스크립트가 죽어도 빈 문자열 → green이 되던 착시를 막는다: 파싱 실패는 red다.
    if [ "$UNCOVERED" = "PARSE-FAILED" ]; then
      red "pytest.ini testpaths 파싱 실패 — 커버리지 검사 불가 (검사 불가를 통과로 세지 않는다)"
    elif [ -n "$UNCOVERED" ]; then
      red "pytest testpaths 미포함 테스트 디렉토리: $UNCOVERED (수집되지 않아 조용히 미실행)"
    else
      green "pytest testpaths 커버리지: 모든 테스트 디렉토리 포함"
    fi
  fi
  "$PYTEST_PY" -m pytest >"$TMPD/pytest" 2>&1; PYTEST_RC=$?
  # exit 5 = 수집 0. 테스트가 상존하는 레포에서 수집 0은 경로 붕괴 신호이므로 실패다
  # (CI와 fail-closed 방향 통일).
  if [ "$PYTEST_RC" -eq 0 ]; then
    green "pytest: $(grep -oE '[0-9]+ passed' "$TMPD/pytest" | tail -1) (pytest.ini testpaths)"
  elif [ "$PYTEST_RC" -eq 5 ]; then
    red "pytest 수집 0 — testpaths 붕괴 (pytest.ini 확인)"
  else
    red "pytest failed (see: $PYTEST_PY -m pytest)"
  fi
else
  red "pytest unavailable — install pytest to verify tests"
fi

hdr "5. 시크릿 스캔 (기본)"
# 결과를 변수로 수집해 판정한다 — `... | head -1 | grep -q`는 매치가 많을 때
# 상류 grep이 SIGPIPE(141)로 죽고 pipefail이 파이프라인을 비정상 종료로 만들어,
# 시크릿이 있어도 else(green)로 빠지던 false-green(적대적 리뷰 P0)을 유발했다.
SECRET_HITS=$(git ls-files | xargs grep -nIE '(api[_-]?key|secret|password|token)[[:space:]]*[:=][[:space:]]*["'"'"'][A-Za-z0-9/+]{16,}' 2>/dev/null | grep -v -E 'test|example|placeholder|YOUR_|xxx' || true)
if [ -n "$SECRET_HITS" ]; then
  red "잠재 시크릿 발견 (수동 확인 필요)"
else
  green "no obvious secrets"
fi

hdr "6. 문서 카운트/버전 sync"
# plugin.json 버전 ↔ CHANGELOG 최상단 버전 일치 (릴리스 체크리스트: 버전 범프 시
# CHANGELOG 누락 방지 — 캐시가 버전으로 키잉되므로 불일치는 릴리스 사고).
PJ_VER=$(grep -oE '"version"[[:space:]]*:[[:space:]]*"[0-9.]+"' plugins/common/.claude-plugin/plugin.json 2>/dev/null | grep -oE '[0-9.]+' | head -1)
CL_VER=$(grep -oE '^## \[[0-9.]+\]' CHANGELOG.md 2>/dev/null | grep -oE '[0-9.]+' | head -1)
if [ -z "$PJ_VER" ] || [ -z "$CL_VER" ]; then
  red "버전 sync: 파싱 실패 (plugin.json='$PJ_VER' CHANGELOG='$CL_VER')"
elif [ "$PJ_VER" = "$CL_VER" ]; then
  green "버전 sync: plugin.json = CHANGELOG = $PJ_VER"
else
  red "버전 sync: plugin.json $PJ_VER ≠ CHANGELOG 최상단 $CL_VER (릴리스 체크리스트 위반)"
fi
# 카운트 검사는 scripts/check_doc_counts.py 가 단일 소스 (F-023) — CI(validate.yml)와
# 동일 스크립트를 호출한다. bash 재구현 금지(로직 이중화 = 드리프트).
if python3 scripts/check_doc_counts.py; then
  green "doc counts 일치 (check_doc_counts.py — CI와 단일 소스)"
else
  red "doc counts drift (상세는 위 check_doc_counts.py 출력)"
fi
# 릴리스 태그 sync — CHANGELOG의 **과거** 릴리스는 전부 태그가 있어야 한다.
# 최상단(=지금 작업 중인 버전)은 아직 커밋 전일 수 있으므로 제외한다.
# 실제로 v2.10.4 이후 20개 릴리스가 무태그로 방치됐다(2026-08-17 소급 부여) —
# 관례가 조용히 끊긴 것을 아무도 몰랐던 게 문제라 산문 대신 기계 검사로 못박는다.
# 로컬 전용 검사다(CI의 shallow checkout은 태그를 안 가져온다).
MISSING_TAGS=""; _skip_top=1
for v in $(grep -oE '^## \[[0-9]+\.[0-9]+\.[0-9]+\]' CHANGELOG.md | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'); do
  if [ "$_skip_top" -eq 1 ]; then _skip_top=0; continue; fi
  git rev-parse -q --verify "refs/tags/v$v" >/dev/null 2>&1 || MISSING_TAGS="$MISSING_TAGS v$v"
done
if [ -n "$MISSING_TAGS" ]; then
  red "릴리스 태그 누락:$MISSING_TAGS — 릴리스 후 'git tag -a vX <릴리스 커밋>' + push --tags"
else
  green "릴리스 태그 sync: 과거 릴리스 전부 태그 존재 (로컬)"
fi
# 로컬에 있어도 **원격에 없으면 아무도 못 본다.** 이 검사가 로컬만 볼 때, 레포 분리로
# 태그 44개가 새 원격에 하나도 안 올라간 상태가 일주일간 green 으로 통과했다(실측).
# 검사가 도는 조건: 원격이 붙어 있고 조회 가능할 때, CHANGELOG 의 과거 릴리스 태그가
# 원격에 없으면 발화한다. 원격이 없거나 오프라인이면 노란 줄로 남긴다 — green 으로
# 위장하지 않는다(§3b 와 같은 비대칭).
if git remote get-url origin >/dev/null 2>&1; then
  if REMOTE_TAGS="$(git ls-remote --tags origin 2>/dev/null)"; then
    MISSING_REMOTE=""; _skip_top=1
    for v in $(grep -oE '^## \[[0-9]+\.[0-9]+\.[0-9]+\]' CHANGELOG.md | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'); do
      if [ "$_skip_top" -eq 1 ]; then _skip_top=0; continue; fi
      printf '%s\n' "$REMOTE_TAGS" | grep -q "refs/tags/v$v$" || MISSING_REMOTE="$MISSING_REMOTE v$v"
    done
    if [ -n "$MISSING_REMOTE" ]; then
      red "원격에 없는 릴리스 태그:$MISSING_REMOTE — 'git push origin <태그들>'"
    else
      green "릴리스 태그 sync: 원격에도 전부 존재"
    fi
  else
    printf '  \033[33m! 원격 태그 조회 실패(오프라인?) — 원격 태그 검사 생략\033[0m\n'
  fi
else
  printf '  \033[33m! origin 원격 없음 — 원격 태그 검사 생략\033[0m\n'
fi

hdr "7. stale 참조 (hooks.json + rules/agents/skills 가 가리키는 대상 존재)"
MISSING=0
for s in $(grep -oE '\$\{CLAUDE_PLUGIN_ROOT\}/[A-Za-z0-9_./-]+\.py' plugins/common/hooks/hooks.json 2>/dev/null | sed 's|${CLAUDE_PLUGIN_ROOT}|plugins/common|'); do
  [ -f "$s" ] || { red "hooks.json → 없는 스크립트: $s"; MISSING=1; }
done
# rules/agents/skills 산문이 가리키는 ./scripts/<name>.sh 가 실재하는지 검증 —
# always-injected 룰의 죽은 스크립트 참조(예: 존재하지 않는 db-tunnel.sh)가 매 세션
# 주입되던 문제 방지.
#
# **skills/ 가 원래 빠져 있었다**(2026-09-09 추가). 그 사이로 죽은 참조가 실제로 샜다 —
# `control-loop` 이 제거된 `agent-teams/SKILL.md` 를 "관련" 표에 걸어 두고 있었고,
# `facilitator` 에이전트는 없는 파일을 "참고" 하라고 지시했다. warning-signal.md
# §검토 절차 5("이 검사의 대상 밖은 어디인가")를 §7 자신에게 적용해 찾았다.
for ref in $(grep -rhoIE '(\./)?scripts/[A-Za-z0-9_/-]+\.sh' plugins/common/rules plugins/common/agents plugins/common/skills 2>/dev/null | sed 's|^\./||' | sort -u); do
  [ -f "$ref" ] || { red "rules/agents/skills → 없는 스크립트 참조: $ref"; MISSING=1; }
done
# 배포물 안에서 서로를 가리키는 plugins/common/** 경로도 실재해야 한다. 제거된 스킬·
# 에이전트를 가리키는 참조는 "없는 기능을 안내하는 문서"이고, 그걸 읽는 것은 모델이다.
#
# **tests/ 는 제외한다** — 오탐이 아니라 성질이 다르다. 테스트는 가짜 경로를 **일부러**
# 만든다(예: 가짜 `git ls-files` 출력에 `hooks/new.py`). 그리고 이 검사의 목적은
# "배포물이 없는 기능을 **모델에게 안내**하지 않는다"이므로, 모델이 지시로 읽지 않는
# 테스트 픽스처는 애초에 대상이 아니다. 오탐을 남기면 그 검사는 곧 무시당한다
# (docs/conventions/warning-signal.md).
# -I: 바이너리(__pycache__ 등)를 건너뛴다 — 없으면 'Binary file … matches' 가 경로로 오인된다.
for ref in $(grep -rhoIE --exclude-dir=tests --exclude-dir=__pycache__ 'plugins/common/(skills|agents|rules|hooks)/[A-Za-z0-9_/.-]+\.(md|py|json)' plugins/common 2>/dev/null | sort -u); do
  [ -f "$ref" ] || { red "배포물 → 없는 컴포넌트 참조: $ref"; MISSING=1; }
done
[ "$MISSING" -eq 0 ] && green "hooks.json + rules/agents/skills 참조 대상 모두 존재"
# rules 무결성 매니페스트 강제 — 해시 일치 + **집합 동등성**(매니페스트에 없는
# 신규 파일도 red — 나열-파일만 검사하는 -c의 맹점 보완, 재감사 ATK-002/007)
if command -v shasum >/dev/null 2>&1; then _SHA="shasum -a 256"; elif command -v sha256sum >/dev/null 2>&1; then _SHA="sha256sum"; else _SHA=""; fi
if [ -z "$_SHA" ]; then
  red "rules CHECKSUMS: 해시 도구 부재(shasum/sha256sum) — 검증 불가"
elif (cd plugins/common/rules && $_SHA *.md 2>/dev/null | grep -v CHECKSUMS | diff -q - CHECKSUMS.sha256 >/dev/null 2>&1); then
  green "rules CHECKSUMS 일치 (집합 동등)"
else
  red "rules CHECKSUMS 불일치/신규 파일 — 재생성: (cd plugins/common/rules && $_SHA *.md | grep -v CHECKSUMS > CHECKSUMS.sha256)"
fi
# 룰 해설본 미러 동기 — 검사 로직은 scripts/sync-rule-mirror.sh 가 단일 소스.
# docs/architecture/rules/ 가 주입 룰보다 뒤처지면 FAIL (실제로 3건 드리프트했었다).
if ./scripts/sync-rule-mirror.sh >"$TMPD/mirror" 2>&1; then
  green "rules 해설본 미러 동기 (docs/architecture/rules ↔ plugins/common/rules)"
else
  red "rules 해설본 미러 드리프트 (run: scripts/sync-rule-mirror.sh)"
  sed 's/^/    /' "$TMPD/mirror" | head -10
fi
# 배포 에이전트 MCP 미배선 가드 (W-015): frontmatter tools에 mcp__ 금지 + description/body가
# Context7/Tavily/mcp__를 자기 능력으로 지시 금지(web-research 스킬 위임 문맥은 허용).
# 미설치 소비자 환각(CC #13898) 방지 — frontmatter-only 가드의 산문 맹점 보완(적대리뷰 ATK-004).
MCP_VIOL=0
# `< <(find -print0)`: 파이프가 아니라 프로세스 치환이어야 한다 — `find | while`로 쓰면
# 루프가 서브셸에서 돌아 red()의 FAIL 증가와 MCP_VIOL 대입이 통째로 버려진다(false-green).
while IFS= read -r -d '' f; do
  fm=$(awk 'NR==1&&/^---/{fr=1;next} fr&&/^---/{exit} fr{print}' "$f")
  printf '%s' "$fm" | grep -q "mcp__" && { red "MCP: frontmatter에 mcp__ — $f"; MCP_VIOL=1; }
  # 산문이 Context7/Tavily/mcp__를 언급하면서 web-research 위임 문맥이 없으면 위반
  # ("Exa"는 "example" 오탐이라 제외)
  if grep -qE "Context7|Tavily|mcp__" "$f" && ! grep -q "web-research" "$f"; then
    red "MCP: 에이전트 산문이 MCP를 자기 능력으로 지시(스킬 위임 아님) — $f"; MCP_VIOL=1
  fi
done < <(find plugins/common/agents -name "*.md" -print0 2>/dev/null)
[ "$MCP_VIOL" -eq 0 ] && green "MCP: 배포 에이전트 frontmatter·산문 모두 MCP 미배선(스킬 위임)"

hdr "8. Durable checklist 완료 게이트 (active Work, W-013)"
# checklist.json이 완료 상태의 단일 authority. active Work에 passes:false 잔존 시 FAIL.
# status exit: 0=전항목pass 1=미완/손상 3=진짜 부재(skip). helper가 없는데 checklist는
# 있으면 fail-closed(적대적 리뷰: helper 삭제 시 미완이 green 되던 false-green 차단).
CL_HELPER="plugins/common/hooks/checklist.py"
CL_FOUND=0
for cl in docs/works/active/*/checklist.json; do
  [ -f "$cl" ] || continue
  CL_FOUND=1
  wd="$(dirname "$cl")"
  if [ ! -f "$CL_HELPER" ]; then
    red "checklist 존재하나 helper($CL_HELPER) 없음 → 검증 불가(fail-closed): $(basename "$wd")"
    continue
  fi
  python3 "$CL_HELPER" status "$wd" >"$TMPD/checklist" 2>&1
  rc=$?
  if [ "$rc" -eq 0 ]; then
    green "checklist 전항목 pass: $(basename "$wd")"
  elif [ "$rc" -eq 3 ]; then
    : # 진짜 부재 → skip (loop 도중 파일 생성 전)
  else
    red "checklist 미완/손상: $(basename "$wd") — $(tr '\n' ' ' <"$TMPD/checklist")"
  fi
done
[ "$CL_FOUND" -eq 0 ] && green "active checklist 없음 (skip)"

hdr "9. test-ratchet (테스트/assert 삭제 방지, W-013)"
# diff에서 test/assert가 allow-marker 없이 순감소하면 FAIL. 산문 규율이 아닌 기계 체크.
python3 - <<'EOF' && green "test-ratchet: 테스트 감소 없음" || red "test-ratchet: allow-marker 없이 테스트/assert 순감소 (의도적이면 커밋 메시지에 TEST-RATCHET-ALLOW 명시)"
import re
import subprocess
import sys


def sh(*a):
    r = subprocess.run(a, capture_output=True, text=True)
    return r.stdout.strip(), r.returncode


# 비교 기준(base) 선택 — 적대적 리뷰 F4: `merge-base main HEAD`는 HEAD가 main일 때
# HEAD와 같아져(=빈 diff) 커밋된 테스트 삭제를 못 본다. 또 main이 없으면 조용히 green.
# → fork point가 degenerate하면 origin/main → HEAD~1 로 폴백하고, 어디에도 없으면
#   조용한 green이 아니라 [warn] 후 skip.
base, mrc = sh("git", "merge-base", "main", "HEAD")
head, _ = sh("git", "rev-parse", "HEAD")
if mrc != 0 or not base or base == head:
    omb, orc = sh("git", "merge-base", "origin/main", "HEAD")
    if orc == 0 and omb and omb != head:
        base = omb
    else:
        h1, h1rc = sh("git", "rev-parse", "--verify", "--quiet", "HEAD~1")
        if h1rc == 0 and h1:
            base = "HEAD~1"
        else:
            # fresh/단일-커밋 저장소: HEAD를 base로 두면 최소한 워킹트리 미커밋
            # 테스트 삭제는 잡는다(조용한 skip보다 낫다, 적대적 리뷰 P2).
            base = "HEAD"

pat = re.compile(r"(def\s+test_|\bassert\b|\bit\(|\btest\(|\bexpect\()")
# 테스트 파일 경로만 집계 — prod 코드의 방어적 assert 삭제가 오탐 FAIL 내지 않도록.
test_path = re.compile(
    r"(^|/)(test_|[^/]*_test\.|[^/]*\.test\.|[^/]*\.spec\.|conftest|(tests?|specs?|__tests__)/)"
)


def _is_test(p):
    p = p.strip()
    if p in ("", "/dev/null"):
        return False
    for pre in ("a/", "b/"):
        if p.startswith(pre):
            p = p[2:]
            break
    return bool(test_path.search(p))


def count(diff):
    """diff에서 테스트 파일의 (추가, 삭제) 마커 줄 수.

    --unified=0에서 삭제된 내용줄 '-- x'는 '--- x'로, 추가줄 '++ x'는 '+++ x'로 보여
    파일 헤더로 오인될 수 있다(적대적 리뷰). diff --git/@@ 로 헤더 영역 vs 내용 영역을
    명확히 분리해, --- /+++ 는 hunk 시작(@@) 전에만 헤더로 해석한다.
    """
    added = removed = 0
    old_test = in_test = in_hunk = False
    for ln in diff.splitlines():
        if ln.startswith("diff --git"):
            in_hunk = False
            old_test = in_test = False
            continue
        if ln.startswith("@@"):
            in_hunk = True
            continue
        if not in_hunk and ln.startswith("--- "):
            old_test = _is_test(ln[4:])
            continue
        if not in_hunk and ln.startswith("+++ "):
            in_test = old_test or _is_test(ln[4:])
            continue
        if not in_hunk or not in_test:
            continue
        if ln.startswith("+") and pat.search(ln):
            added += 1
        elif ln.startswith("-") and pat.search(ln):
            removed += 1
    return added, removed


fail = False

# ── (1) base 대비 순증감 — PR 관점. 워킹트리 미커밋 삭제도 여기서 잡힌다 ──────────
r = subprocess.run(["git", "diff", "--unified=0", base], capture_output=True, text=True)
if r.returncode != 0:
    print(f"    [warn] test-ratchet: git diff 실패({base}) — 순증감 검사 skip")
else:
    diff = r.stdout
    if diff.strip() and "TEST-RATCHET-ALLOW" not in diff:
        added, removed = count(diff)
        if removed - added > 0:
            print(f"    테스트 삭제 {removed} > 추가 {added} (net -{removed - added}, base={base[:8]})")
            fail = True

# ── (2) 커밋 단위 — 순증감이 상쇄해 가리는 삭제를 드러낸다 ────────────────────────
# 2026-08-27 발견: (1)만 있으면 장기 통합 브랜치(25+ 커밋)에서 "먼저 20개 추가 →
# 나중에 14개 삭제"가 net +6 으로 green이 된다. 'PR 단위 순감소'는 막지만 '브랜치
# 내부 삭제'는 구조적으로 못 본다. 게이트가 있다는 사실이 방어를 보증하지 않는다.
# 마커는 **커밋 메시지**에서 찾는다 — diff 아무 곳이나 허용하면 무관한 파일의 한 줄로
# 검사 전체가 꺼진다(같은 날 발견한 두 번째 구멍).
revs, rrc = sh("git", "rev-list", "--no-merges", f"{base}..HEAD")
if rrc != 0:
    print("    [warn] test-ratchet: rev-list 실패 — 커밋 단위 검사 skip")
elif revs:
    offenders = []
    for rev in revs.split("\n"):
        rev = rev.strip()
        if not rev:
            continue
        msg, _ = sh("git", "log", "-1", "--format=%B", rev)
        if "TEST-RATCHET-ALLOW" in msg:
            continue
        d = subprocess.run(
            ["git", "show", "--unified=0", "--format=", rev],
            capture_output=True,
            text=True,
        )
        if d.returncode != 0:
            continue
        a, rm = count(d.stdout)
        if rm - a > 0:
            subj, _ = sh("git", "log", "-1", "--format=%s", rev)
            offenders.append(f"{rev[:8]} -{rm - a} {subj[:56]}")
    if offenders:
        print("    커밋 단위 테스트 감소 (순증감으로 가려짐):")
        for o in offenders:
            print(f"      {o}")
        print("    의도적이면 해당 커밋 메시지에 TEST-RATCHET-ALLOW 를 남겨라")
        fail = True

sys.exit(1 if fail else 0)
EOF

hdr "10. Agent evals 스키마 (오프라인, W-B / toolkit-improvement-batch)"
# 행동 eval 자체(claude -p 실제 호출)는 API 비용이 들어 여기 넣지 않는다 —
# release-gate는 scripts/run-evals.sh의 몫(README §exit code 참고). 여기서는
# expect.json 스키마 + 시나리오-에이전트 참조 무결성만 오프라인 검증한다.
# evals/ 부재는 fail-closed(조용한 skip 금지) — run.py의 validate_all()이 이를 강제한다.
if [ -f evals/run.py ]; then
  if python3 evals/run.py --validate >"$TMPD/evals_validate" 2>&1; then
    green "evals --validate: $(tail -1 "$TMPD/evals_validate")"
  else
    red "evals --validate 실패 — $(tail -3 "$TMPD/evals_validate" | tr '\n' ' ')"
  fi
else
  red "evals/run.py 없음 (fail-closed — W-B 산출물 누락)"
fi

hdr "13. Eval 커버리지·기준선 게이트 (W-018 / S1)"
# 시나리오 디렉토리 ⇄ 기준선 (agent,scenario) 집합의 양방향 대조 + tier1 최소
# 커버리지. 로직 단일 소스는 scripts/check_eval_coverage.py — CI(validate.yml)가
# 동일 스크립트를 호출한다(F-023 관례). 에이전트 호출 0건(비용 없음), 매 커밋 가능.
if [ -f scripts/check_eval_coverage.py ]; then
  if python3 scripts/check_eval_coverage.py >"$TMPD/eval_coverage" 2>&1; then
    green "eval 커버리지 정합 (baseline ⇄ scenarios)"
    sed 's/^/    /' "$TMPD/eval_coverage"
  else
    red "eval 커버리지 드리프트 — 상세는 check_eval_coverage.py 출력"
    sed 's/^/    /' "$TMPD/eval_coverage"
  fi
else
  red "scripts/check_eval_coverage.py 없음 (W-018 S1 산출물 누락)"
fi

hdr "11. 하네스 진입점 이식 드리프트 (W-017) — AGENTS.md · GEMINI.md"
# rules/ 를 고치고 AGENTS.md를 재생성하지 않으면, Codex·OpenCode 등 다른 하네스에서
# 도는 에이전트는 **옛 규범**을 읽는다. 같은 레포에서 하네스마다 규율이 갈리는 상태를
# 침묵으로 두지 않는다. exit 2(SKIPPED)는 소스 미탐지 — green으로 세지 않는다.
if [ -f scripts/export-harness.sh ] && [ -f plugins/common/hooks/export_harness.py ]; then
  ./scripts/export-harness.sh --check >"$TMPD/agents_md" 2>&1
  EH_RC=$?
  if [ "$EH_RC" -eq 0 ]; then
    green "진입점 최신 (rules 원문 + 블록 본문 일치)"
  elif [ "$EH_RC" -eq 2 ]; then
    red "export-harness SKIPPED — 규범 소스 미탐지"
    sed 's/^/      /' "$TMPD/agents_md" | head -6
  else
    # exit 1은 드리프트만이 아니다 — 분류 미등재/유령 엔트리, 마커 손상, 본문 변조,
    # 인코딩 실패가 모두 여기 모인다. 원인을 안 보여주면 "재생성하라"가 무한루프가 된다
    # (분류 문제는 재생성으로 안 고쳐진다).
    red "진입점 검사 실패 — 아래 원인 확인 (재생성으로 안 고쳐지는 경우가 있다)"
    sed 's/^/      /' "$TMPD/agents_md" | head -10
  fi
else
  red "export-harness 산출물 누락 (scripts/export-harness.sh 또는 hooks/export_harness.py) — W-017"
fi

hdr "14. 다중 하네스 타겟 매니페스트 드리프트 (W-019)"
# packaging/targets.json + plugins/common/.claude-plugin/plugin.json(SSOT)에서 계산되는
# Codex·Antigravity 타겟 매니페스트가 SSOT와 어긋나지 않는지 검사한다. enabled:true인
# 타겟은 매니페스트가 실제로 존재하고 SSOT와 바이트 단위로 일치해야 한다 — 미생성도
# 드리프트로 취급해 fail이다(D1 판정, targets.json gate.requireGeneratedManifestPresent,
# build-targets.py 원칙 3). S1 단계처럼 enabled 타겟이 아예 없을 때만 검사 대상 0건으로
# 관대히 통과한다.
if [ -f packaging/targets.json ] && [ -f scripts/build-targets.py ]; then
  python3 scripts/build-targets.py --check >"$TMPD/targets" 2>&1
  BT_RC=$?
  if [ "$BT_RC" -eq 0 ]; then
    green "타겟 매니페스트: $(tail -1 "$TMPD/targets")"
  else
    red "타겟 매니페스트 드리프트 (run: python3 scripts/build-targets.py --check)"
    sed 's/^/      /' "$TMPD/targets" | head -10
  fi
else
  red "다중 하네스 생성기 산출물 누락 (packaging/targets.json 또는 scripts/build-targets.py) — W-019"
fi

hdr "16. 상시 주입 예산 — 규범+WORKFLOW · 에이전트 설명 (W-025 / D-20·D-46)"
# 판정 로직은 scripts/check_injection_budget.py 가 단일 소스 — CI(validate.yml)와 동일
# 스크립트를 호출한다. 원래 이 게이트는 여기 인라인이었고 **CI 에 없었다** — 발화 조건이
# "누가 로컬에서 verify-done.sh 를 돌릴 때만"이었다는 뜻이다(F-023 + §18 이 같은 구멍을
# 겪었다). 상한 도출·축 분리 근거는 그 스크립트의 독스트링에 있다.
if python3 scripts/check_injection_budget.py; then
  green "상시 주입 예산 통과 (check_injection_budget.py — CI와 단일 소스)"
else
  red "상시 주입 예산 초과 — 매 세션 이만큼이 컨텍스트를 먹는다 (상세는 위 출력)"
fi

hdr "15. AGENTS.md 크기 예산 (W-022 R7)"
# Codex의 project_doc_max_bytes(기본 32 KiB)는 전역(~/.codex/AGENTS.md) → git-root →
# cwd AGENTS.md를 **병합한 총량**에 걸리고, 넘으면 cwd에 가까운 파일부터 **조용히
# 잘린다**(경고 없음) — docs/research/2026-08-27-superpowers-distribution.md 부록.
# 이 레포의 AGENTS.md 혼자 32 KiB를 다 써버리면 사용자의 전역 AGENTS.md와 합쳐지는
# 순간 어느 쪽이든 잘릴 여지가 남는다. 그래서 32 KiB 자체가 아니라 그 75%인
# 24,576 B를 이 레포 몫의 보수적 상한으로 둔다 — 나머지는 사용자의 전역 파일 몫.
CONV_SIZE_CAP=24576
if [ -f AGENTS.md ]; then
  AGENTS_BYTES=$(wc -c <AGENTS.md | tr -d ' ')
  if [ "$AGENTS_BYTES" -le "$CONV_SIZE_CAP" ]; then
    green "AGENTS.md ${AGENTS_BYTES}B ≤ ${CONV_SIZE_CAP}B (Codex project_doc_max_bytes 32KiB의 75% 보수 상한)"
  else
    red "AGENTS.md ${AGENTS_BYTES}B > ${CONV_SIZE_CAP}B — Codex에서 전역 AGENTS.md와 병합 시 잘릴 수 있다"
    echo "      → plugins/common/hooks/export_harness.py의 CONVENTIONS_INLINE에서 항목을 빼거나"
    echo "        rules/*.md 원문을 줄여라. (병합 총량 상한이므로 이 파일 혼자 다 쓰면 안 된다)"
  fi
else
  red "AGENTS.md 없음 — ./scripts/export-harness.sh 로 먼저 생성하라"
fi

hdr "17. 배포물 안 오케스트레이션 도구 이름 0건 (G-D6, W-026 / D-6·Q5)"
# control-loop의 운송 부록(docs/control-loop-transport.md)은 특정 오케스트레이션
# CLI(orca) 이름을 담지만, 그 부록은 비규범이고 docs/에만 있다(D-6). plugins/ 아래
# 어디든 이 이름이 새면 배포물이 소비자에게 orca 같은 특정 도구를 전제하는 것처럼
# 보이는 드리프트다 — G-D6는 이 불변식을 결정적으로 강제한다(되돌려-FAIL).
# 대소문자 구분: export_harness.py의 "Orca"(ADE 예시로서의 일반 명사, §7 주석 참고)
# 는 오케스트레이션 CLI를 가리키는 것이 아니므로 소문자 정확 매치만 검사한다.
# git-tracked 파일만 본다 — .ruff_cache·__pycache__ 등 생성물의 우연한 매치(바이너리
# 캐시 blob 등)를 걸러낸다. 소스가 아닌 것은 이 게이트의 대상이 아니다.
ORCA_FILES=$(git ls-files plugins 2>/dev/null | xargs -I{} sh -c 'grep -l "orca" "{}" 2>/dev/null' 2>/dev/null)
ORCA_HITS=$(printf '%s\n' "$ORCA_FILES" | grep -c . || true)
if [ "$ORCA_HITS" -eq 0 ]; then
  green "plugins/ 안 'orca' 0건"
else
  red "plugins/ 안 'orca' ${ORCA_HITS}건 — 운송 도구 이름은 docs/control-loop-transport.md로"
  printf '%s\n' "$ORCA_FILES" | sed 's/^/      /'
fi

hdr "18. 이름 SSOT 파생 드리프트 (D-3 / W-027 27-2)"
# plugins/common/.claude-plugin/plugin.json 의 name(SSOT)에서 README·plugins/common/
# README·CLAUDE.md·site/content/**를 파생시키는 scripts/derive-name.py 의 드리프트
# 검사. §17은 D-22(상호 참조 실재 게이트, 25-16)의 몫으로 예약돼 있으므로 다음 빈
# 번호(§18)를 쓴다 — 섹션 번호 규약(재사용·재배치 금지)은 위 §36-49 주석 참고.
if [ -f packaging/name-targets.json ] && [ -f scripts/derive-name.py ]; then
  python3 scripts/derive-name.py --check >"$TMPD/name_derive" 2>&1
  ND_RC=$?
  if [ "$ND_RC" -eq 0 ]; then
    green "이름 파생: $(tail -1 "$TMPD/name_derive")"
  else
    red "이름 파생 드리프트 (run: python3 scripts/derive-name.py --write)"
    sed 's/^/      /' "$TMPD/name_derive" | head -10
  fi
else
  red "이름 파생 생성기 산출물 누락 (packaging/name-targets.json 또는 scripts/derive-name.py) — D-3"
fi

hdr "19. 배포 매니페스트·컴포넌트 (claude plugin validate --strict)"
# 왜 있나: **커뮤니티 카탈로그의 pin 전진이 이 검사를 돌린다.** 상류
# bump-plugin-shas.yml 이 새 SHA 에서 `claude plugin validate` 를 실행하고, 실패하면
# 그 항목은 red PR 로 남거나 freeze 목록에 올라 **자동 전진이 영구히 멈춘다.** 즉 이
# 검사는 우리 CI 가 아니라 **배포 경로가 실제로 거는 관문**이고, 우리는 그것을 미리
# 돌려 본다.
#
# 이 검사가 도는 조건(warning-signal.md §검토 절차 4): `claude` CLI 가 PATH 에 있을 때,
# 매니페스트·에이전트·스킬에 스키마 위반이나 미지 필드가 있으면 발화한다. 실제로 발화한
# 이력: 최상위 `repository` 필드가 두 레포 모두에 있었고 로드 시 무시되고 있었다.
#
# --strict 를 쓰는 이유: 상류는 기본(비-strict)으로 돌리지만, **우리가 소비자보다
# 느슨할 이유가 없다.** 경고 단계에서 잡으면 상류 정책이 조여져도 영향받지 않는다.
if command -v claude >/dev/null 2>&1; then
  CPV_FAIL=0
  : >"$TMPD/cpv"
  for _t in .claude-plugin/marketplace.json plugins/common \
            plugins/common/agents plugins/common/skills; do
    [ -e "$_t" ] || continue
    if ! claude plugin validate --strict "$_t" >>"$TMPD/cpv" 2>&1; then
      CPV_FAIL=1
    fi
  done
  # exit code 를 신뢰하지 않는다: --strict 실패 시에도 0 을 내는 것이 관측됐다(실측).
  # 그래서 출력의 실패 표식도 함께 본다 — 종료코드만 보면 거짓 green 이 된다.
  if grep -q "Validation failed" "$TMPD/cpv" 2>/dev/null; then CPV_FAIL=1; fi
  if [ "$CPV_FAIL" -eq 0 ]; then
    green "claude plugin validate --strict: 매니페스트·에이전트·스킬 전부 통과"
  else
    red "claude plugin validate --strict 실패 — 카탈로그 pin 전진이 이 검사에 걸린다"
    grep -E "❯|✘|⚠" "$TMPD/cpv" | sed 's/^/    /' | head -20
  fi
else
  # §3b 와 같은 비대칭: 미설치를 green 으로 위장하지 않고 노란 줄로 남긴다.
  # (주석을 '# shellcheck' 로 시작하면 셸 린터가 지시자로 파싱한다 — 실측으로 걸렸다.)
  printf '  \033[33m! claude CLI 미설치 — 배포 매니페스트 검증 생략 (CI 가 판정)\033[0m\n'
fi

hdr "20. 살아있는 표면에 구 프로젝트 이름 0건 (개명 잔재)"
# §17과 같은 형태의 불변식이다: **지금 쓰이는 것**에 구 이름이 실리면 안 된다.
# 제외는 역사 기록(docs/·CHANGELOG)과 정책 자신뿐 — 정책 데이터로 둔다.
# 판정 로직은 scripts/check_old_names.py 가 단일 소스 — CI(validate.yml)와 동일
# 스크립트를 호출한다. bash 재구현 금지(F-023: 복제 로직은 반드시 드리프트한다).
if python3 scripts/check_old_names.py; then
  green "살아있는 표면에 구 이름 0건 (check_old_names.py — CI와 단일 소스)"
else
  red "구 이름 잔존 — 살아있는 표면에 개명 잔재 (상세는 위 출력)"
fi

hdr "21. 설치된 git 훅이 이 레포의 정본과 같은가 (배포 ≠ 실행 결함 클래스)"
# **경고이지 오류가 아니다** — §3b·§19 와 같은 비대칭이다.
#
# 왜 필요한가: 이 킷의 대표 결함 클래스는 "커밋·테스트·문서를 다 갖춘 가드가 설치본에
# 없어 집행이 0회"다. 실측(v3.7.0): .private-names 비공개 이름 차단이 setup/pre-commit
# 소스에만 있고 어느 저장소에도 설치되지 않은 채 "활성"으로 릴리스 보고됐다. 원인은
# session-check 가 훅이 **없을 때만** 설치해 최초 판이 영구 동결된 것이었다(v3.8.0 수정).
#
# 왜 red 가 아닌가: 훅 소스를 고치는 중에는 repo 가 설치본보다 앞선 것이 **정상**이다.
# red 로 두면 훅 작업 내내 발화해 죽은 경고가 된다(warning-signal.md §검토 절차 1).
#
# 대상이 둘인 이유(§검토 절차 5 — "이 검사의 대상 밖은 어디인가"): 처음엔 pre-commit
# 하나만 봤는데, v3.11.0 에서 들인 opt-in git 훅은 소비자가 **손으로 복사**하도록
# 안내했다 — 그건 방금 고친 install-once/드리프트 문제 그 자체다. 그래서 목록으로 만들고,
# 새 킷 훅이 생기면 여기 한 줄만 더한다.
#
# 설치 여부의 의미가 둘로 갈린다:
#   - pre-commit: session-check 가 자동 설치한다 → **없으면** 집행이 안 도는 것이므로 알린다
#   - reference-transaction: opt-in 이다 → **없는 것이 정상**이므로 침묵한다
# 없는 보호를 있다고 적지 않는 것과 같은 규율의 뒷면이다 — 안 켠 것을 결함으로 보고하면
# 그 경고는 켜지 않은 모든 소비자에게 상시 참이 되어 죽는다.
#
# 검사 조건 한 문장: **설치된 훅이 킷 마커를 갖고 있는데 repo 정본과 내용이 다르면 노란 줄.**
HOOKS_DIR="$(git rev-parse --git-path hooks 2>/dev/null)"
# "정본경로|설치이름|마커|미설치시_알림(1=알림, 0=침묵)"
KIT_HOOKS="plugins/common/setup/pre-commit|pre-commit|# Auto-installed by session-check.py|1
plugins/common/setup/git-hooks/reference-transaction|reference-transaction|# kit-managed-hook|0"
while IFS='|' read -r _src _name _marker _notify; do
  [ -n "$_src" ] || continue
  _dst="${HOOKS_DIR}/${_name}"
  if [ ! -f "$_src" ]; then
    red "훅 정본 없음: $_src"
  elif [ ! -f "$_dst" ]; then
    if [ "$_notify" = "1" ]; then
      printf '  \033[33m! %s 미설치 — 커밋타임 집행이 이 저장소에서 돌지 않는다\033[0m\n' "$_name"
    else
      green "${_name}: 미설치 (opt-in — 안 켠 것은 결함이 아니다)"
    fi
  elif ! grep -qF -- "$_marker" "$_dst"; then
    printf '  \033[33m! %s 이 킷 소유가 아니다(마커 없음) — 대조 생략\033[0m\n' "$_name"
  elif cmp -s "$_src" "$_dst"; then
    green "설치된 ${_name} = repo 정본"
  else
    printf '  \033[33m! 설치된 %s 가 repo 정본과 다르다\033[0m\n' "$_name"
    printf '      정본 %s B / 설치본 %s B\n' "$(wc -c <"$_src" | tr -d " ")" "$(wc -c <"$_dst" | tr -d " ")"
  fi
done <<EOF
$KIT_HOOKS
EOF

hdr "22. 그림자 정의 0건 (같은 모듈에 같은 이름의 최상위 정의)"
# 판정은 scripts/check_shadowed_defs.py 가 단일 소스 — CI 와 동일 스크립트(F-023).
#
# **ruff 로 부족하다** `[confirmed 2026-09-09]`. F811(Redefinition of unused name)이 이
# 결함이고 켜져 있지만, ruff 는 `_` 접두 이름을 dummy 로 보고 **면제**한다 — 그런데
# 밑줄 접두가 이 레포 테스트 헬퍼의 기본 명명 관례라 면제 범위가 정확히 위험 지대와
# 겹친다. `dummy-variable-rgx` 를 좁히면 잡히지만 그 설정은 F841·B007·RUF059 와 공유라
# 서술적 폐기 이름(`_scenario`·`_lines`) 10곳이 `_` 한 글자로 강등된다 — 그 가독성을
# 이 검사 하나와 바꾸지 않는다.
#
# 왜 red 인가: 그림자 정의는 **테스트가 통과하면서 다른 것을 재는** 상태를 만든다.
# 이 레포가 가장 나쁘게 보는 false-green 이다(F-012).
if python3 scripts/check_shadowed_defs.py; then
  green "그림자 정의 0건 (check_shadowed_defs.py — CI와 단일 소스)"
else
  red "그림자 정의 잔존 — 나중 정의가 앞선 것을 덮는다 (상세는 위 출력)"
fi

# ── 결과 ──────────────────────────────────────────────────────────
hdr "═══ 기계 검사 결과: ${PASS} pass / ${FAIL} fail ═══"
hdr "수동 DoD attest (증거와 함께 명시 — 자동 검사 불가)"
cat <<'EOF'
  [ ] 스펙·계획의 모든 항목 구현 (spec ↔ 코드 대조, 누락 없음)
  [ ] 적대적 리뷰 1회 (버그·엣지케이스·문서 sync 능동 탐색)
  [ ] Work 라이프사이클 상태 정확히 보고 (active/validation vs completed)
  [ ] CHANGELOG·README·CLAUDE.md 영향 반영
EOF

if [ "$FAIL" -gt 0 ]; then
  printf '\n\033[31m완료 불가 — 기계 검사 %d건 실패. "완료"를 주장하지 말 것.\033[0m\n' "$FAIL"
  exit 1
fi
printf '\n\033[32m기계 검사 전부 통과. 위 수동 attest를 증거와 함께 확인한 뒤에만 "완료" 선언.\033[0m\n'
exit 0
