#!/usr/bin/env python3
"""build-targets.py — 다중 하네스 타겟 매니페스트 생성기 (W-019 / S1-S3).

왜 필요한가
-----------
Codex·Antigravity는 각자 매니페스트 규격(`.codex-plugin/plugin.json`, `plugins/common/
plugin.json`)을 갖는다. 이 값(name·version·description 등)을 손으로 세 곳에 유지하면
`plugins/common/.claude-plugin/plugin.json`(기존 Claude Code SSOT)과 반드시 드리프트한다
— 이 레포가 doc-count·CHECKSUMS·MIRROR·AGENTS.md 게이트를 만든 것과 같은 실패 유형이다
(스펙 §5.2, HANDOFF).

이 스크립트는 SSOT(`plugins/common/.claude-plugin/plugin.json`)와 정책
(`packaging/targets.json`)만으로 타겟 매니페스트를 **재현 가능하게** 계산한다. 필드
매핑·문구는 전부 `packaging/targets.json`에서 읽는다 — 이 파일에 타겟별 값을
하드코딩하지 않는다.

설계 원칙 (export_harness.py와 같은 철학, W-017 선례 참고 — 복제하지 않고 참고함)
--------------------------------------------------------------------------------
1. **결정론적.** 같은 입력(SSOT + targets.json + 컴포넌트 디렉토리 실측)은 항상 같은
   바이트를 만든다 (키 정렬 + 고정 인코딩) — `--check`가 diff 대신 바이트 비교로
   드리프트를 잡을 수 있으려면 이게 전제다.
2. **`enabled`는 "지금 생성 대상" 하나만 의미한다.** S1에서는 `enabled`가 "로드맵에
   있다"와 "지금 만든다"를 겸하게 두었다가, `--write`가 매니페스트를 실제로 쓰면
   그 순간부터 `--check`가 "미생성=drift"로 막혀야 하는데 코드가 그걸 절차 제약(사람이
   "이번엔 쓰지 마라"를 지키는 것)으로만 표현하고 있었다 — S2에서 정책이 고쳐졌다
   (targets.json v1.1.0, `gate.requireGeneratedManifestPresent`). 이제 `enabled:true`는
   "이 실행에서 만들어야 하고, 없으면 드리프트"를 뜻한다. 아직 만들 준비가 안 된 타겟은
   정책에서 `enabled:false`로 두고 준비되면 승격한다(`_enabledPromotion` 참고) — 코드가
   아니라 정책 파일이 단계를 표현한다.
3. **`--check`는 항상 안전(읽기 전용)하지만, `enabled`인데 미생성이면 드리프트다.**
   "매니페스트가 없다"를 "아직 이 단계가 아님"으로 관대히 봐주면, 생성물을 실수로(또는
   악의로) 지워도 게이트가 green이 된다 — 이 레포가 게이트를 만드는 이유 자체를
   무효화하는 침묵 구멍이다(W-018과 같은 실패 유형, 2026-08-26 판정). "존재하지 않는
   파일"은 이제 "드리프트"와 동의어다. 아직 만들 준비가 안 된 타겟은 `enabled:false`로
   두어라 — 그러면 애초에 검사 대상에서 빠진다(원칙 2).
4. **SSOT 부재는 명확한 실패다.** 컴포넌트 디렉토리 부재("skills 없음")는 정상적인
   조건 분기이지만, SSOT 매니페스트 자체가 없으면 계산할 것이 없으므로 즉시, 명확한
   메시지로 실패한다(raw traceback 금지) — 이 도구가 잘못 배치됐다는 신호다.
5. **stdlib only, Python 3.9 floor.** 이 스크립트는 repo-local이라 소비자 환경에서
   돌 필요는 없지만, 이 레포의 게이트(verify-done.sh §4 python39-compat 관례)와 CI가
   3.9로 로드 가능성을 검사한다 — 그 관례를 따른다.
6. **경로는 레포 루트 밖으로 못 나간다 — `--check`·`--write` 둘 다.** `manifestPath`·
   `marketplace.path`는 `packaging/targets.json`(정책 파일)에서 온 문자열이다.
   `repo_root / rel_path`는 `rel_path`가 절대경로면 `repo_root`를 통째로 버리는
   pathlib의 함정이 있고, `..`나 심링크로도 트리 밖으로 나갈 수 있다 — 셋 다 실제로
   재현됐다(2026-08-27 적대적 리뷰). `_resolve_in_repo()`가 **한 번만** resolve해서
   그 결과를 검증·기록 양쪽에 그대로 쓴다(`tools/export_harness.py`의 `_resolve_in_repo`
   교훈 — 검사와 쓰기가 각자 resolve하면 그 사이가 TOCTOU 창이 된다). 봉쇄를
   `--write`에만 걸면 `--check`가 구멍으로 남는다(2.14.1에서 실제로 났던 실수) — 그래서
   둘 다에 같은 헬퍼를 쓴다.

사용:
  python3 scripts/build-targets.py --check              # 전체 enabled 타겟 드리프트 검사
  python3 scripts/build-targets.py --check --only codex # 하나만
  python3 scripts/build-targets.py --write               # 전체 enabled 타겟 기록
  python3 scripts/build-targets.py --write --only codex # 하나만 기록

스킬별 Codex 메타데이터 (5.4.0)
-------------------------------
타겟 정책에 `skillInterface` 가 있으면 각 스킬(`skills/<name>/SKILL.md`)의 frontmatter 에서
`skills/<name>/<path>`(Codex: `agents/openai.yaml`)를 **파생**한다. 매니페스트와 같은
생성물이므로 `--check` 의 드리프트·미생성 판정을 그대로 받는다. frontmatter 는 한 줄
`key: value` 만 읽는다 — 블록 스칼라(`|`·`>`)나 읽을 수 없는 형태는 추측하지 않고 exit 1.

edition 배포 타겟 (Hermes 판, 2026-11-24)
-----------------------------------------
`delivery: "edition"` 타겟은 **main 트리에 파일을 만들지 않는다** — 생성 브랜치의 축소판으로
배포되고, 판 트리는 판 빌더(정책의 `editionBuilder`)가 만든다. 이 스크립트는 그 타겟의
매니페스트를 `build_manifest()` 로 **계산만** 해 Agent Plugins v1 정적 제약을 판정한다
(`ap_v1_violations`). `enabled`·`--only` 와 무관하게 `--check`·`--write` 마다 돈다 — 정책 파손을 판 빌더가
생기기 전에, 병합 전에 잡기 위해서다. `--only <edition>` 은 판 빌더로 안내하는 오류다(검사한
척 성공하지 않는다). 판정 근거: docs/specs/2026-11-24-hermes-edition/design-verdict.md D1·D3.

`--check` 는 fail-closed 불변식의 정적 대리 검사도 한다: `<pluginRoot>/plugin.json` 의
`$schema` 가 AP v1 URL 이 아니고 `<pluginRoot>/plugin.yaml`(`.yml`)이 없어야 한다. main 트리를
ref 없이 설치한 Hermes 사용자가 `manifest_invalid` 로 막히게 하는 장치다(판정 D1).

출력 경로 충돌
--------------
main 에 생성하는 활성 타겟들의 출력 경로가 겹치면(같은 파일, 또는 한쪽이 다른 쪽의 상위
디렉토리 — 같은 타겟 안의 생성물끼리도) `--check`·`--write` 모두 **아무것도 쓰기 전에** exit 1
이다. 생성물이 생성기의 **읽기 입력**(SSOT `source.manifest`, 정책 파일, 훅 스크립트, 스킬
`SKILL.md`)과 겹쳐도 같다. 비교는 `_resolve_in_repo` 가 정규화한 경로로 한다 — `./`·`..`·심링크
별칭이 서로 다른 문자열로 같은 파일을 가리킬 수 있다. 이미 있는 파일은 `os.path.samefile`
(하드링크)로도 보고, darwin 에서는 대소문자를 접어 비교한다(기본 파일시스템이 대소문자 무시).
`--only` 로 좁혀도 비교는 활성 타겟 전체로 한다(좁힌 타겟의 쓰기가 다른 타겟의 생성물을 덮을
수 있다). 그 계산이 다른 타겟 때문에 실패하면 실패 타겟 이름을 함께 알린다.

fail-closed 불변식·edition 판정도 `--only` 와 무관하게 돈다. 불변식은 디스크(`--check`)와
**계산된 생성물**(`--check`·`--write`) 양쪽으로 본다 — `--write` 가 위반을 직접 만들지 않도록.

정책 구조 검증: 모든 `targets[].id` 는 비어 있지 않은 유일한 문자열이어야 한다(대상 선택 전).

exit code:
  0 = 성공 (또는 --check 드리프트 없음)
  1 = --check 드리프트(미생성 포함) / SSOT 부재 / 알 수 없는 --only id / 정책 파싱 실패 /
      스킬 frontmatter 를 읽지 못함 / edition AP v1 판정 실패 / fail-closed 불변식 위반 /
      출력 경로 충돌(생성물·읽기 입력) / `manifestPath`·중첩 필수 키 없음 / 타겟 id 누락·중복 /
      `--only <edition 타겟>`
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_POLICY = REPO_ROOT / "packaging" / "targets.json"

#: 훅 인자는 정책 파일에서 와서 **셸 명령 문자열에 그대로 이어 붙는다**. 경로 봉쇄와
#: 같은 계열의 규율이다(`docs/conventions/path-containment.md`) — 설정값을 검증 없이
#: 명령으로 조립하지 않는다. 인용·치환·구분자를 깰 수 있는 문자를 원천 배제한다.
_HOOK_ARG_RE = re.compile(r"--[A-Za-z0-9][A-Za-z0-9._-]*(=[A-Za-z0-9._-]+)?")
_HOOK_INTERPRETER_RE = re.compile(r"[A-Za-z0-9_./ -]+")

#: Agent Plugins v1 정적 제약 — Hermes 가 포터블 `plugin.json` 을 받는 조건.
#: 출처(원문 발췌·sha·줄 번호): `scripts/tests/fixtures/hermes_agent_plugins_352b249.txt`
#: (NousResearch/hermes-agent `hermes_cli/agent_plugins.py` @352b249f, 46-57·212-217·230-261행).
#: 상수가 그 발췌와 같다는 것을 `test_ap_v1_constants_match_upstream_excerpt` 가 지킨다.
#: 정책(`packaging/targets.json`)에서 읽지 않는다 — **정책과 독립된 오라클**이어야 정책이 망가질
#: 때 판정이 같이 망가지지 않는다. 정책의 `_apV1Source` 가 이 위치를 가리킨다.
#:
#: 원문보다 엄격한 곳(의도): 원문은 허용 밖 최상위 필드와 객체가 아닌 `extensions` 를 진단만 남기고
#: **버린 뒤 설치를 진행**한다. 여기서는 실패로 본다 — 생성한 값이 조용히 버려지는 배포를 내지 않는다.
AP_V1_SCHEMA_URL = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
AP_V1_TOP_LEVEL = frozenset(
    {
        "$schema",
        "name",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "extensions",
    }
)
AP_V1_NAME_RE = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
AP_V1_NAME_MIN = 1
AP_V1_NAME_MAX = 64
AP_V1_AUTHOR_FIELDS = frozenset({"name", "email", "url"})
#: 있으면 문자열이어야 하는 필드(원문 `_validate_manifest` 의 타입 검사).
AP_V1_STRING_FIELDS = ("version", "description", "homepage", "repository", "license")
#: Hermes 가 플러그인 디렉토리에서 네이티브 매니페스트로 읽는 이름. 있으면 `plugin.json` 을 보지
#: 않는다 — 원문 발췌 `scripts/tests/fixtures/hermes_plugins_discovery_352b249.txt`
#: (`hermes_cli/plugins_discovery.py` @352b249f, 165-177행).
HERMES_NATIVE_MANIFESTS = ("plugin.yaml", "plugin.yml")
#: AP v1 매니페스트는 패키지 루트에 고정이다.
AP_V1_MANIFEST_NAME = "plugin.json"

#: `delivery` 의 허용 값. 키가 없으면 main 생성(기존 동작)이다.
DELIVERY_EDITION = "edition"
#: edition 타겟에 있으면 main 생성물을 뜻하게 되는 키 — 조용히 무시하지 않고 거부한다.
_EDITION_FORBIDDEN_KEYS = ("manifestPath", "marketplace", "skillInterface", "hooks")


class PolicyError(Exception):
    """정책·SSOT 파싱 실패 — main이 exit 1과 명확한 메시지로 변환한다."""


def load_policy(path: Path) -> dict:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as err:
        raise PolicyError(f"정책 파일을 읽지 못했다: {path} ({err})") from err
    try:
        return json.loads(raw)
    except json.JSONDecodeError as err:
        raise PolicyError(f"정책 파일 JSON 파싱 실패: {path} ({err})") from err


def load_ssot(repo_root: Path, policy: dict) -> dict:
    """`packaging/targets.json`의 `source.manifest`가 가리키는 SSOT 매니페스트.

    부재는 조용히 넘기지 않는다 — 계산할 입력 자체가 없다는 뜻이므로 즉시,
    raw traceback 없이 명확한 메시지로 실패한다.
    """
    p = _source_path(repo_root, policy, "manifest")
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as err:
        raise PolicyError(
            f"SSOT 매니페스트를 읽지 못했다: {p}\n"
            f"  (packaging/targets.json의 source.manifest가 가리키는 파일이다) — {err}"
        ) from err
    try:
        return json.loads(raw)
    except json.JSONDecodeError as err:
        raise PolicyError(f"SSOT 매니페스트 JSON 파싱 실패: {p} ({err})") from err


def _detect_components(plugin_root: Path, policy: dict) -> set[str]:
    """`source.pluginRoot` 아래 실재하는 컴포넌트 디렉토리 이름 집합.

    목록을 손으로 유지하지 않는다 — 존재 여부를 실측한다(정책 파일의 `_meta.detection`).
    """
    meta = _require(policy.get("source"), "_meta", "source")
    candidates = _require(meta, "componentDirs", "source._meta")
    return {
        name
        for name in candidates
        if _policy_path(plugin_root, name, "source.componentDirs").is_dir()
    }


def _find_target(policy: dict, target_id: str) -> dict | None:
    for t in policy.get("targets", []):
        if t.get("id") == target_id:
            return t
    return None


def _require(container: object, key: str, where: str) -> object:
    """정책의 중첩 키를 꺼낸다. 없으면 KeyError traceback 대신 PolicyError(exit 1)."""
    if not isinstance(container, dict) or key not in container:
        raise PolicyError(f"{where}: 필수 키 '{key}' 가 없다 (packaging/targets.json)")
    return container[key]


def validate_targets(policy: dict) -> list[dict]:
    """대상 선택 **전에** 정책의 타겟 목록 구조를 검증한다.

    `id` 는 비어 있지 않은 유일한 문자열이어야 한다. 중복을 받아 주면 id 로 찾는 모든 자리
    (`--only`·생성물 묶음)에서 한쪽이 다른 쪽을 가려, 가려진 타겟의 생성물이 기록·검사·충돌
    비교에서 조용히 사라진다(false green — 적대적 리뷰 ATK-001).
    """
    targets = policy.get("targets", [])
    if not isinstance(targets, list):
        raise PolicyError("targets: 타겟 객체의 목록이 필요하다")
    seen: dict[str, int] = {}
    for i, target in enumerate(targets):
        if not isinstance(target, dict):
            raise PolicyError(
                f"targets[{i}]: 타겟 객체가 필요하다 — {type(target).__name__}"
            )
        tid = target.get("id")
        if not isinstance(tid, str) or not tid.strip():
            raise PolicyError(
                f"targets[{i}]: id 는 비어 있지 않은 문자열이어야 한다 — {tid!r}"
            )
        if tid in seen:
            raise PolicyError(
                f"targets[{i}]: id '{tid}' 중복 — targets[{seen[tid]}] 와 같다. 한쪽 생성물이 "
                f"기록·검사에서 사라진다"
            )
        seen[tid] = i
        if is_edition(target):
            _edition_builder(target)
    return targets


def build_manifest(ssot: dict, target: dict, present_dirs: set[str]) -> dict:
    """타겟 하나의 플러그인 매니페스트 내용을 계산한다. 필드 매핑은 전부 target(정책)이 정한다.

    필드 하드코딩 없음: SSOT에서 뽑을 필드 이름(`requiredFields`/`optionalFields`/
    `passthroughFields`), 컴포넌트 필드 매핑(`componentFields`), 인터페이스 문구(`interface`)와
    SSOT 에서 옮겨 담을 인터페이스 필드(`interfaceFrom`), 스키마 URL(`schemaUrl`)은 전부
    `packaging/targets.json`에서 온다.

    `optionalFields`와 `passthroughFields`는 동작이 같다(SSOT에 있으면 싣고, 없으면 조용히
    생략) — 이름을 분리한 것은 정책 문서의 의도를 구분해 남기기 위해서다:
    `optionalFields`는 이 타겟의 스키마가 원래 아는 필드(`$schema` 등), `passthroughFields`는
    "SSOT에 있는데 이 타겟 매니페스트가 놓치면 안 되는" 값(author·license 등, S2 관찰 승인 —
    저작자·라이선스 없는 패키지가 공개 디렉토리에 올라가는 사고를 막는다) — 정책을 읽는
    사람에게 "왜 이 필드가 있는가"를 남긴다. 코드 경로는 하나로 합쳐 로직 이중화를 피한다.
    """
    out: dict = {}
    if target.get("schemaUrl"):
        out["$schema"] = target["schemaUrl"]
    for field in target.get("requiredFields", []):
        if field not in ssot:
            raise PolicyError(
                f"타겟 '{target['id']}': SSOT 매니페스트에 필수 필드 '{field}' 없음"
            )
        out[field] = ssot[field]
    for field in [
        *target.get("optionalFields", []),
        *target.get("passthroughFields", []),
    ]:
        if field in ssot:
            out[field] = ssot[field]
    for field, rel in target.get("componentFields", {}).items():
        if field in present_dirs:
            out[field] = rel
    hooks = target.get("hooks")
    if hooks and "hooks" in present_dirs:
        out["hooks"] = _require(hooks, "manifestField", f"타겟 '{target['id']}' hooks")
    if target.get("interface") or target.get("interfaceFrom"):
        interface = dict(target.get("interface", {}))
        # 같은 값을 정책에 리터럴로 두면 SSOT 와 두 벌이 된다 — SSOT 에서 옮겨 담는다.
        # 원천이 없으면 빈 URL 을 조용히 싣지 않고 실패한다.
        for field, src in target.get("interfaceFrom", {}).items():
            if src not in ssot:
                raise PolicyError(
                    f"타겟 '{target['id']}': interface.{field} 의 원천 SSOT 필드 '{src}' 없음"
                )
            interface[field] = ssot[src]
        out["interface"] = interface
    return out


def ap_v1_violations(manifest: dict) -> list[str]:
    """계산된 매니페스트가 Agent Plugins v1 정적 제약을 어기는 이유 목록(빈 목록 = 통과).

    판정 항목(원문 `_validate_manifest` 순서): 허용 최상위 필드만, `$schema` 정확 일치,
    `name` 정규식 + 1~64자, 문자열 필드 5종의 타입, `keywords` 는 문자열 배열, `author` 는
    `{name,email,url}` 문자열만 담은 객체, `extensions` 는 객체이고 그 값도 객체.
    스킬 frontmatter·심링크 같은 판 트리 판정은 판 빌더의 몫이다(이 스크립트는 매니페스트만 계산한다).
    """
    out: list[str] = []
    schema = manifest.get("$schema")
    if schema != AP_V1_SCHEMA_URL:
        out.append(
            f"$schema 가 AP v1 URL 과 다르다 — {schema!r} (기대: {AP_V1_SCHEMA_URL})"
        )
    extra = sorted(set(manifest) - AP_V1_TOP_LEVEL)
    if extra:
        out.append(f"AP v1 이 허용하지 않는 최상위 필드 — {extra}")
    name = manifest.get("name")
    if (
        not isinstance(name, str)
        or not AP_V1_NAME_MIN <= len(name) <= AP_V1_NAME_MAX
        or not AP_V1_NAME_RE.fullmatch(name)
    ):
        out.append(
            f"name 이 AP v1 규칙(소문자·숫자·.·-, 1~{AP_V1_NAME_MAX}자, "
            f"--·.. 금지, 영숫자로 시작·끝)을 어긴다 — {name!r}"
        )
    for field in AP_V1_STRING_FIELDS:
        if field in manifest and not isinstance(manifest[field], str):
            out.append(
                f"{field} 는 문자열이어야 한다 — {type(manifest[field]).__name__}"
            )
    if "keywords" in manifest:
        keywords = manifest["keywords"]
        if not isinstance(keywords, list) or not all(
            isinstance(k, str) for k in keywords
        ):
            out.append("keywords 는 문자열 배열이어야 한다")
    if "extensions" in manifest:
        extensions = manifest["extensions"]
        if not isinstance(extensions, dict):
            out.append("extensions 는 객체여야 한다(원문은 버리고 진행한다)")
        elif any(not isinstance(v, dict) for v in extensions.values()):
            out.append("extensions 의 네임스페이스 값은 객체여야 한다")
    if "author" in manifest:
        author = manifest["author"]
        if not isinstance(author, dict):
            out.append(f"author 는 객체여야 한다 — {type(author).__name__}")
        else:
            bad = sorted(
                k
                for k, v in author.items()
                if k not in AP_V1_AUTHOR_FIELDS or not isinstance(v, str)
            )
            if bad:
                out.append(
                    f"author 는 {sorted(AP_V1_AUTHOR_FIELDS)} 문자열만 허용한다 — 위반 키 {bad}"
                )
    return out


def is_edition(target: dict) -> bool:
    """`delivery` 해석. 키가 없으면 main 생성, `"edition"` 이면 판 배포, 그 밖은 정책 오류."""
    delivery = target.get("delivery")
    if delivery is None:
        return False
    if delivery == DELIVERY_EDITION:
        return True
    raise PolicyError(
        f"타겟 '{target.get('id')}': 알 수 없는 delivery 값 {delivery!r} "
        f"(허용: 키 생략 = main 생성, {DELIVERY_EDITION!r})"
    )


def _edition_builder(target: dict) -> str:
    """edition 타겟의 정책 모순을 거부하고 판 빌더 경로(안내 문구용)를 돌려준다."""
    for key in _EDITION_FORBIDDEN_KEYS:
        # 빈 값(null·{})도 금지 — 의도가 모호한 정책을 조용히 받지 않는다
        if key in target:
            raise PolicyError(
                f"타겟 '{target['id']}': delivery:edition 인데 {key} 가 있다 — edition 은 main 에 "
                f"생성물을 만들지 않는다(판 경로는 판 빌더 상수)"
            )
    builder = target.get("editionBuilder")
    if not isinstance(builder, str) or not builder:
        raise PolicyError(
            f"타겟 '{target['id']}': delivery:edition 에는 editionBuilder(판 빌더 경로)가 필요하다"
        )
    return builder


def build_marketplace(ssot: dict, target: dict, plugin_root_rel: str) -> dict | None:
    """타겟의 마켓플레이스 카탈로그(있는 경우만). codex 전용, antigravity는 None.

    `target["marketplace"]`의 `legacyAlsoRead`/`_meta` 키는 여기서 읽지 않는다 —
    생성물 필드가 아니라 "Codex가 legacy 경로도 읽는다"는 사실을 정책 문서에
    남겨두는 순수 주석용 필드다(적대적 리뷰 2026-08-27 확인 — 결함 아님).
    """
    mk = target.get("marketplace")
    if not mk:
        return None
    entry: dict = {
        "name": f"{ssot['name']}-marketplace",
        "plugins": [
            {
                "name": ssot["name"],
                "source": {"source": "local", "path": f"./{plugin_root_rel}"},
                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            }
        ],
    }
    iface = target.get("interface", {})
    if iface.get("displayName"):
        entry["interface"] = {"displayName": iface["displayName"]}
    if iface.get("category"):
        entry["plugins"][0]["category"] = iface["category"]
    return entry


def build_hooks(plugin_root: Path, target: dict) -> dict | None:
    """타겟의 훅 매니페스트(있는 경우만). 현재는 codex 전용.

    **왜 별도 파일인가.** Claude Code 의 `plugins/common/hooks/hooks.json` 은 exec
    form(`command` + `args[]`)이고, Codex 는 그 형식을 **로드하지 않는다** — 한 문자열
    안에 인터프리터와 인용된 경로가 들어가야 한다 [confirmed: W-022 S4/R5]. 형식이
    다르므로 한 파일을 둘이 공유할 수 없다. 그래서 SSOT 는 정책(`packaging/targets.json`)
    에 두고 타겟별 파일을 **생성**한다 — 손으로 두 벌 유지하면 조용히 갈린다.

    **matcher 를 쓰지 않는다.** Codex 가 `matcher` 를 해석하는지 실측하지 않았다.
    필터링은 훅 스크립트 자신이 페이로드의 `tool_name` 으로 한다(측정하지 않은 것을
    싣지 않는다는 계약).

    선언된 스크립트가 실재하지 않으면 **exit 1** 이다. 없는 스크립트를 가리키는
    훅은 소비자 세션에서 매번 조용히 실패하고, 그 침묵이 "훅이 돌고 있다"는
    착각을 유지시킨다.
    """
    spec = target.get("hooks")
    if not spec:
        return None
    interpreter = _quote_interpreter(spec.get("interpreter", ""))
    events: dict = {}
    events_spec = _require(spec, "events", f"타겟 '{target['id']}' hooks")
    if not isinstance(events_spec, dict):
        raise PolicyError(f"타겟 '{target['id']}' hooks.events: 객체가 필요하다")
    for event, entries in events_spec.items():
        built = []
        for entry in entries:
            rel = _require(
                entry, "script", f"타겟 '{target['id']}' hooks.events.{event}[]"
            )
            resolved = _policy_path(plugin_root, rel, "hooks.script")
            if not resolved.is_file():
                raise PolicyError(
                    f"타겟 '{target['id']}': 선언된 훅 스크립트가 없다 — {rel}\n"
                    f"  (packaging/targets.json 의 hooks.events.{event} 가 가리킨다)"
                )
            # Ship the confined, normalized path, not an unchecked second resolution.
            quoted = _quote_hook_path(resolved.relative_to(plugin_root).as_posix())
            command = f"{interpreter} {quoted}" if interpreter else quoted
            for arg in entry.get("args", []):
                if not isinstance(arg, str) or not _HOOK_ARG_RE.fullmatch(arg):
                    raise PolicyError(
                        f"타겟 '{target['id']}': 훅 인자에 허용되지 않는 문자 — {arg!r}\n"
                        f"  (packaging/targets.json 의 hooks.events.{event}[].args)"
                    )
                command += f" {arg}"
            hook: dict = {"type": "command", "command": command}
            if entry.get("timeout"):
                hook["timeout"] = entry["timeout"]
            limit = _context_limit(target["id"], event, entry)
            if limit is not None:
                hook["additionalContextLimit"] = limit
            built.append(hook)
        events[event] = [{"hooks": built}]
    return {"hooks": events}


def _quote_interpreter(value: object) -> str:
    """The interpreter is one executable path, never a shell command or flags."""
    if value == "":
        return ""
    if not isinstance(value, str) or not _HOOK_INTERPRETER_RE.fullmatch(value):
        raise PolicyError(f"hooks.interpreter: 실행 파일 경로가 아니다 — {value!r}")
    if value != value.strip() or value.startswith("-"):
        raise PolicyError(f"hooks.interpreter: 잘못된 실행 파일 경로 — {value!r}")
    return shlex.quote(value)


def _quote_hook_path(relative: str) -> str:
    """Expand only the plugin root; double-quote metacharacters in the literal tail."""
    escaped = relative.translate(str.maketrans({char: "\\" + char for char in '\\$`"'}))
    return '"${CLAUDE_PLUGIN_ROOT}/' + escaped + '"'


def _context_limit(target_id: str, event: str, entry: dict) -> int | None:
    """훅 엔트리의 `additionalContextLimit` — 없으면 None(생성물에 키를 싣지 않는다).

    Codex 핸들러 설정 필드다(`codex-rs/config/src/hook_config.rs`, 상류 PR #34393):
    미설정이면 2,500 토큰에서 훅 출력을 잘라 머리·꼬리만 모델에 주고, `0` 이면 자르지
    않는다. 값의 근거는 `packaging/targets.json` 의 `hooks._evidence.hookContextSpill`.

    `bool` 을 따로 거부하는 이유: `True` 는 `int` 의 하위 타입이라 `isinstance` 를
    통과하고, 직렬화하면 `true` 가 된다 — Codex 가 그것을 무엇으로 읽든 **우리가 정한
    값이 아니다.**
    """
    if "additionalContextLimit" not in entry:
        return None
    value = entry["additionalContextLimit"]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PolicyError(
            f"타겟 '{target_id}': additionalContextLimit 은 0 이상의 정수여야 한다 — "
            f"{value!r}\n  (packaging/targets.json 의 hooks.events.{event}[])"
        )
    return value


_FM_LINE_RE = re.compile(r"^([A-Za-z0-9_-]+):[ \t]*(.*?)[ \t]*$")
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")


def read_skill_frontmatter(skill_md: Path) -> dict[str, str]:
    """SKILL.md 의 YAML frontmatter 를 **한 줄 `key: value`** 로만 읽는다.

    stdlib only 라 YAML 파서가 없다. 킷 스킬의 frontmatter 는 전부 한 줄 평문이므로
    그 형태만 받아들이고, 블록 스칼라·여러 줄 값처럼 읽지 못하는 형태는 **추측하지 않고**
    PolicyError 로 거부한다 — 잘못 읽은 값을 생성물에 싣는 것보다 멈추는 편이 낫다.
    """
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError as err:
        raise PolicyError(f"스킬 파일을 읽지 못했다: {skill_md} ({err})") from err
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise PolicyError(f"frontmatter 가 없다: {skill_md}")
    out: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return out
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = _FM_LINE_RE.match(line)
        if m is None or m.group(2) in ("|", ">", "|-", ">-", ""):
            raise PolicyError(
                f"frontmatter 를 한 줄 `key: value` 로 읽지 못했다: {skill_md}\n"
                f"  줄: {line!r} — 블록 스칼라·여러 줄 값은 지원하지 않는다"
            )
        value = m.group(2)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        out[m.group(1)] = value
    raise PolicyError(f"frontmatter 가 닫히지 않았다: {skill_md}")


def build_skill_interface(frontmatter: dict[str, str], spec: dict, skill: str) -> dict:
    """스킬 하나의 Codex 메타데이터(`agents/openai.yaml`) 내용. 매핑은 정책(`spec`)이 정한다.

    `implicitInvocationOffWhen` 키가 frontmatter 에서 `true` 일 때만 `policy` 를 싣는다 —
    키가 없는 스킬에 기본값(true)을 적으면 SSOT 에 없는 결정이 생성물에 생긴다.
    """
    first = set(spec.get("firstSentence", []))
    interface: dict = {}
    mapping = _require(spec, "interfaceFrom", f"스킬 '{skill}' skillInterface")
    if not isinstance(mapping, dict):
        raise PolicyError(
            f"스킬 '{skill}' skillInterface.interfaceFrom: 객체가 필요하다"
        )
    for field, src in mapping.items():
        value = frontmatter.get(src, "").strip()
        if field in first:
            value = _SENTENCE_END_RE.split(value, maxsplit=1)[0].strip()
        if not value:
            # 제출 검사(skill_agent_interface_missing)가 빈 값을 거부한다.
            raise PolicyError(
                f"스킬 '{skill}': interface.{field} 의 원천 frontmatter `{src}` 가 비어 있다"
            )
        interface[field] = value
    out: dict = {"interface": interface}
    off_key = spec.get("implicitInvocationOffWhen")
    if off_key and frontmatter.get(off_key, "").lower() == "true":
        out["policy"] = {"allow_implicit_invocation": False}
    return out


def _yaml_scalar(value: object) -> str:
    """JSON 문자열은 YAML 큰따옴표 스칼라로도 유효하다 — 이스케이프를 직접 짜지 않는다."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return json.dumps(value, ensure_ascii=False)


def _dumps_yaml(d: dict) -> str:
    """2단 매핑만 쓰는 결정론적 YAML. 키 순서는 내용 dict 의 순서(정책 순서) 그대로."""
    lines = [
        "# 자동 생성 — scripts/build-targets.py (packaging/targets.json skillInterface).",
        "# 손으로 고치지 말 것: SKILL.md frontmatter 를 고치고 --write 로 재생성한다.",
    ]
    for section, body in d.items():
        lines.append(f"{section}:")
        for key, value in body.items():
            lines.append(f"  {key}: {_yaml_scalar(value)}")
    return "\n".join(lines) + "\n"


def _dumps(d: dict) -> str:
    """결정론적 직렬화 — 키 정렬 + 고정 개행. `--check`의 바이트 비교 전제."""
    return json.dumps(d, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _resolve_in_repo(
    container_root: Path, rel_path: str
) -> tuple[Path | None, str | None]:
    """`rel_path`(정책 파일의 문자열)를 `container_root` 안으로만 한정해 해석한다.

    `container_root / rel_path`는 `rel_path`가 절대경로면 `container_root`를 버리고
    `rel_path` 그대로가 된다(pathlib의 문서화된 동작). `..`나 심링크로도 트리 밖으로
    나갈 수 있다 — 셋 다 `resolve()` 한 번으로 정규화한 뒤 `container_root` 하위인지
    대조하면 전부 같은 검사로 잡힌다. **호출자는 이 결과(Path)를 그대로 재사용해야
    한다** — 다시 `container_root / rel_path`를 계산하면 검증한 값과 실제로 쓰는 값이
    달라질 수 있다(모듈 docstring 원칙 6).

    시그니처는 `scripts/check_eval_coverage.py::_resolve_in_repo`와 **동일**하다
    (D-15: 구현은 여러 벌, 계약만 하나 — 파라미터 이름까지 통일해 둔다).
    공유 적대적 케이스 표는 `scripts/tests/resolve_in_repo_contract.py`.
    """
    real = (container_root / rel_path).resolve()
    try:
        real.relative_to(container_root.resolve())
    except ValueError:
        return None, f"레포 루트 밖을 가리킨다 → {real}"
    return real, None


def _policy_path(root: Path, value: object, field: str) -> Path:
    """Confine policy reads and writes with the same resolver and controlled errors."""
    if not isinstance(value, str) or not value or "\0" in value:
        raise PolicyError(f"{field}: 비어 있지 않은 경로 문자열이 필요하다")
    try:
        resolved, error = _resolve_in_repo(root, value)
    except (OSError, RuntimeError) as err:
        raise PolicyError(f"{field}: 경로를 해석하지 못했다 — {err}") from err
    if resolved is None:
        raise PolicyError(f"{field}: 경로 탈출 차단 — {error}")
    return resolved


def _source_path(root: Path, policy: dict, field: str) -> Path:
    source = policy.get("source")
    if not isinstance(source, dict):
        raise PolicyError("source: 경로 설정 객체가 필요하다")
    return _policy_path(root, source.get(field), f"source.{field}")


class Artifact:
    """타겟 하나가 만드는 파일 하나(매니페스트 또는 마켓플레이스)와 그 계산된 내용.

    `resolved_path`는 생성 시점에 **한 번만** 계산된다 — `--check`/`--write` 양쪽이
    이 값을 그대로 쓴다(원칙 6). 레포 루트 밖으로 나가면 `resolved_path`가 `None`이고
    `escape_error`에 사유가 담긴다.
    """

    def __init__(
        self,
        target_id: str,
        kind: str,
        rel_path: str,
        content: dict,
        repo_root: Path,
        text: str | None = None,
    ):
        self.target_id = target_id
        self.kind = kind  # "manifest" | "hooks" | "marketplace" | "skill-interface"
        self.rel_path = rel_path
        self.content = content
        self.text = _dumps(content) if text is None else text
        self.resolved_path, self.escape_error = _resolve_in_repo(repo_root, rel_path)


def artifacts_for(
    repo_root: Path, policy: dict, ssot: dict, target: dict
) -> list[Artifact]:
    manifest_path = target.get("manifestPath")
    if not isinstance(manifest_path, str) or not manifest_path:
        raise PolicyError(
            f"타겟 '{target.get('id')}': manifestPath 가 없다 — main 에 생성하는 타겟"
            f'(delivery 생략)에는 필수다. 판으로 배포한다면 delivery:"edition" 을 쓴다'
        )
    plugin_root = _source_path(repo_root, policy, "pluginRoot")
    present = _detect_components(plugin_root, policy)
    out = [
        Artifact(
            target["id"],
            "manifest",
            manifest_path,
            build_manifest(ssot, target, present),
            repo_root,
        )
    ]
    # 훅 디렉토리가 없으면 스펙 자체를 계산하지 않는다 — 컴포넌트는 실측으로 판정하므로
    # (`_meta.detection`), 없는 컴포넌트의 스크립트 존재를 따지는 것은 의미가 없다.
    if "hooks" in present:
        hooks = build_hooks(plugin_root, target)
        if hooks is not None:
            out.append(
                Artifact(
                    target["id"],
                    "hooks",
                    _require(target["hooks"], "path", f"타겟 '{target['id']}' hooks"),
                    hooks,
                    repo_root,
                )
            )
    spec = target.get("skillInterface")
    if spec and "skills" in present:
        skills_dir = _policy_path(plugin_root, "skills", "source.componentDirs")
        root_real = repo_root.resolve()
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            skill = skill_md.parent.name
            content = build_skill_interface(
                read_skill_frontmatter(skill_md), spec, skill
            )
            out_path = _policy_path(
                skill_md.parent,
                _require(spec, "path", f"타겟 '{target['id']}' skillInterface"),
                "skillInterface.path",
            )
            out.append(
                Artifact(
                    target["id"],
                    "skill-interface",
                    out_path.relative_to(root_real).as_posix(),
                    content,
                    repo_root,
                    text=_dumps_yaml(content),
                )
            )
    mk = build_marketplace(
        ssot, target, plugin_root.relative_to(repo_root.resolve()).as_posix()
    )
    if mk is not None:
        out.append(
            Artifact(
                target["id"],
                "marketplace",
                _require(
                    target["marketplace"], "path", f"타겟 '{target['id']}' marketplace"
                ),
                mk,
                repo_root,
            )
        )
    return out


def _selected_targets(policy: dict, only: str | None) -> tuple[list[dict], list[str]]:
    """정책의 타겟 목록에서 이번 실행이 다룰 타겟들. (선택됨, 경고 메시지들)을 반환.

    `only`가 없으면 enabled:true 전체 — `--check`·`--write` 둘 다 이 범위를 쓴다(대칭).
    `only`가 있으면 그 하나만 — 존재하지 않으면 PolicyError(명확한 실패), enabled:false면
    빈 목록+경고(조용한 성공이 아니라 "왜 아무것도 안 됐는지"를 보여준다).
    """
    all_targets = validate_targets(policy)
    if only is None:
        return [t for t in all_targets if t.get("enabled") and not is_edition(t)], []
    t = _find_target(policy, only)
    if t is None:
        known = ", ".join(sorted(x["id"] for x in all_targets)) or "(없음)"
        raise PolicyError(
            f"--only '{only}' 는 정책에 없는 타겟 id다. 알려진 id: {known}"
        )
    if is_edition(t):
        raise PolicyError(
            f"--only '{only}' 는 delivery:edition 타겟이다 — main 에 생성물이 없고, 판 트리 생성·검사는 "
            f"판 빌더({_edition_builder(t)})가 담당한다. 매니페스트 계산 판정만 보려면 "
            f"--only 없이 --check 를 돌려라."
        )
    if not t.get("enabled"):
        return [], [
            f"'{only}' 는 enabled:false — 건너뜀 ({t.get('_disabledReason', '사유 미기재')})"
        ]
    return [t], []


def _main_artifacts(
    repo_root: Path, policy: dict, ssot: dict, only: str | None
) -> list[tuple[dict, list[Artifact]]]:
    """main 에 생성하는 활성 타겟 전부의 생성물을 정책 순서대로. 충돌·불변식 검사는 `--only`
    와 무관하게 이 전체로 한다 — 좁힌 타겟의 쓰기가 다른 타겟의 생성물을 덮을 수 있다.

    키를 id 로 두지 않는다(목록 순서 그대로) — id 유일성은 `validate_targets` 가 따로 지킨다.
    """
    out: list[tuple[dict, list[Artifact]]] = []
    for target in validate_targets(policy):
        if not target.get("enabled") or is_edition(target):
            continue
        try:
            out.append((target, artifacts_for(repo_root, policy, ssot, target)))
        except PolicyError as err:
            if only is not None and target["id"] != only:
                raise PolicyError(
                    f"{err}\n  (--only {only}: 충돌 검사를 위해 활성 타겟 전체를 계산했다 — "
                    f"실패 타겟: {target['id']})"
                ) from err
            raise
    return out


def _arts_of(
    all_arts: list[tuple[dict, list[Artifact]]], target: dict
) -> list[Artifact]:
    for t, arts in all_arts:
        if t is target:
            return arts
    raise PolicyError(f"타겟 '{target.get('id')}': 생성물 계산에서 빠졌다 (내부 오류)")


def _path_key(p: Path) -> tuple[str, ...]:
    """비교 키. darwin 은 기본 파일시스템이 대소문자를 무시하므로 casefold 로 접는다."""
    if sys.platform == "darwin":
        return tuple(part.casefold() for part in p.parts)
    return p.parts


def _same_path(a: Path, b: Path) -> bool:
    """같은 파일인가 — 정규화 경로·대소문자(darwin)·이미 있는 파일의 inode(하드링크) 순으로 본다."""
    if _path_key(a) == _path_key(b):
        return True
    try:
        return a.exists() and b.exists() and os.path.samefile(a, b)
    except OSError:
        return False


def _overlaps(a: Path, b: Path) -> bool:
    """같은 파일이거나 한쪽이 다른 쪽의 상위 디렉토리면 겹친다."""
    if _same_path(a, b):
        return True
    ka, kb = _path_key(a), _path_key(b)
    shorter, longer = (ka, kb) if len(ka) < len(kb) else (kb, ka)
    return longer[: len(shorter)] == shorter


def _input_paths(
    repo_root: Path, policy: dict, policy_path: Path | None
) -> list[tuple[str, Path]]:
    """생성기가 **읽는** 입력. 생성물이 이것과 겹치면 생성이 자기 입력을 덮는다."""
    plugin_root = _source_path(repo_root, policy, "pluginRoot")
    out = [("source.manifest(SSOT)", _source_path(repo_root, policy, "manifest"))]
    if policy_path is not None:
        out.append(("정책 파일", policy_path.resolve()))
    present = _detect_components(plugin_root, policy)
    if "skills" in present:
        skills_dir = _policy_path(plugin_root, "skills", "source.componentDirs")
        out += [
            ("스킬 원본", p.resolve()) for p in sorted(skills_dir.glob("*/SKILL.md"))
        ]
    if "hooks" in present:
        for target in validate_targets(policy):
            spec = target.get("hooks")
            if (
                not target.get("enabled")
                or is_edition(target)
                or not isinstance(spec, dict)
            ):
                continue
            events = spec.get("events")
            for entries in events.values() if isinstance(events, dict) else []:
                for entry in entries if isinstance(entries, list) else []:
                    script = entry.get("script") if isinstance(entry, dict) else None
                    if isinstance(script, str) and script:
                        out.append(
                            (
                                "훅 스크립트",
                                _policy_path(plugin_root, script, "hooks.script"),
                            )
                        )
    return out


def _path_collisions(
    repo_root: Path, arts: list[Artifact], inputs: list[tuple[str, Path]]
) -> list[str]:
    """정규화 경로(`Artifact.resolved_path`, `_resolve_in_repo` 결과)가 겹치는 쌍.

    생성물끼리(같은 타겟 안 포함), 그리고 생성물과 읽기 전용 입력 사이를 본다. 탈출
    경로(None)는 여기서 보지 않는다 — 각 모드가 "경로 탈출 차단" 으로 따로 보고한다.
    """
    root = repo_root.resolve()

    def shown(p: Path) -> str:
        try:
            return p.relative_to(root).as_posix()
        except ValueError:
            return str(p)

    placed = [a for a in arts if a.resolved_path is not None]
    out: list[str] = []
    for i, a in enumerate(placed):
        for b in placed[i + 1 :]:
            if _overlaps(a.resolved_path, b.resolved_path):
                out.append(
                    f"{a.target_id}:{a.rel_path} ↔ {b.target_id}:{b.rel_path} "
                    f"(정규화 경로 {shown(a.resolved_path)} · {shown(b.resolved_path)})"
                )
        for label, path in inputs:
            if _overlaps(a.resolved_path, path):
                out.append(
                    f"{a.target_id}:{a.rel_path} ↔ 입력 {label} {shown(path)} "
                    f"(생성이 자기 입력을 덮는다)"
                )
    return out


def _report_collisions(
    repo_root: Path,
    policy: dict,
    all_arts: list[tuple[dict, list[Artifact]]],
    policy_path: Path | None,
) -> bool:
    flat = [a for _, arts in all_arts for a in arts]
    collisions = _path_collisions(
        repo_root, flat, _input_paths(repo_root, policy, policy_path)
    )
    for c in collisions:
        print(f"[build-targets] ✗ 출력 경로 충돌 — {c}")
    if collisions:
        print(
            "  → 생성 전에 중단했다. packaging/targets.json 의 출력 경로를 서로 겹치지 않게 고쳐라."
        )
    return bool(collisions)


def _check_editions(repo_root: Path, policy: dict, ssot: dict) -> tuple[int, bool]:
    """edition 타겟 전부(enabled 무관)의 매니페스트를 계산해 AP v1 판정. (판정 수, 실패 여부)."""
    plugin_root = _source_path(repo_root, policy, "pluginRoot")
    present = _detect_components(plugin_root, policy)
    fail = False
    count = 0
    for target in validate_targets(policy):
        if not is_edition(target):
            continue
        count += 1
        problems = ap_v1_violations(build_manifest(ssot, target, present))
        for problem in problems:
            print(
                f"[build-targets] ✗ edition '{target['id']}' AP v1 판정 실패 — {problem}"
            )
        if problems:
            fail = True
        else:
            print(
                f"[build-targets] ✓ edition '{target['id']}' — AP v1 매니페스트 계산 판정 통과 "
                f"(main 생성물 없음, 판은 {_edition_builder(target)})"
            )
    return count, fail


def _invariant_computed(
    repo_root: Path, policy: dict, all_arts: list[tuple[dict, list[Artifact]]]
) -> bool:
    """fail-closed 불변식을 **계산된 생성물**로 판정한다. 위반이면 True.

    디스크만 보면 `--write` 가 위반을 직접 만들거나(정책의 schemaUrl 을 AP URL 로 바꾼 경우)
    `--check --only` 가 그것을 놓친다(적대적 리뷰 ATK-003). 그래서 기록 전에 이것을 본다.
    """
    plugin_root = _source_path(repo_root, policy, "pluginRoot")
    rel_root = plugin_root.relative_to(repo_root.resolve()).as_posix()
    manifest = plugin_root / AP_V1_MANIFEST_NAME
    natives = [plugin_root / n for n in HERMES_NATIVE_MANIFESTS]
    fail = False
    for _, arts in all_arts:
        for art in arts:
            p = art.resolved_path
            if p is None:
                continue
            if any(_same_path(p, n) for n in natives):
                print(
                    f"[build-targets] ✗ fail-closed 불변식 위반 — 생성물 {art.target_id}:{art.rel_path} "
                    f"가 {rel_root} 의 Hermes 네이티브 매니페스트 자리다"
                )
                fail = True
            elif (
                _same_path(p, manifest)
                and isinstance(art.content, dict)
                and art.content.get("$schema") == AP_V1_SCHEMA_URL
            ):
                print(
                    f"[build-targets] ✗ fail-closed 불변식 위반 — 생성물 {art.target_id}:{art.rel_path} "
                    f"가 $schema 를 AP v1 URL 로 쓴다 (ref 없는 Hermes 설치가 main 트리를 받아들이게 된다)"
                )
                fail = True
    return fail


def _check_fail_closed_invariant(repo_root: Path, policy: dict) -> bool:
    """main 의 플러그인 루트(디스크)가 Hermes 에 설치 가능한 패키지로 보이지 않는가. 위반이면 True.

    판정할 수 없는 상태(읽기·파싱 실패)는 통과로 치지 않는다. 읽기 경로는 `_policy_path` 로
    봉쇄한다 — 심링크로 레포 밖을 가리키면 PolicyError(exit 1)다.
    """
    plugin_root = _source_path(repo_root, policy, "pluginRoot")
    rel_root = plugin_root.relative_to(repo_root.resolve()).as_posix()
    fail = False
    for name in HERMES_NATIVE_MANIFESTS:
        # lexists: 끊어진 심링크도 "있다"로 본다 — 판정을 관대하게 하지 않는다(lstat 만, 읽지 않는다).
        if os.path.lexists(plugin_root / name):
            print(
                f"[build-targets] ✗ fail-closed 불변식 위반 — {rel_root}/{name} 이 있다 "
                f"(Hermes 가 main 트리를 네이티브 플러그인으로 읽는다)"
            )
            fail = True
    if os.path.lexists(plugin_root / AP_V1_MANIFEST_NAME):
        manifest = _policy_path(plugin_root, AP_V1_MANIFEST_NAME, "fail-closed 불변식")
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError) as err:
            print(
                f"[build-targets] ✗ fail-closed 불변식 판정 불가 — {rel_root}/{AP_V1_MANIFEST_NAME} "
                f"를 읽지 못했다 ({err})"
            )
            return True
        if not isinstance(data, dict):
            print(
                f"[build-targets] ✗ fail-closed 불변식 판정 불가 — {rel_root}/{AP_V1_MANIFEST_NAME} "
                f"가 JSON 객체가 아니다"
            )
            fail = True
        elif data.get("$schema") == AP_V1_SCHEMA_URL:
            print(
                f"[build-targets] ✗ fail-closed 불변식 위반 — {rel_root}/{AP_V1_MANIFEST_NAME} 의 "
                f"$schema 가 AP v1 URL 이다 (ref 없는 Hermes 설치가 main 트리를 받아들이게 된다)"
            )
            fail = True
    return fail


def cmd_check(
    repo_root: Path, policy: dict, only: str | None, policy_path: Path | None = None
) -> int:
    """드리프트 검사. **항상 읽기 전용.** enabled인데 미생성이면 드리프트다(모듈 docstring 원칙 3).

    충돌·불변식(계산 + 디스크)·edition 판정은 `--only` 와 무관하게 전체로 돈다.
    """
    validate_targets(policy)
    ssot = load_ssot(repo_root, policy)
    require_present = bool(
        policy.get("gate", {}).get("requireGeneratedManifestPresent")
    )
    targets, warnings = _selected_targets(policy, only)
    for w in warnings:
        print(f"[build-targets] i {w}")
    all_arts = _main_artifacts(repo_root, policy, ssot, only)
    fail = _report_collisions(repo_root, policy, all_arts, policy_path)
    fail = _invariant_computed(repo_root, policy, all_arts) or fail
    fail = _check_fail_closed_invariant(repo_root, policy) or fail
    editions, edition_fail = _check_editions(repo_root, policy, ssot)
    fail = edition_fail or fail
    checked = 0
    for target in targets:
        for art in _arts_of(all_arts, target):
            if art.resolved_path is None:
                print(
                    f"[build-targets] ✗ 경로 탈출 차단 — {art.rel_path}: {art.escape_error}"
                )
                fail = True
                continue
            p = art.resolved_path
            if not p.exists():
                if require_present:
                    print(
                        f"[build-targets] ✗ 미생성 — {art.rel_path} (enabled:true인데 생성물이 없다 → 드리프트)\n"
                        f"  → --write --only {art.target_id} 로 생성하라."
                    )
                    fail = True
                else:
                    print(f"[build-targets] · {art.rel_path} — 미생성 (skip)")
                continue
            checked += 1
            try:
                current = p.read_text(encoding="utf-8")
            except OSError as err:
                print(f"[build-targets] ✗ {art.rel_path} 읽기 실패: {err}")
                fail = True
                continue
            if current != art.text:
                print(
                    f"[build-targets] ✗ 드리프트 — {art.rel_path}\n  → --write --only {art.target_id} 로 재생성하라."
                )
                fail = True
    if fail:
        return 1
    tail = f" · edition {editions}개 AP v1 계산 판정 통과 · fail-closed 불변식 통과"
    if checked == 0:
        print(f"[build-targets] ✓ 검사 대상 없음 (enabled 타겟 없음){tail}")
    else:
        print(f"[build-targets] ✓ 생성물 {checked}개 모두 SSOT와 일치{tail}")
    return 0


def cmd_write(
    repo_root: Path, policy: dict, only: str | None, policy_path: Path | None = None
) -> int:
    """생성물 기록. enabled 전체(또는 `--only`로 좁힌 하나)를 쓴다(모듈 docstring 원칙 2).

    **부분 실패 시에도 나머지 아티팩트는 계속 시도한다.** 타겟 2개 중 첫 번째가
    경로 탈출이나 쓰기 실패로 막혀도 두 번째는 시도조차 안 되는 것보다,
    "무엇이 되고 무엇이 안 됐는지"를 전부 보고하는 편이 디버깅에 낫다. 부분적으로
    쓰인 상태를 롤백하지는 않는다 — `--check`가 바로 그 부분 상태(일부만 SSOT와
    일치)를 드리프트로 잡아내므로, 이 명령이 자체적으로 원자성을 보장할 필요가
    없다(적대적 리뷰 2026-08-27, Medium 판정 반영).

    단 **정책 자체의 결함**(출력 경로 충돌, 계산된 생성물의 fail-closed 불변식 위반, edition
    AP v1 판정 실패)은 `--only` 와 무관하게 **아무것도 쓰기 전에** 막는다 — 부분 기록이 아니라
    잘못된 생성물을 만드는 것이기 때문이다.
    """
    validate_targets(policy)
    ssot = load_ssot(repo_root, policy)
    targets, warnings = _selected_targets(policy, only)
    for w in warnings:
        print(f"[build-targets] i {w}")
    all_arts = _main_artifacts(repo_root, policy, ssot, only)
    blocked = _report_collisions(repo_root, policy, all_arts, policy_path)
    blocked = _invariant_computed(repo_root, policy, all_arts) or blocked
    blocked = _check_editions(repo_root, policy, ssot)[1] or blocked
    if blocked:
        print("[build-targets] ✗ 정책 결함 — 아무것도 기록하지 않았다.")
        return 1
    written = 0
    failed = 0
    for target in targets:
        for art in _arts_of(all_arts, target):
            if art.resolved_path is None:
                print(
                    f"[build-targets] ✗ 경로 탈출 차단 — {art.rel_path}: {art.escape_error}"
                )
                failed += 1
                continue
            p = art.resolved_path
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(art.text, encoding="utf-8")
            except OSError as err:
                print(f"[build-targets] ✗ {art.rel_path} 기록 실패: {err}")
                failed += 1
                continue
            print(f"[build-targets] ✓ 기록: {art.rel_path}")
            written += 1
    if failed:
        return 1
    if written == 0:
        print("[build-targets] i 기록 대상 없음 (enabled 타겟이 없거나 모두 제외됨)")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--policy",
        default=str(DEFAULT_POLICY),
        help="정책 파일 경로 (기본: packaging/targets.json)",
    )
    ap.add_argument("--repo-root", default=str(REPO_ROOT), help="레포 루트 (테스트용)")
    ap.add_argument(
        "--only",
        default=None,
        help="이 id 하나만 처리 (기본: enabled 전체 — --check·--write 동일)",
    )
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check", action="store_true", help="드리프트만 검사, 기록하지 않음"
    )
    mode.add_argument("--write", action="store_true", help="생성물 기록")
    args = ap.parse_args(argv)

    repo_root = Path(args.repo_root)
    try:
        policy = load_policy(Path(args.policy))
    except PolicyError as err:
        print(f"[build-targets] ✗ {err}", file=sys.stderr)
        return 1

    try:
        if args.check:
            return cmd_check(repo_root, policy, args.only, Path(args.policy))
        return cmd_write(repo_root, policy, args.only, Path(args.policy))
    except PolicyError as err:
        print(f"[build-targets] ✗ {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
