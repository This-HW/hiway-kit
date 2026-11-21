# 과제

`duration.py` 의 `parse_duration(text)` 는 아직 구현되지 않았다 — docstring 이 스펙이다.
TDD 로 진행하라: 테스트를 먼저 쓰고, 그다음 `parse_duration` 을 구현해 테스트를 통과시킨다.

최소한 다음 케이스를 포함한다: `"1h30m"` → 5400, `"45s"` → 45, `"2m"` → 120,
빈 문자열과 `"5x"` → `ValueError`.
