"""가격 계산 규칙."""


def final_price(total: int, tier: str) -> int:
    """회원 등급 할인율을 적용한 최종 금액(원 단위, 소수점 이하 버림)을 반환한다.

    알 수 없는 등급이면 ValueError.
    """
    raise NotImplementedError
