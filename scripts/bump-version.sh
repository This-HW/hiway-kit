#!/usr/bin/env bash
#
# bump-version.sh — 버전 갱신 + 생성물 재생성 + 자기 검증을 한 명령으로 (W-022 R8).
#
# 왜 필요한가: v2.15.0 릴리스에서 SSOT(`.claude-plugin/plugin.json`)의 버전만 올리고
# `build-targets.py --write`를 잊었다 — `verify-done.sh §14`가 드리프트로 잡아서
# 발견은 됐지만, **게이트가 없었으면 옛 버전이 실린 Codex·Antigravity 매니페스트가
# 그대로 나갔을 것**이다. 탐지보다 예방이 낫다(superpowers의 `.version-bump.json`
# 팬아웃과 같은 동기, 다만 우리 매니페스트는 값이 아니라 *생성물*이므로 팬아웃 대신
# 재생성이 정답이다 — docs/research/2026-08-27-superpowers-distribution.md §3).
#
# 이 스크립트가 사람이 기억해야 했던 2단계(SSOT 갱신 → 재생성)를 하나로 묶고,
# 마지막에 `--check`로 **자기 결과를 스스로 검증**한다 — "성공했다고 말했는데 실은
# 드리프트가 남아있다"를 원천 봉쇄한다.
#
# 경로 봉쇄: 이 스크립트는 정책·설정값으로 파일 경로를 조립하지 않는다(대상 경로는
# 전부 스크립트에 고정된 상대경로) — 그래서 CLAUDE.md의 `_resolve_in_repo()` 관례가
# 적용될 지점이 없다. 실제 봉쇄가 필요한 지점(타겟 매니페스트 경로)은
# `build-targets.py`가 이미 그 관례로 처리한다 — 여기서 다시 구현하지 않는다.
#
# 낡은 버전 문자열 감사는 **만들었다가 뺐다**(2026-08-27, decision-log 참고).
# superpowers(`.version-bump.json`)가 감사를 두는 이유는 그쪽이 매니페스트 6개를
# **손으로** 편집하기 때문이다. 이 레포는 생성물이라 그 실패 모드 자체가 없다 —
# claim이 실릴 수 있는 자리(타겟 매니페스트 §14, SSOT↔CHANGELOG §6, README)가 전부
# 이미 다른 게이트로 막혀 있다. 실제로 만들어 실물 레포에 돌려본 결과 93건 중
# 압도적 다수가 "버전을 주장"이 아니라 "과거 사고를 버전으로 회고"하는 코드 주석
# (mention)이었다 — 그 둘은 문자열 매칭으로 못 가른다. **읽히지 않는 리포트는 없는
# 도구보다 나쁘다** — 있다고 착각하게 만든다. 다시 만들기 전에 이 판단을 재확인해라.
#
# 사용:
#   scripts/bump-version.sh <new-version> [--repo-root <path>]
#
# 종료코드:
#   0 = 성공(SSOT 갱신 + 재생성 + 자기검증 전부 통과)
#   1 = 버전 형식 오류 / SSOT 부재·갱신 실패 / 재생성 실패 / 자기검증 실패
#
set -euo pipefail

usage() {
  echo "Usage: scripts/bump-version.sh <new-version> [--repo-root <path>]" >&2
  exit 1
}

