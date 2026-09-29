---
status: in-progress
size: small
---

# 회원 등급 할인 계산

## 요구사항

`final_price(total, tier)` 를 구현한다. 등급별 할인율을 적용하고, 알 수 없는 등급은 ValueError.

## 결정

- domain 계층은 infra 계층을 import 하지 않는다(`.importlinter` 의 `domain-independent-of-infra` 계약).
- 등급별 할인율은 domain 이 소유한다.

## 완료 조건

```bash
lint-imports
python3 -m pytest -q
```
