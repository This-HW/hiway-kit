#!/usr/bin/env python3
"""
Feedback Ledger — validation/review에서 반복 발견되는 결함 패턴을 누적하고,
session-start가 주입할 digest를 제공하는 학습 루프의 SSOT (Spec 3 / W-007).

핵심 안티-부채 장치는 Claude 재량이 아니라 코드에 있다:
  - 상한(CAP): 엔트리 수 제한
  - 중복제거(dedupe): category+pattern 정규화 키로 upsert (freq++)
  - 감쇠(decay): 상한 초과 시 frequency·recency 하위 제거

사용:
  - session-start.py가 load_digest()를 import해 주입 (읽기)
  - auto-dev T-merge가 CLI로 upsert (쓰기):
      python3 feedback_ledger.py upsert <category> <severity> <pattern...>
      python3 feedback_ledger.py digest [K]
      python3 feedback_ledger.py promote   (26-16, 아래 "스테이징→승격" 참고)

ledger 경로: <git-common-dir>/kit/ledger.md — **모든 워크트리가 공유**한다.
  구 위치(<project_root>/docs/works/feedback/ledger.md)는 작업 트리 안이라
  워크트리마다 갈라졌다. 남아 있으면 첫 실행이 **병합 이관**하고 .migrated 로 개명한다.
ledger 부재/파싱 실패 시 전 구간 무동작 (fail-open, opt-in).

## 스테이징 → 승격 (26-16, D-43)

컨트롤 프로젝트의 레지스트리가 있으면 이 ledger는 **세션 로컬 스테이징 버퍼**다 —
`promote()`가 승격에 성공하면 비운다. 없으면 지금까지처럼 이 ledger가 **내구
진실**이고 `/self-improve`가 직접 읽는다(폴백). 어느 쪽이든 upsert/parse/digest의
동작은 동일하다 — 달라지는 것은 `promote()`가 호출됐을 때뿐이다.

레지스트리 발견: `$(git rev-parse --git-common-dir)/kit/registry.json` 포인터를
읽는다(공유 gitdir — untracked, 클론과 함께 죽는다). 포인터는 `command`(argv)만
허용하고 `url`은 거절한다(D-48, exec 전용 — 이 킷이 자격증명을 다루지 않는다).
`describe` 동사를 호출해 능력을 협상하고, **`describe` 외의 동사 이름을 코드에
하드코딩하지 않는다**(D-42) — 실제로 호출할 승격 동사 이름은 포인터 파일 자신의
`promotionVerb` 필드(컨트롤이 쓰는 값, 킷 소스가 아니다)에서 읽거나, `describe`가
`write` 동사를 정확히 하나만 선언하면 그것으로 추론한다. 어느 쪽도 안 되면
승격을 보류하고 그 이유를 보고한다 — 추측으로 동사를 고르지 않는다.

신선도(D-49·D-50): `describe`의 선택적 `head` 필드를 현재 git HEAD와 대조한다.
일치하면 승격, 불일치면 보류(ledger 보존), 불일치가 연속 임계(3회)를 넘으면
레지스트리를 **미신뢰로 강등**하고 이후 호출은 폴백(내구 ledger 유지)으로
처리한다 — 이 강등 상태는 `$(git-common-dir)/kit/registry_trust.json`에 기록된다.
`head` 미선언은 오류가 아니라 "신선도 모름" 경고로만 남긴다 — 미선언 레지스트리에서
승격이 영구 차단되면 그 자체가 동작하지 않는 안전장치가 된다.

이 파일이 실제로 읽는 describe 필드는 **`verbs[].name` 과 `verbs[].effect`, 그리고
최상위 `head` 뿐**이다. D-42/D-44 스키마에는 `args`·`idempotent` 도 있으나 이 구현은
**둘 다 참조하지 않는다** — 있다고 적고 안 쓰는 것이 최악이므로 명시한다.
`idempotent` 를 안 봐도 되는 이유는 승격이 **성공분을 항상 차감**하기 때문이다(아래
`promote()`): 성공한 항목은 원장에서 빠지므로 다음 호출이 같은 동사를 재호출하지 않는다.
예외는 하나뿐이고 코드가 그 자리에 적어 뒀다 — 승격 직후 원장을 읽지 못해 차감을
건너뛴 경우, 다음 호출이 재승격한다(원장 파괴보다 낫다는 의도된 선택). 비멱등 동사를
쓰는 레지스트리는 그 경로에서 중복을 받을 수 있다.

설계 공백 하나도 명시한다: D-42/D-44의 describe 스키마에는 "이 동사가 승격/등록용이다"를
나타내는 필드가 없다. `promotionVerb`를 포인터 파일(컨트롤 소유·비-repo 파일)에 두는 것은
그 필드가 킷 소스에 박히는 것이 아니라 **컨트롤이 자기 레지스트리를 소개할 때
스스로 선언하는 값**이라 D-42의 "동사 이름을 하드코딩하지 않는다"를 어기지 않는다
— 다만 이 구체적 필드명 자체는 설계 문서에 명문화돼 있지 않은 이 구현의 해석이다.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager, suppress
from datetime import datetime
from pathlib import Path

CAP = 50  # 최대 엔트리 수
DEFAULT_DIGEST_K = 5  # 주입할 상위 교훈 수
DIGEST_CHAR_CAP = 1200  # digest 문자 상한 (토큰 예산 보호)
VALID_CATEGORIES = {"lint", "security", "architecture", "test", "convention"}
VALID_SEVERITIES = {"critical", "high", "medium", "low"}

# ── 26-16: 레지스트리 스테이징→승격 (D-42·D-43·D-48·D-49·D-50) ─────────
_REGISTRY_POINTER_REL = ("kit", "registry.json")
_TRUST_STATE_REL = ("kit", "registry_trust.json")
_DESCRIBE_TIMEOUT_SECONDS = 10
_PROMOTE_CALL_TIMEOUT_SECONDS = 10
_MISMATCH_DEMOTE_THRESHOLD = 3  # head 연속 불일치 임계 — 초과 시 레지스트리 미신뢰 강등
_LOCK_TIMEOUT_SECONDS = 5  # 락 획득 데드라인 — 초과 시 무락 진행(fail-open)
# 승격 **총량** 데드라인. 항목당 타임아웃만 있으면 최악은 CAP(50) × 10s = ~500초이고,
# 그 시간 내내 호출자(세션 훅·파이프라인)가 블로킹된다. 락에는 5초 데드라인을 걸어
# "정지한 프로세스 때문에 파이프라인이 무한 대기하지 않게" 해 놓고 그보다 100배 긴
# 경로를 열어 두는 것은 같은 파일 안의 비대칭이다. 초과분은 실패로 계상돼 partial 로
# 떨어지고, 남은 항목은 원장에 남아 다음 호출이 재시도한다 — 유실되지 않는다.
_PROMOTE_TOTAL_BUDGET_SECONDS = 60

_HEADER = (
    "# Feedback Ledger\n\n"
    "> 자동 생성 (Spec 3 / W-007). validation·review에서 잡힌 결함 패턴 누적.\n"
    f"> 상한 {CAP}개, frequency·recency 기준 감쇠. 수동 편집 가능하나 형식 유지 필요.\n\n"
    "| id | category | pattern | frequency | last_seen | severity |\n"
    "| -- | -------- | ------- | --------- | --------- | -------- |\n"
)


def _project_root() -> Path:
    proj = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if proj:
        return Path(proj)
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip())
    except Exception:
        pass
    return Path.cwd()


def legacy_ledger_path(root: Path | None = None) -> Path:
    """구 위치 — **워크트리마다 갈라지던** 자리. 이관 원본으로만 쓴다."""
    root = root or _project_root()
    return root / "docs" / "works" / "feedback" / "ledger.md"


def ledger_path(root: Path | None = None) -> Path:
    """원장 정본 경로. **공용 gitdir 아래**가 기본이다.

    **왜 옮겼나.** 구 위치(`docs/works/feedback/ledger.md`)는 **작업 트리 안**이라
    워크트리마다 별도 파일이 된다. 그런데 이 킷은 워크트리 운영을 권장한다
    (`isolation: worktree`·`parallel-worktree`·`control-loop`) — 권장을 따르는 순간
    **학습 원장이 세션마다 갈라진다.** 실측: 같은 레포의 두 워크트리에 서로 다른
    50항목 원장이 있었고, 한쪽에서 배운 것이 다른 쪽에 영영 도달하지 않았다.

    `<git-common-dir>/kit/` 은 **모든 워크트리가 공유**하고 구조적으로 untracked 이며
    git 만 있으면 되므로 하네스와도 무관하다 — 자식 마커·레지스트리 포인터가 이미
    거기 산다. 원장도 같은 자리로 올린다.

    git 저장소가 아니면(또는 조회 실패) 구 위치로 물러선다 — 이 헬퍼는 임의의
    디렉토리에서도 동작해야 한다(fail-open).
    """
    root = root or _project_root()
    common = _git_common_dir(root)
    if common is None:
        return legacy_ledger_path(root)
    return common / "kit" / "ledger.md"


def _merge_entries(base: list[dict], incoming: list[dict]) -> list[dict]:
    """dedupe 키가 같으면 frequency 합산·최근 날짜 채택. 이관용 병합."""
    index = {_normalize(e["category"], e["pattern"]): e for e in base}
    for src in incoming:
        key = _normalize(src["category"], src["pattern"])
        hit = index.get(key)
        if hit is None:
            index[key] = dict(src)
            continue
        hit["frequency"] += src["frequency"]
        hit["last_seen"] = max(hit["last_seen"], src["last_seen"])
    merged = list(index.values())
    # id 재채번 — 두 원장의 F-번호가 충돌할 수 있다.
    for i, e in enumerate(sorted(merged, key=lambda x: x["id"]), start=1):
        e["id"] = f"F-{i:03d}"
    return merged


def migrate_legacy_ledger(root: Path | None = None) -> str:
    """구 위치 원장을 정본으로 **병합** 이관한다. 반환: 'merged' | 'noop'.

    **이동이 아니라 병합인 이유**: 워크트리마다 원장이 갈려 있었으므로 먼저 도착한
    하나만 채택하면 나머지의 학습이 사라진다. 각 워크트리가 자기 것을 병합해 올린다.

    이관 후 원본은 `.migrated` 접미사로 **개명**한다 — 지우지 않는 것은 되돌릴 수
    있게 하기 위해서고, 개명하는 것은 다음 실행이 같은 것을 또 병합해 frequency 를
    부풀리지 않게 하기 위해서다(멱등).

    심링크는 건드리지 않는다 — 사용자가 공유 원장으로 링크해 둔 경우다(F7).
    """
    root = root or _project_root()
    legacy = legacy_ledger_path(root)
    target = ledger_path(root)
    if target == legacy:
        return "noop"
    # 잠금 **밖**의 검사는 값싼 조기 탈출일 뿐 판정 근거가 아니다.
    if legacy.is_symlink() or not legacy.is_file():
        return "noop"
    with _ledger_lock(target):
        # **잠금 안에서 다시 본다.** 밖의 검사와 실제 병합 사이에 다른 프로세스가 이미
        # 이관했을 수 있다 — 그대로 진행하면 같은 항목을 두 번 세어 frequency 가 부푼다.
        # 개명도 **잠금 안**이어야 한다. 밖에 두면 두 번째 프로세스가 이 재검사를 통과해
        # 버린다(검사와 상태 변경 사이의 틈이 곧 TOCTOU다 — 이 레포가 경로 봉쇄에서
        # 배운 것과 같은 형태다).
        if legacy.is_symlink() or not legacy.is_file():
            return "noop"
        incoming = parse_ledger(legacy)
        if not incoming:
            return "noop"
        # **개명이 먼저다** (ATK-008). 병합·쓰기를 먼저 하고 개명을 나중에 하면 둘이
        # 원자적이지 않아, 개명이 실패했을 때(권한·파일시스템·경합) 구 원장이 그대로
        # 남는다. 그러면 다음 SessionStart 마다 같은 항목이 다시 병합돼 frequency 가
        # 부푼다 — frequency 는 digest 순위를 정하므로 부푼 항목이 진짜 반복 결함을
        # digest 밖으로 밀어낸다. 개명이 성공한 뒤에는 구 경로가 없으므로 재실행돼도
        # 중복 병합이 없다(멱등).
        #
        # 반대 방향의 손해는 감수한다: 개명 뒤 쓰기가 실패하면 이번 병합분이 정본에
        # 반영되지 않는다. 그러나 원본은 .migrated 로 **디스크에 남아 있어** 되돌릴 수
        # 있고, 반대편(중복 계수)은 조용히 순위를 오염시켜 되돌릴 수 없다.
        backup = legacy.with_suffix(".md.migrated")
        legacy.rename(backup)
        merged = _merge_entries(parse_ledger(target), incoming)
        kept = _decay(merged)
        _write_ledger(target, kept)
    dropped = len(merged) - len(kept)
    if dropped:
        # **조용히 지우지 않는다.** 상한·감쇠는 설계된 동작이지만, 이관 중에 일어나면
        # 사용자가 고르지 않은 유실로 보인다. 원본은 .migrated 로 남아 있으므로
        # 되돌릴 수 있다는 것까지 같이 알린다.
        print(
            f"[feedback_ledger] 원장을 {target} 로 병합 이관했습니다 "
            f"(상한 {CAP} 초과 {dropped}건은 감쇠 규칙으로 제외 — "
            f"원본은 {backup.name} 로 보존).",
            file=sys.stderr,
        )
    return "merged"


def _sanitize(pattern: str) -> str:
    """pattern을 ledger 셀에 안전하게 — '|'(테이블 구분자)·개행 제거, 공백 정규화.

    review 결함에 '|'(예: 'string | null', 'A | B')가 포함되면 마크다운 행이
    깨져 파싱 시 엔트리가 유실되고 dedupe가 무력화된다 (안티-부채 설계 붕괴 방지).
    """
    return " ".join(pattern.replace("|", "/").split())


def _normalize(category: str, pattern: str) -> str:
    """dedupe 키 — category + 소문자/sanitize된 pattern."""
    return f"{category}::{_sanitize(pattern).lower()}"


class LedgerUnreadable(Exception):
    """원장이 **있는데 읽지 못했다**. 빈 원장과 구별하기 위한 신호다.

    둘을 같은 값(빈 리스트)으로 뭉개면 그 직후 `upsert` 가 `_write_ledger` 로 파일을
    통째로 교체해 **최대 50개 학습 항목이 조용히 사라진다.** 이 파일은 스스로
    *"fail-open 은 '막지 않는다'이지 '지운다'가 아니다"* 라고 적어 놓고(promote 주석)
    읽기 경로에는 그 원칙을 적용하지 않고 있었다.

    발생 조건(전부 평범하다): 손편집·부분쓰기로 생긴 `UnicodeDecodeError`,
    공유 `.git/kit/` 를 다른 uid 가 먼저 만들어 생긴 `PermissionError`,
    병렬 실행 중 `EMFILE`.
    """


def parse_ledger(path: Path) -> list[dict]:
    """ledger.md 테이블을 파싱.

    **부재는 빈 리스트(정상), 읽기 실패는 예외다.** 이 구분이 없으면 호출부가
    "볼 게 없었다"와 "못 봤다"를 같게 취급해 원장을 덮어쓴다 (`LedgerUnreadable` 참고).
    """
    entries: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return entries  # 부재 = 정상. 아직 배운 게 없을 뿐이다.
    except (OSError, UnicodeDecodeError, ValueError) as err:
        raise LedgerUnreadable(f"{path}: {err}") from err
    for line in lines:
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 6:
            continue
        if cells[0].lower() == "id" or set(cells[0]) <= {"-", ":"}:
            continue  # 헤더/구분선
        try:
            freq = int(cells[3])
        except ValueError:
            continue
        entries.append(
            {
                "id": cells[0],
                "category": cells[1],
                "pattern": cells[2],
                "frequency": freq,
                "last_seen": cells[4],
                "severity": cells[5],
            }
        )
    return entries


def _decay(entries: list[dict]) -> list[dict]:
    """상한 초과 시 frequency↑, last_seen↑(최근) 우선 보존, 하위 제거."""
    entries.sort(key=lambda e: (e["frequency"], e["last_seen"]), reverse=True)
    return entries[:CAP]


@contextmanager
def _ledger_lock(path: Path):
    """ledger read-modify-write 직렬화 (W-011).

    auto-dev가 T-review/T-security를 병렬 실행하며 둘 다 upsert를 호출하는
    시나리오가 스킬 설계에 내장돼 있다 — 락 없이는 lost-update(한쪽 기록 소실)와
    F-id 중복 채번이 발생한다. 별도 락 파일에 flock 배타 락을 잡는다.

    fcntl.flock은 darwin/linux 전용(kit 대상 플랫폼). 락 파일 생성/획득 실패 시
    무락으로 진행한다 — ledger는 학습 보조 데이터라 가용성 우선(fail-open).

    - 락 파일은 저장소 트리가 아니라 사용자별 `$TMPDIR/claude-{uid}`(0700)에 둔다 —
      repo 안 `.lock`은 커밋 오염 + auto-dev 마커 지문(porcelain) 교란을 낳았다(F10).
    - 락 파일은 O_NOFOLLOW로 연다(CWE-59).
    - 블로킹 flock 대신 LOCK_NB + 재시도(_LOCK_TIMEOUT_SECONDS 데드라인) —
      락 보유 프로세스가 정지해도 파이프라인이 무한 대기하지 않는다. 데드라인 초과 시
      무락으로 진행하되 **stderr 경고**를 남겨 lost-update 재발을 관측 가능하게 한다(F9).
    """
    lock_file = _lock_path_for(path)
    try:
        fd = os.open(str(lock_file), os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        fh = os.fdopen(fd, "w")
    except Exception:
        yield
        return
    locked = False
    try:
        deadline = time.monotonic() + _LOCK_TIMEOUT_SECONDS
        while True:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    print(
                        "[feedback_ledger] lock timeout — proceeding unlocked "
                        "(동시 upsert 시 기록 유실 가능)",
                        file=sys.stderr,
                    )
                    break  # 데드라인 초과 → 무락 진행(fail-open)
                time.sleep(0.05)
        yield
    finally:
        try:
            if locked:
                fcntl.flock(fh, fcntl.LOCK_UN)
        finally:
            fh.close()


def _lock_path_for(path: Path) -> Path:
    """ledger 경로에 대응하는 사용자별 락 파일 경로 (repo 트리 밖)."""
    try:
        uid = os.getuid()
    except AttributeError:
        uid = os.environ.get("USER", "user")
    # 경로 지문(락 파일명)일 뿐 보안 용도가 아니다 → FIPS 환경에서도 동작하도록 명시.
    key = hashlib.md5(str(path.resolve()).encode(), usedforsecurity=False).hexdigest()[
        :12
    ]
    fallback = path.with_name(path.name + ".lock")  # 폴백: 기존 위치
    d = Path(tempfile.gettempdir()) / f"claude-{uid}"
    try:
        d.mkdir(mode=0o700, exist_ok=True)
    except Exception:
        return fallback
    # `exist_ok=True` 는 **이미 있는 디렉토리를 그대로 받아들이고**, `mode=` 는 생성
    # 시에만 적용된다. 다중 사용자 머신의 공용 /tmp 에서 이 이름이 선점돼 있으면
    # (소유자가 다르거나 group/other 쓰기 가능) 남이 통제하는 디렉토리에 락 파일을
    # 연다 — O_NOFOLLOW 는 락 **파일**의 심링크만 막지 디렉토리 자체는 막지 못한다(M-1).
    if not _lock_dir_is_safe(d):
        return fallback
    return d / f"ledger_{key}.lock"


def _lock_dir_is_safe(d: Path) -> bool:
    """락 디렉토리를 재사용해도 되는가 — 실제 디렉토리 · 내 소유 · 남이 쓸 수 없음.

    `lstat` 을 쓴다(`stat` 이 아니라) — 심링크면 그 자체로 거절해야 하는데 `stat` 은
    링크를 따라가 대상 디렉토리의 속성을 보여 준다.
    """
    try:
        st = os.lstat(str(d))
    except OSError:
        return False
    if not stat.S_ISDIR(st.st_mode):
        return False  # 심링크·일반 파일 등 — 디렉토리가 아니면 쓰지 않는다
    try:
        if st.st_uid != os.getuid():
            return False
    except AttributeError:
        pass  # getuid 없는 플랫폼 — 소유권 개념이 없으니 퍼미션 검사만 한다
    return not st.st_mode & (stat.S_IWGRP | stat.S_IWOTH)


def _symlinked_target_is_safe(path: Path, real: Path) -> bool:
    """원장이 심링크일 때 그 대상을 따라가도 되는가 — **내 소유일 때만**.

    심링크 **보존**은 의도된 기능이다(F7: ledger.md 를 공유 원장으로 링크해 두는 사용).
    그래서 봉쇄가 아니라 **소유권 확인**으로 가른다 — 내가 만든 링크 대상은 따라가고,
    남이 심어 둔 것은 따라가지 않는다. 같은 파일의 락 디렉토리 검사
    (`_lock_dir_is_safe`)와 **같은 기준**이다.

    **왜 필요했나.** 이전 독스트링은 *"ledger.md 는 저장소 내부의 사용자 통제 파일이라
    심링크 추적이 안전하다"* 고 적었다 — 그건 **검사가 아니라 가정**이었다. 같은 파일이
    락 경로에는 소유권 검사를 걸어 두고 원장 경로에는 안 걸었다는 비대칭이 근거다
    (`docs/conventions/path-containment.md` 규칙 1·3: 한 번만 resolve 하고, 읽기 경로도 본다).

    **한계는 정직하게 적는다.** 같은 uid 로 도는 공격자(공유 CI 러너에서 모두가 같은
    계정인 경우)는 이 검사를 통과한다. 그 시나리오에서는 `.git/hooks/` 도 쓸 수 있으므로
    이 검사가 마지막 방어선이 아니다 — 여기서 막는 것은 **다른 사용자가 심어 둔 링크**다.
    """
    if not path.is_symlink():
        return True
    try:
        st = os.lstat(str(real))
    except OSError:
        return True  # 대상이 아직 없다 — 우리가 만들 것이므로 정상 경로다
    try:
        return st.st_uid == os.getuid()
    except AttributeError:
        return True  # 소유권 개념이 없는 플랫폼


def _write_ledger(path: Path, entries: list[dict]) -> None:
    """tmp + os.replace 원자 교체 **+ fsync** — 부분 쓰기·크래시 유실 방지.

    시그니처·계약은 `export_harness.py::_atomic_write` 와 **동일하다**
    (D-15: 구현은 여러 벌, 계약만 하나). **한쪽을 고치면 다른 쪽도 고쳐라.**
    공용 모듈로 뽑지 않는 이유: 두 파일 모두 킷 내부 의존이 없는 standalone 이고
    플러그인 캐시에서 CLI 로 직접 실행된다 — 공용 import 경로는 그 호출 형태에서
    성립하지 않는다(소비자 환경을 깨는 쪽이 중복보다 나쁘다).

    대상이 심링크면 링크 자체가 아니라 **링크가 가리키는 실제 파일**을 교체한다 —
    사용자가 ledger.md를 공유 원장으로 심링크해 둔 경우를 보존한다(F7). 다만 그
    대상이 **내 소유일 때만** 따라간다(`_symlinked_target_is_safe`).
    """
    real = Path(os.path.realpath(path))
    if not _symlinked_target_is_safe(path, real):
        # **쓰지 않고 조용히 물러선다(fail-open).** 학습 루프는 본 작업을 막지 않는다 —
        # 여기서 예외를 올리면 남이 심어 둔 링크 하나로 세션이 죽는다. 다만 조용히
        # 넘어가지도 않는다: 관측 가능해야 다음 사람이 원인을 찾는다.
        print(
            f"[feedback_ledger] 원장이 남의 소유 파일로 링크돼 있다 — 쓰지 않는다: {path}",
            file=sys.stderr,
        )
        return
    real.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        f"| {e['id']} | {e['category']} | {e['pattern']} | "
        f"{e['frequency']} | {e['last_seen']} | {e['severity']} |"
        for e in entries
    ]
    text = _HEADER + "\n".join(rows) + ("\n" if rows else "")
    # 기존 파일의 모드를 보존한다. 무조건 0644 로 덮으면 공유 원장을 0600 으로 두거나
    # 팀이 0664 로 공동 편집하던 설정이 조용히 바뀐다 — 원장은 심링크로 공유되는
    # 것이 의도된 기능(F7)이므로 모드도 남의 결정이다.
    try:
        mode = os.stat(real).st_mode & 0o7777
    except OSError:
        cur = os.umask(0)
        os.umask(cur)
        mode = 0o666 & ~cur
    # mkstemp: 이름이 예측 불가하고 O_EXCL 로 원자 생성된다(0600).
    #   이전에는 `<name>.tmp.<pid>` 고정 이름이었다 — 이름을 선점당하면 죽고,
    #   컨테이너처럼 낮은 PID 가 재사용되는 환경에서는 우연한 충돌도 가능하다.
    fd, tmp_name = tempfile.mkstemp(
        dir=str(real.parent), prefix=f".{real.name}.", suffix=".tmp"
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            # tmp+replace 는 **프로세스 사망**에는 원자적이지만 호스트 크래시에는
            # 아니다. rename 만 반영되고 데이터가 안 반영되면 최대 CAP 개의 학습
            # 항목이 빈/잘린 원장으로 남는다 — 이 파일에서 고친 유실 결함 둘
            # (`promote()` 전체 비우기 · `parse_ledger` 부재/실패 뭉갬)과 같은 계열이다.
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, real)
        # 디렉토리 fsync 실패는 무시한다 — 일부 파일시스템·플랫폼이 지원하지 않고,
        # 여기서 죽으면 fail-open 원칙(학습 루프가 본 작업을 막지 않는다)이 깨진다.
        with suppress(OSError):
            dfd = os.open(str(real.parent), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
    finally:
        with suppress(OSError):
            tmp.unlink()


def upsert(category: str, severity: str, pattern: str, root: Path | None = None) -> str:
    """결함 패턴을 추가하거나 기존 freq를 증가.

    반환: 'added' | 'incremented' | 'skipped'(원장을 읽지 못해 쓰지 않음).

    parse→수정→write 전체가 _ledger_lock 안에서 실행된다 — 병렬 upsert에서도
    양쪽 기록이 모두 보존되고 F-id가 중복 채번되지 않는다.
    """
    if category not in VALID_CATEGORIES:
        # **재분류는 유지하되 조용히 하지 않는다.** 바로 아래 `severity` 는 화이트리스트
        # 밖 값을 `''` 로 비워 **기존값을 보존**하는데, category 만 강제 재분류였다 —
        # 비대칭이다. 게다가 `_normalize` 가 category 를 dedupe 키에 넣으므로, 오타
        # 하나가 잘못된 버킷에 누적되면서 **키까지 오염**시킨다(같은 결함이 두 항목으로
        # 갈리거나 무관한 항목과 합쳐진다).
        #
        # category 는 severity 와 달리 dedupe 키의 일부라 빈 값으로 둘 수 없으므로
        # 재분류 자체는 유지한다. 고치는 것은 **침묵**뿐이다 — 무엇을 무엇으로 바꿨는지
        # 한 줄 남기면 오타를 낸 호출자가 그 자리에서 본다.
        print(
            f"[feedback_ledger] category {category!r} 는 화이트리스트 밖이다 "
            f"({', '.join(sorted(VALID_CATEGORIES))}) — 'convention' 으로 기록한다.",
            file=sys.stderr,
        )
        category = "convention"
    # severity도 화이트리스트 강제 — pattern만 sanitize하는 비대칭은 '|'/개행 주입으로
    # 테이블 행을 깨뜨려 엔트리 유실·세션 주입 벡터가 된다 (ATK-006/M-2).
    # 화이트리스트 밖 값은 ''로 비워 기존 semantics 유지(빈 값 = 기존 severity 보존,
    # 신규 엔트리는 medium 기본값).
    severity = (severity or "").strip().lower()
    if severity not in VALID_SEVERITIES:
        severity = ""
    pattern = _sanitize(pattern)
    _try_migrate(root)
    path = ledger_path(root)
    # 로컬 날짜를 유지하되 tz를 명시(naive 시각 금지) — 원장 날짜는 사용자 기준일이다.
    today = datetime.now().astimezone().date().isoformat()
    with _ledger_lock(path):
        try:
            entries = parse_ledger(path)
        except LedgerUnreadable as err:
            # **읽지 못한 원장 위에 쓰지 않는다.** 여기서 빈 리스트로 진행하면 그 직후
            # `_write_ledger` 가 파일을 통째로 교체해 학습 항목이 전부 사라진다.
            # 작업은 막지 않는다(fail-open) — 배우지 못할 뿐이다.
            print(f"[feedback_ledger] 원장을 읽지 못해 기록을 건너뛴다 — {err}", file=sys.stderr)
            return "skipped"
        key = _normalize(category, pattern)
        for e in entries:
            if _normalize(e["category"], e["pattern"]) == key:
                e["frequency"] += 1
                e["last_seen"] = today
                e["severity"] = severity or e["severity"]
                _write_ledger(path, _decay(entries))
                return "incremented"
        # id 충돌 방지: 기존 최대 번호 + 1
        nums = [
            int(e["id"][2:])
            for e in entries
            if e["id"].startswith("F-") and e["id"][2:].isdigit()
        ]
        next_id = f"F-{(max(nums) + 1) if nums else len(entries) + 1:03d}"
        entries.append(
            {
                "id": next_id,
                "category": category,
                "pattern": pattern,
                "frequency": 1,
                "last_seen": today,
                "severity": severity or "medium",
            }
        )
        _write_ledger(path, _decay(entries))
        return "added"


def _try_migrate(root: Path | None) -> None:
    """이관은 **본 작업을 막지 않는다** — 실패하면 조용히 구 위치 그대로 동작한다.

    학습 루프는 opt-in·fail-open 이 원칙이다(rules/feedback-loop.md). 이관 실패로
    upsert/digest 가 죽으면 그 원칙이 깨진다.

    **다만 완전히 침묵하지는 않는다** — 초판은 `contextlib.suppress(Exception)` 으로
    삼켜, 개명 실패로 구 원장이 남아 매 세션 중복 병합되는 상태가 어디에서도 드러나지
    않았다(ATK-008). fail-open 은 유지하되 stderr 한 줄로 관측 가능하게 한다.

    warning-signal §4 — **이 경고가 도는 조건을 한 문장으로**: *"구 원장이 실제로
    존재해서 이관을 시도했고, 그 이관이 예외로 실패했을 때만 발화한다."* 구 원장이
    없으면 `migrate_legacy_ledger` 가 예외 없이 "noop" 을 돌려주므로 정상 운영에서는
    한 번도 발화하지 않는다 — 상시 참인 경고가 아니다.
    """
    try:
        migrate_legacy_ledger(root)
    except Exception as ex:
        print(
            f"[feedback_ledger] warning: 구 원장 이관 실패 — 구 위치 그대로 진행합니다 "
            f"({type(ex).__name__}: {ex}). 반복되면 구 원장이 매 세션 재병합돼 "
            f"frequency 가 부풀 수 있습니다.",
            file=sys.stderr,
        )


def load_digest(top_k: int = DEFAULT_DIGEST_K, root: Path | None = None) -> str:
    """주입용 digest 문자열. ledger 부재/빈/읽기 실패 시 빈 문자열 (fail-open).

    **읽기 전용 경로라 실패를 삼켜도 안전하다** — 쓰기 경로(`upsert`)와 달리 여기서는
    "못 읽음"이 데이터를 파괴하지 않는다. 다만 조용히 넘기지는 않는다.
    """
    _try_migrate(root)
    try:
        entries = parse_ledger(ledger_path(root))
    except LedgerUnreadable as err:
        print(f"[feedback_ledger] 원장을 읽지 못해 digest 를 비운다 — {err}", file=sys.stderr)
        return ""
    if not entries:
        return ""
    entries.sort(key=lambda e: (e["frequency"], e["last_seen"]), reverse=True)
    top = entries[:top_k]
    lines = ["과거 validation에서 반복된 결함 — 구현/리뷰 시 우선 점검:"]
    for e in top:
        lines.append(
            f"  - [{e['category']}/{e['severity']}] {e['pattern']} (x{e['frequency']})"
        )
    digest = "\n".join(lines)
    if len(digest) > DIGEST_CHAR_CAP:
        digest = digest[:DIGEST_CHAR_CAP].rstrip() + " …"
    return digest


def _git_common_dir(root: Path) -> Path | None:
    """공유 gitdir 절대경로. 없거나 git 리포지토리가 아니면 None(fail-open).

    `--git-common-dir`은 주 체크아웃에서 상대경로를 반환하므로(§14.7 구현 함정)
    반드시 `root` 기준으로 resolve한 뒤 끝까지 그 결과만 쓴다.
    """
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    p = Path(r.stdout.strip())
    if not p.is_absolute():
        p = (root / p).resolve()
    return p


def _current_head(root: Path) -> str | None:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _pointer_source_is_safe(pointer_path: Path) -> bool:
    """포인터 파일과 **그 부모 디렉토리**가 내 소유이고 남이 쓸 수 없는가.

    이 포인터의 `command` 는 `subprocess.run` 으로 **실행**된다 — 이 파일에서 가장
    위험한 경로다. 그런데 같은 파일이 `/tmp` 락 디렉토리에는 정확히 이 검사를 걸어
    두고(`_lock_dir_is_safe`), 원장 심링크에도 걸어 두고(`_symlinked_target_is_safe`),
    **exec 경로에만 걸어 두지 않았다.** 그 비대칭이 이 함수의 근거다
    (`docs/conventions/path-containment.md` 규칙 3: 읽기 경로도 봉쇄한다 — 여기서는
    읽은 값이 곧 실행이므로 더 강하게 적용된다).

    부모 디렉토리까지 보는 이유: 파일만 검사하면 남이 쓸 수 있는 디렉토리에서
    파일을 갈아치우는 경로가 남는다. `lstat` 을 쓴다(`stat` 이 아니라) — 심링크는
    그 자체로 거절해야 하는데 `stat` 은 링크를 따라가 대상의 속성을 보여 준다.

    **한계는 정직하게 적는다.** 같은 uid 로 도는 공격자(공유 CI 러너에서 모두가 같은
    계정인 경우)는 이 검사를 통과한다. 그 시나리오에서는 `.git/hooks/` 도 쓸 수
    있으므로 이 검사가 마지막 방어선이 아니다 — 여기서 막는 것은 **다른 사용자가
    심어 두거나 갈아치울 수 있는 포인터**다.
    """
    for target, want_dir in ((pointer_path.parent, True), (pointer_path, False)):
        try:
            st = os.lstat(str(target))
        except OSError:
            return False
        if want_dir and not stat.S_ISDIR(st.st_mode):
            return False
        if not want_dir and not stat.S_ISREG(st.st_mode):
            return False  # 심링크·특수 파일 — 따라가지 않는다
        try:
            if st.st_uid != os.getuid():
                return False
        except AttributeError:
            pass  # getuid 없는 플랫폼 — 소유권 개념이 없으니 퍼미션 검사만 한다
        if st.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            return False
    return True


def discover_registry_pointer(root: Path | None = None) -> dict | None:
    """컨트롤 레지스트리 포인터를 읽는다. 없거나 부적합하면 None(fail-open, 폴백).

    `url` 필드가 있으면 무조건 거절한다(D-48) — 이 킷은 exec 전용 계약이다.
    포인터 파일·부모 디렉토리의 소유권도 검사한다(`_pointer_source_is_safe`) —
    여기서 읽은 `command` 는 실행되므로 남이 통제하는 파일을 신뢰하지 않는다.
    """
    root = root or _project_root()
    common = _git_common_dir(root)
    if common is None:
        return None
    pointer_path = common.joinpath(*_REGISTRY_POINTER_REL)
    if not pointer_path.exists():
        return None  # 없음은 정상 경로다(폴백) — 경고하지 않는다
    if not _pointer_source_is_safe(pointer_path):
        # 조용히 넘어가지 않는다: 관측 가능해야 다음 사람이 원인을 찾는다.
        # 다만 막지도 않는다 — 폴백(킷 ledger 가 내구 진실)으로 계속 돈다.
        print(
            "[feedback_ledger] 레지스트리 포인터가 남의 소유이거나 남이 쓸 수 있다 — "
            f"실행하지 않고 폴백한다: {pointer_path}",
            file=sys.stderr,
        )
        return None
    try:
        raw = pointer_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or "url" in data:
        return None
    command = data.get("command")
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(c, str) for c in command)
    ):
        return None
    return data


def describe_registry(command: list[str], cwd: Path | None = None) -> dict | None:
    """`command + ['describe']`를 실행해 파싱된 응답을 반환한다.

    `cwd`는 대상 레포 루트를 넘긴다 — 레지스트리가 "이 응답이 반영하는 레포
    커밋"(head)을 계산할 때 어느 레포를 봐야 하는지 알 수 있게 한다.

    실행 실패·타임아웃·비-JSON·스키마 밖 형태는 전부 None — 부분 신뢰하지 않는다
    (D-44: "describe 부재·파싱 실패·스키마 미해석 → 전면 폴백").
    """
    try:
        r = subprocess.run(
            [*command, "describe"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_DESCRIBE_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    try:
        parsed = json.loads(r.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict) or not isinstance(parsed.get("verbs"), list):
        return None
    return parsed


def _read_trust_state(common: Path) -> dict:
    p = common.joinpath(*_TRUST_STATE_REL)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return {"consecutiveMismatches": 0, "untrusted": False}


def _write_trust_state(common: Path, state: dict) -> None:
    p = common.joinpath(*_TRUST_STATE_REL)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state), encoding="utf-8")
    except OSError:
        pass  # 신뢰 상태 기록 실패는 치명적이지 않다 — 다음 승격 시도가 다시 판단한다


def _select_promotion_verb(pointer: dict, verbs: list[dict]) -> tuple[str | None, str]:
    """승격에 쓸 동사 이름을 고른다. 실패 시 (None, 이유)를 반환한다.

    D-42(동사 이름 하드코딩 금지)를 지키기 위해 이름은 코드가 아니라
    포인터 파일(컨트롤 소유)의 `promotionVerb`에서 읽거나, describe가 write
    동사를 정확히 하나만 선언하면 그것으로 추론한다 — 추측이 아니라 명시적 선언 우선.
    """
    declared_names = {v.get("name") for v in verbs if isinstance(v, dict)}
    explicit = pointer.get("promotionVerb")
    if explicit is not None:
        if explicit in declared_names:
            return explicit, ""
        return None, f"registry.json의 promotionVerb '{explicit}'가 describe에 없다"
    write_verbs = [
        v.get("name")
        for v in verbs
        if isinstance(v, dict) and v.get("effect") == "write" and v.get("name")
    ]
    if len(write_verbs) == 1:
        return write_verbs[0], ""
    return (
        None,
        "승격 동사를 특정할 수 없다 — registry.json에 promotionVerb를 지정하거나 "
        "write 동사를 정확히 하나만 선언해야 한다",
    )


def _call_promotion_verb(
    command: list[str], verb_name: str, entries: list[dict], root: Path
) -> tuple[list[dict], list[str]]:
    """승격 동사를 항목마다 호출한다. **락 밖에서** 돈다 (ATK-001).

    항목당 타임아웃(`_PROMOTE_CALL_TIMEOUT_SECONDS`)과 **총량 예산**
    (`_PROMOTE_TOTAL_BUDGET_SECONDS`)을 둘 다 건다 — 항목당만 있으면 최악이
    CAP × 항목당 = ~500초이고 그동안 호출자가 블로킹된다.

    반환: (승격에 성공한 항목들, 실패 사유들).
    """
    succeeded: list[dict] = []
    failures: list[str] = []
    deadline = time.monotonic() + _PROMOTE_TOTAL_BUDGET_SECONDS
    for idx, e in enumerate(entries):
        if time.monotonic() >= deadline:
            # 남은 항목은 **호출하지 않고** 실패로 계상한다. 차감은 성공분만 하므로
            # (F-2) 이것들은 원장에 그대로 남아 다음 호출이 이어서 시도한다.
            failures.append(
                f"총량 예산 {_PROMOTE_TOTAL_BUDGET_SECONDS}초 초과 — "
                f"남은 {len(entries) - idx}건은 다음 호출로 미룸"
            )
            break
        payload = json.dumps(
            {
                "category": e["category"],
                "severity": e["severity"],
                "pattern": e["pattern"],
                "frequency": e["frequency"],
                "lastSeen": e["last_seen"],
            }
        )
        try:
            r = subprocess.run(
                [*command, verb_name, payload],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=_PROMOTE_CALL_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as ex:
            failures.append(str(ex))
            continue
        if r.returncode == 0:
            succeeded.append(e)
        else:
            failures.append(r.stderr.strip() or f"exit {r.returncode}")
    return succeeded, failures


def _remaining_after_promotion(current: list[dict], promoted: list[dict]) -> list[dict]:
    """원장에서 **승격에 성공한 만큼만 정확히 차감**한 결과를 돌려준다 (ATK-001).

    `promoted` 는 락을 놓기 **전** 스냅샷이다. 락 밖에서 승격이 도는 동안 다른
    프로세스가 새 항목을 쓰거나 기존 항목의 frequency 를 올렸을 수 있고, 그 증분은
    아직 승격되지 않았으므로 **남겨야 한다.** 불변식: promote 가 도는 동안 추가된
    항목은 절대 사라지지 않는다.
    """
    debit: dict[str, int] = {}
    for e in promoted:
        key = _normalize(e["category"], e["pattern"])
        debit[key] = debit.get(key, 0) + e["frequency"]
    kept: list[dict] = []
    for e in current:
        key = _normalize(e["category"], e["pattern"])
        owed = debit.get(key, 0)
        if not owed:
            kept.append(e)
            continue
        debit[key] = 0  # 차감은 한 번만 — 같은 키의 행이 둘이면 뒤엣것은 그대로 남긴다
        remaining = e["frequency"] - owed
        if remaining <= 0:
            continue  # 승격된 만큼으로 전부 상쇄됐다 → 제거
        kept.append({**e, "frequency": remaining})
    return kept


def promote(root: Path | None = None) -> dict:
    """스테이징된 ledger를 컨트롤 레지스트리로 승격하고 비운다(D-43).

    **`mode` 가 계약이고 `promoted` 는 편의값이다.** 불리언으로 분기하지 마라 —
    `promoted: True` 는 세 상태를 뭉뚱그렸었다(빈 원장 / partial / 전량 성공). 그중
    빈 원장은 **레지스트리를 아예 건드리지 않은** 상태라 "승격했다"와 성질이 다르다.

    반환 dict의 `mode`:

    - `'fallback'` — 레지스트리 없음/응답 손상. ledger 보존.
    - `'held'` — 신선도 불일치 또는 동사 미특정. ledger 보존.
    - `'noop'` — **승격할 항목이 없다**(`count: 0`). 레지스트리 미접촉, ledger 불변.
    - `'promoted'` — 전량 성공. 성공분을 원장에서 차감했다.
    - `'partial'` — 일부만 성공. 성공분만 차감하고 실패분은 재시도 대상으로 남긴다.

    `promoted` 는 `mode in {'noop', 'promoted', 'partial'}` 의 편의 표현이다 —
    "실패하지 않았다"는 뜻이지 "무언가를 승격했다"는 뜻이 아니다.
    """
    root = root or _project_root()
    pointer = discover_registry_pointer(root)
    if pointer is None:
        return {
            "promoted": False,
            "mode": "fallback",
            "reason": "레지스트리 없음 — 킷 ledger가 내구 진실(폴백)",
        }

    command: list[str] = pointer["command"]
    describe = describe_registry(command, cwd=root)
    if describe is None:
        return {
            "promoted": False,
            "mode": "fallback",
            "reason": "describe 실패/손상 — 전면 폴백, ledger 보존",
        }

    common = _git_common_dir(root)
    trust = (
        _read_trust_state(common)
        if common
        else {
            "consecutiveMismatches": 0,
            "untrusted": False,
        }
    )

    declared_head = describe.get("head")
    actual_head = _current_head(root)
    freshness = "undeclared"
    if isinstance(declared_head, str):
        if actual_head is not None and declared_head == actual_head:
            freshness = "match"
            trust["consecutiveMismatches"] = 0
            trust["untrusted"] = False
        elif actual_head is not None:
            freshness = "mismatch"
            trust["consecutiveMismatches"] = trust.get("consecutiveMismatches", 0) + 1
            if trust["consecutiveMismatches"] >= _MISMATCH_DEMOTE_THRESHOLD:
                trust["untrusted"] = True
    if common is not None:
        _write_trust_state(common, trust)

    if trust.get("untrusted"):
        return {
            "promoted": False,
            "mode": "fallback",
            "reason": (
                "레지스트리가 head 지속 불일치로 미신뢰 강등됨 — "
                "킷 ledger가 내구 진실(D-50)"
            ),
        }
    if freshness == "mismatch":
        return {
            "promoted": False,
            "mode": "held",
            "reason": (
                f"head 불일치({trust.get('consecutiveMismatches', 0)}/"
                f"{_MISMATCH_DEMOTE_THRESHOLD}) — 승격 보류, ledger 보존"
            ),
        }
    if freshness == "undeclared":
        print(
            "[feedback_ledger] warning: 레지스트리가 head를 선언하지 않음 — "
            "신선도를 확인할 수 없다(D-49)",
            file=sys.stderr,
        )

    verb_name, reason = _select_promotion_verb(pointer, describe.get("verbs", []))
    if verb_name is None:
        return {"promoted": False, "mode": "held", "reason": reason}

    path = ledger_path(root)
    # **락 안에서는 읽기(claim)만 한다.** 승격 subprocess 는 락 밖에서 돈다 — 항목 수 ×
    # _PROMOTE_CALL_TIMEOUT_SECONDS 만큼 락을 붙잡으면 _LOCK_TIMEOUT_SECONDS(5초,
    # **의도된 fail-open**) 를 넘긴 다른 프로세스의 upsert 가 **무락으로** 원장에 쓴다.
    # 그 상태에서 원장을 통째로 비우면 그 항목은 승격도 보존도 되지 않고 사라진다(ATK-001).
    # fail-open 은 "막지 않는다"이지 "지운다"가 아니다.
    with _ledger_lock(path):
        try:
            claimed = parse_ledger(path)
        except LedgerUnreadable as err:
            # 읽지 못한 원장은 승격하지 않는다 — 그리고 **비우지도 않는다.**
            return {"promoted": False, "mode": "fallback", "reason": f"원장 읽기 실패: {err}"}
    if not claimed:
        # 빈 원장은 **승격이 아니다** — 레지스트리 동사를 한 번도 부르지 않았다.
        # `mode: "promoted"` 로 뭉개면 호출자가 "레지스트리에 반영됐다"로 읽는다.
        return {"promoted": True, "mode": "noop", "count": 0}

    succeeded, failures = _call_promotion_verb(command, verb_name, claimed, root)

    if not succeeded:
        return {
            "promoted": False,
            "mode": "fallback",
            "reason": f"승격 호출 전부 실패 — ledger 보존: {failures[:3]}",
        }
    # **성공분은 partial 이든 아니든 차감한다.** 이전 구현은 `failures` 가 있으면 원장을
    # 미변경으로 두고 곧장 반환했다 — 그러면 다음 promote 가 **이미 성공한 항목을 다시
    # claim 해 승격 동사를 재호출**한다. describe 스키마가 동사를 `idempotent: false` 로
    # 선언할 수 있는 이상 재호출은 frequency 를 부풀리고, frequency 가 digest 순위를
    # 정하므로 진짜 반복 결함이 digest 밖으로 밀린다(ATK-008 이 막으려던 손해).
    # "재시도를 위해 비우지 않는다" 의 올바른 구현은 **비우지 않는 것**이 아니라
    # **실패분만 남기는 것**이고, `_remaining_after_promotion` 이 정확히 그것을 한다.
    with _ledger_lock(path):
        # 비우지 않고 **차집합을 다시 계산해** 쓴다. 승격 중 추가·증가된 것은 남는다.
        try:
            current = parse_ledger(path)
        except LedgerUnreadable as err:
            # 승격은 이미 성공했으나 차감할 대상을 읽지 못했다. **덮어쓰지 않는다** —
            # 다음 호출에서 재승격이 일어나는 편이 원장을 파괴하는 것보다 낫다.
            print(
                f"[feedback_ledger] 승격 후 원장을 읽지 못해 차감을 건너뛴다 — {err}",
                file=sys.stderr,
            )
            return {"promoted": True, "mode": "partial", "count": len(succeeded),
                    "reason": "차감 실패 — 원장 보존"}
        _write_ledger(path, _remaining_after_promotion(current, succeeded))
    if failures:
        return {
            "promoted": True,
            "mode": "partial",
            "count": len(succeeded),
            "failed": len(failures),
            "reason": "일부 실패 — 성공분만 차감하고 실패분은 재시도 대상으로 남김",
        }
    return {"promoted": True, "mode": "promoted", "count": len(succeeded)}


def _main(argv: list[str]) -> int:
    if not argv:
        print(
            "usage: feedback_ledger.py upsert <category> <severity> <pattern> "
            "| digest [K] | promote",
            file=sys.stderr,
        )
        return 2
    cmd = argv[0]
    if cmd == "upsert":
        if len(argv) < 4:
            print("usage: upsert <category> <severity> <pattern...>", file=sys.stderr)
            return 2
        result = upsert(argv[1], argv[2], " ".join(argv[3:]))
        print(result)
        return 0
    if cmd == "digest":
        k = int(argv[1]) if len(argv) > 1 and argv[1].isdigit() else DEFAULT_DIGEST_K
        print(load_digest(k))
        return 0
    if cmd == "promote":
        result = promote()
        print(json.dumps(result, ensure_ascii=False))
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(_main(sys.argv[1:]))
    except Exception as e:  # fail-open: 학습 루프 오류가 본 작업을 막으면 안 됨
        print(f"[feedback_ledger] warning: {e}", file=sys.stderr)
        sys.exit(0)
