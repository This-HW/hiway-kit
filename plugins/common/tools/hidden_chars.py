"""hidden_chars — 사람 눈에는 안 보이고 모델은 읽는 Unicode 문자의 **단일 정의**.

킷의 산출물은 LLM 이 읽는 프롬프트다. 아래 범위의 문자는 터미널·리뷰 화면에서 보이지 않지만
모델 입력에는 그대로 들어간다 — tag 문자(U+E0000–E007F)는 ASCII 를 한 글자씩 숨겨 실을 수
있고, bidi 제어는 보이는 순서와 읽히는 순서를 갈라놓는다. 그래서 두 자리가 같은 범위를 쓴다:

- 런타임 정제 — `hooks/session-start.py`(활성 계획 제목·상태·디렉토리 이름)와
  `tools/feedback_ledger.py`(원장 기록·digest)가 소비자 레포에서 읽어 세션에 주입하는 문자열
- 배포 텍스트 게이트 — `scripts/check_unicode_safety.py`(레포가 추적하는 텍스트 전량)

## 왜 `tools/` 에 있는가

OpenAI ZIP 과 디렉토리 브랜치는 `hooks/` 를 빼고 `tools/` 는 싣는다(v5.2.0). `tools/` 가
`hooks/` 를 import 하면 그 배포본에서 깨지므로, 공유 정의는 양쪽이 다 실리는 `tools/` 에 둔다.
훅은 이미 `tools/` 를 import 경로에 넣는다(`session-start.py` 의 `TOOLS_DIR`).

## 지우되 지웠다고 적는다

정제는 문자를 **지우고 몇 개 지웠는지 표시**한다(`[hidden-chars-removed:N]`). 조용히 지우면
"원래 깨끗했다"와 "숨긴 것이 있었다"가 출력에서 구분되지 않는다 — 폴백이 발화한 것을
아무도 못 세면 그것은 보호가 아니라 은폐다(`docs/conventions/warning-signal.md` §측정 8).

## 제어 문자는 따로 — `CONTROL_RE`

C0(`\x00-\x1f`)·DEL·C1(`\x80-\x9f`, NEL U+0085 포함)·줄/문단 구분자(U+2028/2029)는 **지우지
않고 공백으로 바꾼다** — 한 줄 라벨 안에서 줄을 쪼개거나 섹션 마커를 흉내 내지 못하게 하는 것이
목적이라, 단어 경계를 남기는 편이 맞다. 은닉 문자 표(`HIDDEN_RANGES`)와 섞지 않는다: 배포 텍스트
게이트는 개행·탭이 정상인 파일을 보므로 이 정규식을 쓰지 않는다.

## 범위 밖 (이 모듈이 막지 않는 것)

- 이형 문자(homoglyph — 키릴 `а` 와 라틴 `a`)는 보이는 문자라 대상이 아니다.
- 변형 선택자 U+FE00–FE0F 는 정상 이모지(❤️ = U+2764 U+FE0F)에 상존해 넣지 않는다 — 넣으면
  이모지가 든 모든 제목에 `[hidden-chars-removed:N]` 가 붙어 표시가 상시 참(소음)이 된다.
  보충 변형 선택자 U+E0100–E01EF 는 넣는다 — 일반 텍스트에 거의 나오지 않고 바이트 밀반입
  통로로 알려져 있다.
- U+00AD(soft hyphen)는 대부분의 렌더러가 줄바꿈 자리에서 하이픈으로 **보여 주고**, 한국어·
  독일어 문서의 복사본에 흔히 섞여 들어온다 — 넣으면 정상 텍스트에 표시가 붙는다.
- U+2061–2064(보이지 않는 수학 연산자 — 함수 적용·곱셈·구분·덧셈)는 수식 마크업(MathML 등)에서
  의미를 갖고, 보이지 않는 **문자열을 실어 나를 수 없다**(네 개뿐이라 tag 문자처럼 ASCII 를
  인코딩하지 못한다).
- 그 밖의 서식 문자(Cf — 아랍 숫자 기호 U+0600–0605 등)는 해당 문자 체계에서 보이게 렌더된다.

**폴백은 이 표의 상위집합이다.** 이 모듈을 import 하지 못한 배치(`session-start.py`·
`feedback_ledger.py` 의 `except ImportError`)는 범주 Cf·Cn·Zl·Zp 전체와 U+E0000–E007F·
U+E0100–E01EF 를 지운다 — 위 표의 모든 코드포인트가 그 안에 든다(테스트가 전수로 확인한다).

Python 3.9 floor — 훅과 같이 소비자의 python3 로 돈다.
"""

