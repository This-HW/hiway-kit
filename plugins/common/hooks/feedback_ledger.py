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

ledger 경로: <git-common-dir>/kit/ledger.md — **모든 워크트리가 공유**한다.
  구 위치(<project_root>/docs/works/feedback/ledger.md)는 작업 트리 안이라
  워크트리마다 갈라졌다. 남아 있으면 첫 실행이 **병합 이관**하고 .migrated 로 개명한다.
  이 이관 경로는 4.x → 5.x 업그레이드용이다 — **6.0.0 에서 제거한다**(2026-09-28 결정).
ledger 부재/파싱 실패 시 전 구간 무동작 (fail-open, opt-in).

## 레지스트리 승격 경로는 없다 (v5.0.0 삭제)

2026-08 에 넣은 `promote` 하위명령(컨트롤 레지스트리로 스테이징→승격)은 호출자가
0 이었다 — 킷 안의 어떤 스킬·훅·스크립트도 부르지 않았다. v5.0.0 에서 레지스트리
발견·describe 협상·신뢰 강등 기계와 함께 삭제했다. 이 원장이 유일한 내구 진실이다.
"""

from __future__ import annotations

import fcntl
import hashlib
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

_LOCK_TIMEOUT_SECONDS = 5  # 락 획득 데드라인 — 초과 시 무락 진행(fail-open)

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

    4.x → 5.x 업그레이드 경로다 — **6.0.0 에서 제거한다**(2026-09-28 결정).

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
    *"fail-open 은 '막지 않는다'이지 '지운다'가 아니다"* 라고 적어 놓고(v5.0.0 에서 삭제한 promote 주석)
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
            # (v5.0.0 에서 삭제한 `promote()` 의 전체 비우기 · `parse_ledger` 부재/실패 뭉갬)과 같은 계열이다.
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


def _main(argv: list[str]) -> int:
    if not argv:
        print(
            "usage: feedback_ledger.py upsert <category> <severity> <pattern> "
            "| digest [K]",
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
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(_main(sys.argv[1:]))
    except Exception as e:  # fail-open: 학습 루프 오류가 본 작업을 막으면 안 됨
        print(f"[feedback_ledger] warning: {e}", file=sys.stderr)
        sys.exit(0)
