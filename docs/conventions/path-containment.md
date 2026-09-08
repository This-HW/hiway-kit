**같은 결함이 세 번 반복됐다.** 정책·설정 파일에서 읽은 값으로 파일 경로를 조립하는 코드가
그 값을 검증하지 않으면 레포 밖을 읽거나 쓴다. `pathlib` 의 `a / b` 는 **`b` 가 절대경로면 `a` 를
통째로 버린다** — 이 한 줄이 세 번 모두의 원인이었다.

| 인스턴스 | 발견 | 증상 |
| --- | --- | --- |
| `export_harness.py` | 2.14.1 적대적 리뷰 | 심링크 탈출 + 검사/쓰기가 각각 resolve (TOCTOU) |
| `build-targets.py` | 2.15.0 교차 리뷰 | `manifestPath` 절대경로·`..`·심링크 3종 전부 레포 밖에 **씀** |
| `check_eval_coverage.py` | 2.15.0 기획 세션 전수조사 | `baseline.file` 절대경로로 레포 밖 파일을 기준선으로 **신뢰하고 green** |

**규칙**:

1. 설정에서 온 경로는 **한 번만 resolve** 하고 그 결과를 끝까지 쓴다. 검사와 사용이 각각
   resolve하면 그 틈이 TOCTOU다 (`_resolve_target()` / `_resolve_in_repo()` 관례)
2. resolve 결과가 **레포 루트(또는 정해진 하위 디렉토리) 안**이 아니면 **exit 1**. 절대경로·`..`·심링크 전부
3. **읽기 경로도 봉쇄한다.** 세 번째 인스턴스는 읽기 전용인데도 게이트가 거짓 green을 냈다
4. `--check` 같은 **검사 전용 모드에도 같은 봉쇄를 건다.** 2.14.1은 쓰기에만 걸어 구멍이 남았다

새 코드가 설정값으로 경로를 만든다면 이 레포의 `scripts/build-targets.py`(`_resolve_in_repo`) 또는
`plugins/common/hooks/export_harness.py`(`_resolve_target`)의 헬퍼를 **그대로 따라라.** 관례를 새로
발명하는 것이 이 결함이 반복된 이유다.
