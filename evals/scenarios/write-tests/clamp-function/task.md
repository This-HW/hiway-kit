# 과제

`mathutils.py`의 `clamp(value, lo, hi)` 함수에 대한 pytest 테스트를 작성하라.

요구사항:
- 테스트 파일은 같은 디렉토리에 `test_mathutils.py`로 작성한다.
- 최소한 다음 케이스를 포함한다: 범위 내부 값(변경 없음), 하한 미만(하한으로 clamp),
  상한 초과(상한으로 clamp), `lo > hi`일 때 `ValueError` 발생.
- `mathutils.py`(구현 코드) 자체는 수정하지 않는다 — 테스트만 추가한다.
