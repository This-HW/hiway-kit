#!/usr/bin/env python3
"""
Durable Executor Checklist — 완료 상태의 단일 authority (W-013).

장기·다세션 실행에서 "무엇이 검증되어 완료인가"를 git 파일 하나에 durable하게 둔다.
네이티브 Task는 ~/.claude/tasks/<session-UUID>/ 로 세션 스코프라 세션 경계를 못 넘는다 —
이 파일(`docs/works/<stage>/<W>/checklist.json`, stage=active|idea|completed)이 그 갭을
메우는 cross-session source of truth다.

핵심 설계(적대적 리뷰 반영):
  - `pass`는 모델 주장으로 flip하지 않는다. 아이템의 `verify` 명령을 **실제 실행**해
    exit 0일 때만 passes=true로 전환한다. 단, `verify` 문자열은 plan-task가
    planning-results에서 파생하는 것이 전제다 — executor가 self-author한 trivial verify
    (`true`/`echo ok`)는 이 계층이 막지 못하므로 계획 리뷰에서 걸러야 한다(정직한 한계).
  - verify-done.sh가 `status`로 passes:false/손상 잔존을 결정론 검증한다(종이→기계 게이트).
  - 단일 authority(planning-results에서 파생) + 원자적 쓰기(flock+os.replace) → drift/레이스 차단.

gate-time staleness에 대한 정직한 입장(적대적 리뷰 F1):
  `passes`는 flip 시점의 verify 성공 기록이다. `status`(및 verify-done §8 자동 게이트)는
  이 boolean만 읽고 재실행하지 않으므로, flip 이후 회귀는 status만으로는 못 잡는다 —
  이 한계는 '해소'된 게 아니다. 재증명이 필요하면 **opt-in `verify` 명령**으로 전 항목
  verify를 재실행해 stale-true를 false로 되돌린다. 자동화하지 않는 이유: verify가
  side-effect(재배포 등)를 가질 수 있고 재귀·지연 부채가 생긴다. status=빠른 원장, verify=재증명.

스키마: [{ "id", "description", "acceptance", "verify", "passes": bool, "evidence"?: str }]

CLI (scripts/checklist.sh 래퍼로 호출):
  checklist.py init   <work_dir>            # stdin의 JSON 배열로 checklist 생성(passes=false 강제)
  checklist.py show   <work_dir>            # 사람용 목록
  checklist.py status <work_dir>            # 빠른 원장 조회: 0=전부 pass 1=미완/손상 3=부재
  checklist.py verify <work_dir>            # 전 항목 verify 재실행(opt-in 재증명): 0/1/3
  checklist.py pass   <work_dir> <id>       # 아이템 verify 실행 → exit 0이면 passes=true
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

_LOCK_TIMEOUT_SECONDS = 5
_VERIFY_TIMEOUT_SECONDS = 600
_REQUIRED_FIELDS = ("id", "description", "acceptance", "verify")


def checklist_path(work_dir: Path) -> Path:
    return Path(work_dir) / "checklist.json"


def _repo_root(work_dir: Path) -> str | None:
    """verify 실행 기준 디렉토리 = git 저장소 루트.

    work_dir 깊이가 레이아웃마다 다르므로(docs/works/<W> vs docs/works/active/<W>)
    고정 parent 깊이는 틀린다(적대적 리뷰 P1). git으로 실제 루트를 구한다.
    """
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(Path(work_dir).resolve()),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return None


@contextmanager
def _lock(path: Path):
    """원자 쓰기 직렬화 — feedback_ledger와 동일 패턴(사용자별 tmp 락, O_NOFOLLOW, NB+데드라인)."""
    try:
        uid = os.getuid()
    except AttributeError:
        uid = os.environ.get("USER", "user")
    import hashlib

    # 경로 지문(락 파일명)일 뿐 보안 용도가 아니다 → FIPS 환경에서도 동작하도록 명시.
    key = hashlib.md5(str(path.resolve()).encode(), usedforsecurity=False).hexdigest()[
        :12
    ]
    d = Path(tempfile.gettempdir()) / f"claude-{uid}"
    try:
        d.mkdir(mode=0o700, exist_ok=True)
        fd = os.open(
            str(d / f"checklist_{key}.lock"),
            os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW,
            0o600,
        )
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
                        "[checklist] lock timeout — proceeding unlocked",
                        file=sys.stderr,
                    )
                    break
                time.sleep(0.05)
        yield
    finally:
        try:
            if locked:
                fcntl.flock(fh, fcntl.LOCK_UN)
        finally:
            fh.close()


def _read(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except Exception as e:
        print(f"[checklist] parse error: {e}", file=sys.stderr)
        return []
    return data if isinstance(data, list) else []


def _write(path: Path, items: list[dict]) -> None:
    """tmp + os.replace 원자 교체(심링크는 realpath로 보존)."""
    real = Path(os.path.realpath(path))
    real.parent.mkdir(parents=True, exist_ok=True)
    tmp = real.with_name(f"{real.name}.tmp.{os.getpid()}")
    tmp.unlink(missing_ok=True)
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(items, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp, real)
    finally:
        tmp.unlink(missing_ok=True)


def cmd_init(work_dir: Path, raw: str) -> int:
    """stdin/arg의 JSON 배열로 checklist 생성. passes는 항상 false로 강제(default-FAIL 계약)."""
    try:
        incoming = json.loads(raw)
    except Exception as e:
        print(f"[checklist] init: invalid JSON — {e}", file=sys.stderr)
        return 2
    if not isinstance(incoming, list) or not incoming:
        print(
            "[checklist] init: 비어있지 않은 JSON 배열이 필요합니다.", file=sys.stderr
        )
        return 2
    items = []
    seen = set()
    for i, it in enumerate(incoming):
        if not isinstance(it, dict) or any(f not in it for f in _REQUIRED_FIELDS):
            print(
                f"[checklist] init: 항목 {i}에 필수 필드 누락 {_REQUIRED_FIELDS}",
                file=sys.stderr,
            )
            return 2
        iid = str(it["id"])
        if iid in seen:
            print(f"[checklist] init: 중복 id '{iid}'", file=sys.stderr)
            return 2
        if not str(it["verify"]).strip():
            # 빈 verify는 cmd_pass가 거부 → 영구 미완이 되므로 init에서 차단.
            print(
                f"[checklist] init: 항목 {i}('{iid}') verify가 비어있음 "
                "(검증 명령 필수)",
                file=sys.stderr,
            )
            return 2
        seen.add(iid)
        items.append(
            {
                "id": iid,
                "description": str(it["description"]),
                "acceptance": str(it["acceptance"]),
                "verify": str(it["verify"]),
                "passes": False,
            }
        )
    path = checklist_path(work_dir)
    with _lock(path):
        _write(path, items)
    print(f"[checklist] {len(items)}개 항목 생성: {path}")
    return 0


def cmd_show(work_dir: Path) -> int:
    items = _read(checklist_path(work_dir))
    if not items:
        print("(checklist 없음 또는 비어있음)")
        return 3
    done = sum(1 for it in items if it.get("passes"))
    print(f"Checklist: {done}/{len(items)} passed")
    for it in items:
        mark = "✅" if it.get("passes") else "⬜"
        print(f"  {mark} [{it['id']}] {it['description']}")
        if not it.get("passes"):
            print(f"       verify: {it['verify']}")
    return 0


def cmd_status(work_dir: Path) -> int:
    """exit 0=전부 pass, 1=미완/손상, 3=checklist 진짜 부재(스킵).

    적대적 리뷰(false-green): _read는 파싱 실패/부재를 모두 []로 뭉갠다. 그러면
    `echo '[]' > checklist.json` 이나 손상 파일이 3(skip)이 되어 완료 게이트가 조용히
    통과한다. 파일이 '존재하면' 반드시 비어있지 않은 리스트여야 하며, 아니면 FAIL(1).
    진짜로 파일이 없을 때만 3(스킵)이다.
    """
    path = checklist_path(work_dir)
    if not path.exists():
        return 3
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[checklist] status: 파싱 실패 → FAIL(손상): {e}", file=sys.stderr)
        return 1
    if not isinstance(items, list) or not items:
        # 존재하는데 빈 리스트/비-리스트 = 변조·손상 (init은 빈 배열을 쓰지 않음) → FAIL.
        print(
            "[checklist] status: 파일이 존재하나 비어있음/비-리스트 → FAIL",
            file=sys.stderr,
        )
        return 1
    pending = [str(it.get("id", "?")) for it in items if not it.get("passes")]
    if pending:
        print(
            f"[checklist] 미완 {len(pending)}개: {', '.join(pending)}", file=sys.stderr
        )
        return 1
    return 0


def _run_verify(verify: str, work_dir: Path) -> tuple[int, str]:
    """verify 명령 실행 → (exit_code, 출력 tail). 타임아웃 시 프로세스 '그룹'을
    killpg로 종료해 shell(shell=True)이 fork한 자손을 정리한다(적대적 리뷰 F6).
    best-effort임에 유의: verify의 자손이 스스로 setsid/이중fork(데몬화)하면 그룹을
    벗어나 killpg가 못 미친다 — 그 경우까지 보장하지는 않는다.
    `start_new_session=True`가 자식을 새 그룹 리더로 만들므로 killpg 대상은 항상
    자식 그룹이며, checklist.py 자신을 죽이지 않는다(이 플래그 제거 금지).
    lock을 잡지 않은 채 호출되어야 한다(장시간 락 점유 방지)."""
    try:
        proc = subprocess.Popen(  # noqa: S602
            # shell=True는 이 기능의 본질 — verify는 사용자가 Work 체크리스트에 적은
            # 셸 명령(`pytest && ruff check` 등)이며, 셸 해석이 계약이다.
            verify,
            shell=True,
            cwd=_repo_root(work_dir),  # None이면 현재 cwd 상속(폴백)
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,  # 새 프로세스 그룹 → killpg로 자손까지 정리
        )
    except Exception as e:
        return 1, f"실행 실패: {e}"
    try:
        out, _ = proc.communicate(timeout=_VERIFY_TIMEOUT_SECONDS)
        return proc.returncode, (out or "")[-1500:]
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            proc.kill()
        # 좀비 회수 실패는 무시 — 이미 killpg 했고 반환값은 타임아웃으로 확정이다.
        with contextlib.suppress(Exception):
            proc.communicate(timeout=5)
        return 124, f"타임아웃 {_VERIFY_TIMEOUT_SECONDS}s 초과 → 프로세스 그룹 종료"


def cmd_pass(work_dir: Path, item_id: str) -> int:
    """아이템의 verify 명령을 실행해 exit 0일 때만 passes=true로 전환(기계 게이트).

    모델이 자기 작업을 completed로 찍는 self-mark를 원천 차단한다 — 통과 여부는
    verify 명령의 raw exit-code가 결정한다(리서치 "No PASS without proof").
    verify는 lock 밖에서 실행하고(F6: 600s 동안 락 점유 방지), flip만 lock 안에서
    재읽기→수정→쓰기 한다(verify 중 다른 프로세스 변경 반영).
    """
    path = checklist_path(work_dir)
    items = _read(path)
    target = next((it for it in items if str(it["id"]) == str(item_id)), None)
    if target is None:
        print(f"[checklist] id '{item_id}' 없음", file=sys.stderr)
        return 2
    verify = str(target.get("verify", "")).strip()
    if not verify:
        print(
            f"[checklist] '{item_id}'에 verify 명령이 없어 pass 거부", file=sys.stderr
        )
        return 2
    rc, tail = _run_verify(verify, work_dir)  # 락 밖 실행
    if rc != 0:
        print(
            f"[checklist] verify 실패(exit {rc}) → pass 거부:\n{tail}", file=sys.stderr
        )
        return 1
    with _lock(path):
        items = _read(path)
        target = next((it for it in items if str(it.get("id")) == str(item_id)), None)
        if target is None:
            print(f"[checklist] id '{item_id}' 없음(동시 삭제)", file=sys.stderr)
            return 2
        # TOCTOU: verify를 락 밖에서 돌리는 동안 다른 프로세스가 이 항목의 verify를
        # 바꿨다면, 방금 통과시킨 건 '옛 명령'이다 → stale verify로 flip 금지(적대적 리뷰 F2).
        if str(target.get("verify", "")).strip() != verify:
            print(
                f"[checklist] '{item_id}'의 verify가 실행 중 변경됨 → flip 거부(재실행 필요)",
                file=sys.stderr,
            )
            return 1
        target["passes"] = True
        target["evidence"] = f"verify exit 0: {verify}"
        _write(path, items)
    print(f"[checklist] '{item_id}' passed (verify exit 0)")
    return 0


def cmd_verify(work_dir: Path) -> int:
    """모든 항목의 verify를 지금 재실행해 passes를 현재 상태로 재판정(opt-in 재증명).

    flip 후 회귀한 stale-true 항목을 false로 되돌린다. exit 0=전부 현재도 통과,
    1=미완/실패, 3=checklist 부재. verify가 side-effect를 가질 수 있어(재배포 등)
    verify-done 기본 경로가 아니라 명시적 opt-in 명령이다 — 자동 게이트(§8)는 status를
    쓴다(F1은 '해소'가 아니라, 재증명이 필요할 때 이 명령으로 하도록 제공).
    """
    path = checklist_path(work_dir)
    if not path.exists():
        return 3
    items = _read(path)
    if not items:
        print("[checklist] verify: 비어있음/부재", file=sys.stderr)
        return 3
    # verify 결과를 id별로 모아두고(락 밖 실행), 기록은 락 안에서 최신 파일에 병합한다 —
    # 전체 스냅샷을 그대로 덮어쓰면 실행 중 들어온 동시 pass/신규 항목을 잃는다(적대적 리뷰 F3).
    results: dict[str, tuple[bool, int, str]] = {}
    failed: list[str] = []
    for it in items:
        verify = str(it.get("verify", "")).strip()
        iid = str(it.get("id", "?"))
        if not verify:
            failed.append(iid)
            continue
        rc, _ = _run_verify(verify, work_dir)  # 락 밖 실행
        now_pass = rc == 0
        results[iid] = (now_pass, rc, verify)
        if not now_pass:
            failed.append(iid)
    if results:
        with _lock(path):
            cur = _read(path)  # 최신 재읽기 → id로 병합(전체 덮어쓰기 금지)
            changed = False
            for it in cur:
                r = results.get(str(it.get("id")))
                if r is None:
                    continue
                now_pass, rc, verify = r
                if it.get("passes") != now_pass:
                    it["passes"] = now_pass
                    it["evidence"] = f"reverify exit {rc}: {verify}"
                    changed = True
            if changed:
                _write(path, cur)
    if failed:
        print(f"[checklist] reverify 실패/미완: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd, work_dir = argv[0], Path(argv[1])
    if cmd == "init":
        raw = argv[2] if len(argv) > 2 else sys.stdin.read()
        return cmd_init(work_dir, raw)
    if cmd == "show":
        return cmd_show(work_dir)
    if cmd == "status":
        return cmd_status(work_dir)
    if cmd == "verify":
        return cmd_verify(work_dir)
    if cmd == "pass":
        if len(argv) < 3:
            print("usage: checklist.py pass <work_dir> <id>", file=sys.stderr)
            return 2
        return cmd_pass(work_dir, argv[2])
    print(f"[checklist] unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as e:
        print(f"[checklist] error: {e}", file=sys.stderr)
        sys.exit(2)