from __future__ import annotations

import re

#: (시작, 끝(포함), 분류). **범위를 바꾸려면 여기만 고친다** — 정제·게이트가 전부 이 표를 읽는다.
HIDDEN_RANGES: tuple[tuple[int, int, str], ...] = (
    (0x200B, 0x200D, "zero-width"),  # ZWSP · ZWNJ · ZWJ
    (0x2060, 0x2060, "zero-width"),  # WORD JOINER
    (0x180E, 0x180E, "zero-width"),  # MONGOLIAN VOWEL SEPARATOR (Unicode 6.3 부터 Cf, 폭 0)
    (0xFEFF, 0xFEFF, "zero-width"),  # ZWNBSP / BOM
    (0x200E, 0x200F, "bidi"),  # LRM · RLM
    (0x061C, 0x061C, "bidi"),  # ARABIC LETTER MARK
    (0x202A, 0x202E, "bidi"),  # LRE · RLE · PDF · LRO · RLO
    (0x2066, 0x2069, "bidi"),  # LRI · RLI · FSI · PDI
    # 폐기된 서식 문자 — 대칭 교환·아랍 모양·국가 숫자 형태 억제/활성. 렌더러가 무시해 보이지 않는다
    (0x206A, 0x206F, "deprecated-format"),
    # 행간 주석 앵커·구분자·종결자 — 주석 텍스트를 보이지 않게 끼워 넣을 수 있다
    (0xFFF9, 0xFFFB, "interlinear-annotation"),
    (0xE0000, 0xE007F, "tag"),  # TAG 문자 — ASCII 를 보이지 않게 싣는다
    (0xE0100, 0xE01EF, "variation-selector-supplement"),
)

#: 정제가 남기는 표시의 접두사 — 테스트·소비자가 이 문자열로 표시를 찾는다.
REMOVED_MARKER_PREFIX = "[hidden-chars-removed:"

HIDDEN_RE = re.compile(
    "[" + "".join(f"\\U{lo:08x}-\\U{hi:08x}" for lo, hi, _ in HIDDEN_RANGES) + "]"
)

#: 한 줄 라벨에서 **공백으로 바꿀** 제어 문자 — C0·DEL·C1(NEL 포함)·U+2028/2029. 위 독스트링 참고.
CONTROL_RE = re.compile("[\x00-\x1f\x7f-\x9f\u2028\u2029]+")


def classify(codepoint: int) -> str | None:
    """코드포인트의 분류(`zero-width`·`bidi`·`tag`·…) — 대상이 아니면 None."""
    for lo, hi, kind in HIDDEN_RANGES:
        if lo <= codepoint <= hi:
            return kind
    return None


def strip_hidden(text: str) -> tuple[str, int]:
    """은닉 문자를 지운 문자열과 **지운 개수**. 표시는 붙이지 않는다(호출부가 자리를 정한다)."""
    cleaned, removed = HIDDEN_RE.subn("", text)
    return cleaned, removed


def removed_marker(removed: int) -> str:
    """지운 개수의 가시 표시 — 0 이면 빈 문자열(깨끗한 입력에 소음을 붙이지 않는다)."""
    return f"{REMOVED_MARKER_PREFIX}{removed}]" if removed else ""


def sanitize_hidden(text: str) -> str:
    """지우고, 지웠으면 끝에 ` [hidden-chars-removed:N]` 을 붙인다. 멱등이다.

    표시는 ASCII 라 다시 정제해도 지울 것이 없다 — 같은 값을 두 번 거쳐도(원장 upsert →
    digest) 표시가 겹치지 않는다.
    """
    cleaned, removed = strip_hidden(text)
    return f"{cleaned} {removed_marker(removed)}" if removed else cleaned
