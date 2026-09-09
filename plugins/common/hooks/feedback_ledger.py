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

이 파일이 채우는 설계 공백 하나를 명시한다: D-42/D-44의 describe 스키마
(`name`·`args`·`effect`·`idempotent`)에는 "이 동사가 승격/등록용이다"를 나타내는
필드가 없다. `promotionVerb`를 포인터 파일(컨트롤 소유·비-repo 파일)에 두는 것은
그 필드가 킷 소스에 박히는 것이 아니라 **컨트롤이 자기 레지스트리를 소개할 때
스스로 선언하는 값**이라 D-42의 "동사 이름을 하드코딩하지 않는다"를 어기지 않는다
— 다만 이 구체적 필드명 자체는 설계 문서에 명문화돼 있지 않은 이 구현의 해석이다.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
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
        merged = _merge_entries(parse_ledger(target), incoming)
        kept = _decay(merged)
        _write_ledger(target, kept)
        backup = legacy.with_suffix(".md.migrated")
        legacy.rename(backup)
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


def parse_ledger(path: Path) -> list[dict]:
    """ledger.md 테이블을 파싱. 부재/실패 시 빈 리스트 (fail-open)."""
    entries: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return entries
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
    d = Path(tempfile.gettempdir()) / f"claude-{uid}"
    try:
        d.mkdir(mode=0o700, exist_ok=True)
        return d / f"ledger_{key}.lock"
    except Exception:
        return path.with_name(path.name + ".lock")  # 폴백: 기존 위치


def _write_ledger(path: Path, entries: list[dict]) -> None:
    """tmp 파일 작성 후 os.replace로 원자 교체 — 부분 쓰기 상태 노출 방지.

    대상이 심링크면 링크 자체가 아니라 **링크가 가리키는 실제 파일**을 교체한다 —
    사용자가 ledger.md를 공유 원장으로 심링크해 둔 경우를 보존한다(F7). ledger.md는
    저장소 내부의 사용자 통제 파일이라 /tmp와 달리 심링크 추적이 안전하다.
    """
    real = Path(os.path.realpath(path))
    real.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        f"| {e['id']} | {e['category']} | {e['pattern']} | "
        f"{e['frequency']} | {e['last_seen']} | {e['severity']} |"
        for e in entries
    ]
    tmp = real.with_name(f"{real.name}.tmp.{os.getpid()}")
    tmp.unlink(missing_ok=True)
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(_HEADER + "\n".join(rows) + ("\n" if rows else ""))
        os.replace(tmp, real)
    finally:
        tmp.unlink(missing_ok=True)


def upsert(category: str, severity: str, pattern: str, root: Path | None = None) -> str:
    """결함 패턴을 추가하거나 기존 freq를 증가. 반환: 'added' | 'incremented'.

    parse→수정→write 전체가 _ledger_lock 안에서 실행된다 — 병렬 upsert에서도
    양쪽 기록이 모두 보존되고 F-id가 중복 채번되지 않는다.
    """
    if category not in VALID_CATEGORIES:
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
        entries = parse_ledger(path)
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
    """
    with contextlib.suppress(Exception):
        migrate_legacy_ledger(root)


def load_digest(top_k: int = DEFAULT_DIGEST_K, root: Path | None = None) -> str:
    """주입용 digest 문자열. ledger 부재/빈 경우 빈 문자열 (fail-open)."""
    _try_migrate(root)
    entries = parse_ledger(ledger_path(root))
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


def discover_registry_pointer(root: Path | None = None) -> dict | None:
    """컨트롤 레지스트리 포인터를 읽는다. 없거나 부적합하면 None(fail-open, 폴백).

    `url` 필드가 있으면 무조건 거절한다(D-48) — 이 킷은 exec 전용 계약이다.
    """
    root = root or _project_root()
    common = _git_common_dir(root)
    if common is None:
        return None
    pointer_path = common.joinpath(*_REGISTRY_POINTER_REL)
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


def promote(root: Path | None = None) -> dict:
    """스테이징된 ledger를 컨트롤 레지스트리로 승격하고 비운다(D-43).

    반환 dict의 `mode`: 'fallback'(레지스트리 없음/응답 손상 — ledger 보존),
    'held'(신선도 불일치 또는 동사 미특정 — ledger 보존), 'promoted'(성공 — 비움),
    'partial'(일부만 성공 — ledger 보존, 재시도를 위해 비우지 않음).
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
    with _ledger_lock(path):
        entries = parse_ledger(path)
        if not entries:
            return {"promoted": True, "mode": "promoted", "count": 0}

        failures: list[str] = []
        promoted_count = 0
        for e in entries:
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
                promoted_count += 1
            else:
                failures.append(r.stderr.strip() or f"exit {r.returncode}")

        if promoted_count == 0:
            return {
                "promoted": False,
                "mode": "fallback",
                "reason": f"승격 호출 전부 실패 — ledger 보존: {failures[:3]}",
            }
        if failures:
            return {
                "promoted": True,
                "mode": "partial",
                "count": promoted_count,
                "failed": len(failures),
                "reason": "일부 실패 — 재시도를 위해 ledger를 비우지 않음",
            }
        _write_ledger(path, [])
        return {"promoted": True, "mode": "promoted", "count": promoted_count}


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
