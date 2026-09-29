"""가격 계산 규칙."""
from shop.infra.rates import RATES


def final_price(total: int, tier: str) -> int:
    """회원 등급 할인율을 적용한 최종 금액(원 단위, 소수점 이하 버림)."""
    if tier not in RATES:
        raise ValueError(f"unknown tier: {tier}")
    return int(total * (1 - RATES[tier]))
