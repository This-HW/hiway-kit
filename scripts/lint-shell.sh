#!/usr/bin/env bash
#
# lint-shell.sh — 셸 스크립트 린트의 **단일 소스**
#
# 이 레포의 완료 게이트(verify-done.sh)와 설치 스크립트(setup.sh)는 셸이다. 파이썬은
# ruff로 엄격히 검사하면서 정작 "완료"를 판정하는 스크립트와 소비자 머신에서 도는
# 설치 스크립트가 무린트였다 — 그 갭을 닫는다.
#
# 대상 목록과 심각도 임계값은 여기 한 곳에만 둔다. CI(validate.yml)와 verify-done.sh
# §3b가 **이 커맨드를 그대로** 호출한다. 양쪽에 목록/플래그를 복제하면 드리프트가
# 난다 — `ruff check .`가 단일 커맨드인 것, doc 카운트를 check_doc_counts.py 하나로
# 두는 것과 같은 원칙(F-023).
#
# 종료코드: 0 = clean, 127 = shellcheck 미설치(판정 불가), 그 외 = 위반 있음
set -uo pipefail

# 대상 열거를 `git ls-files`에 의존하므로, 저장소 밖이면 "대상 0건"과 "열거 실패"가
# 구분되지 않는다. 후자를 exit 0으로 넘기면 게이트가 green을 찍는 false-green이 된다.
if ! ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || [ -z "$ROOT" ]; then
  echo "git 저장소가 아니다 — 셸 스크립트 목록을 열거할 수 없다(판정 불가)" >&2
  exit 2
fi
cd "$ROOT" || exit 1

if ! command -v shellcheck >/dev/null 2>&1; then
  echo "shellcheck 미설치 — 셸 린트 판정 불가 (brew install shellcheck / apt install shellcheck)" >&2
  exit 127
fi

# 확장자만으로는 `plugins/common/setup/pre-commit`처럼 확장자 없는 훅 스크립트가
# 빠진다. shebang으로도 판별해 새 스크립트가 추가돼도 목록 수정이 필요 없게 한다.
files=()
while IFS= read -r -d '' f; do
  case "$f" in
    *.sh) files+=("$f"); continue ;;
  esac
  if head -1 "$f" 2>/dev/null | grep -qaE '^#!.*\b(bash|sh|zsh)\b'; then
    files+=("$f")
  fi
done < <(git ls-files -z)

if [ "${#files[@]}" -eq 0 ]; then
  echo "추적 중인 셸 스크립트 없음" >&2
  exit 0
fi

# -S warning: info/style은 제외한다. 게이트는 취향이 아니라 **실제로 깨질 수 있는 것**만
# 막는다 — 임계값을 낮추려면 여기 한 줄만 바꾸면 CI와 로컬이 함께 움직인다.
exec shellcheck -S warning "${files[@]}"