[ $# -ge 1 ] || usage
NEW_VERSION="$1"
shift

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(git -C "$HERE" rev-parse --show-toplevel 2>/dev/null || pwd)"

while [ $# -gt 0 ]; do
  case "$1" in
    --repo-root)
      [ $# -ge 2 ] || usage
      ROOT="$2"
      shift 2
      ;;
    *)
      usage
      ;;
  esac
done

# semver 3-파트만 받는다 — "2.16"이나 "v2.16.0" 같은 변형은 매니페스트에 그대로
# 실리면 이후 §6(버전 sync)·§14(드리프트) 판정이 전부 이 값을 SSOT로 쓰므로
# 형식이 틀리면 여기서 명확히 거부하는 편이, 나중에 다른 게이트에서 원인불명으로
# 죽는 것보다 낫다.
if ! [[ "$NEW_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "✗ 버전 형식 오류: '$NEW_VERSION' — X.Y.Z 형식이어야 한다 (예: 2.16.0)" >&2
  exit 1
fi

cd "$ROOT" || exit 1

PLUGIN_JSON="plugins/common/.claude-plugin/plugin.json"
if [ ! -f "$PLUGIN_JSON" ]; then
  echo "✗ SSOT 없음: $PLUGIN_JSON" >&2
  exit 1
fi

OLD_VERSION="$(python3 -c "import json; print(json.load(open('$PLUGIN_JSON'))['version'])" 2>/dev/null)" || {
  echo "✗ $PLUGIN_JSON 에서 현재 버전을 읽지 못함(JSON 파싱 실패?)" >&2
  exit 1
}

echo "[bump-version] $OLD_VERSION → $NEW_VERSION"

# ── 1) SSOT 갱신 (원자적 쓰기 — 필드 순서·나머지 값 보존) ────────────────────────
if ! python3 - "$PLUGIN_JSON" "$NEW_VERSION" <<'PYEOF'
import json
import os
import sys

path, new_version = sys.argv[1], sys.argv[2]
data = json.loads(open(path, encoding="utf-8").read())
data["version"] = new_version
tmp = path + ".bump.tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")
os.replace(tmp, path)
PYEOF
then
  echo "✗ SSOT 갱신 실패: $PLUGIN_JSON" >&2
  exit 1
fi
echo "[bump-version] ✓ SSOT 갱신: $PLUGIN_JSON"

# ── 2) 곧바로 생성물 재생성 — 이게 이 스크립트의 존재 이유다 ─────────────────────
# --policy를 명시한다: build-targets.py의 --policy 기본값은 **그 스크립트 파일 자신의
# 위치** 기준이라 --repo-root와 무관하게 실제 레포의 packaging/targets.json으로
# 풀린다(build-targets.py 설계 그대로 — repo-local 값을 하드코딩하지 않기 위함).
# 여기서 생략하면 --repo-root로 스크래치 사본을 가리켜도 조용히 진짜 레포 정책을
# 쓰게 되어 테스트 격리가 깨진다(2026-08-27 스모크 테스트에서 실측).
if ! python3 "$HERE/build-targets.py" --repo-root "$ROOT" --policy "$ROOT/packaging/targets.json" --write; then
  echo "✗ 생성물 재생성 실패 (build-targets.py --write)" >&2
  exit 1
fi

# ── 3) 자기 검증 — 방금 쓴 결과가 정말 SSOT와 일치하는지, 추측하지 않고 확인한다 ──
if ! python3 "$HERE/build-targets.py" --repo-root "$ROOT" --policy "$ROOT/packaging/targets.json" --check; then
  echo "✗ 자기 검증 실패 — --write 직후인데 --check가 드리프트를 보고했다. 스크립트 버그다." >&2
  exit 1
fi
echo "[bump-version] ✓ 자기 검증: 생성물이 SSOT와 일치"

# ── 4) CHANGELOG 최상단 버전 — 경고만. verify-done.sh §6이 이미 강제하는 값이라
#       여기서 또 fail시키면 같은 규칙을 두 곳에 복제하는 셈이다(F-023과 같은 함정).
CL_VER="$(grep -oE '^## \[[0-9]+\.[0-9]+\.[0-9]+\]' CHANGELOG.md 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true)"
if [ "$CL_VER" != "$NEW_VERSION" ]; then
  printf '  \033[33m! CHANGELOG.md 최상단이 아직 %s 가 아니다(현재: %s) — verify-done.sh §6이 최종 판정한다.\033[0m\n' \
    "$NEW_VERSION" "${CL_VER:-없음}"
fi

echo "[bump-version] ✓ 완료: $OLD_VERSION → $NEW_VERSION"
