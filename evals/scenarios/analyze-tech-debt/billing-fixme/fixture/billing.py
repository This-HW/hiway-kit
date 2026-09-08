def charge_customer(customer_id, amount):
    # FIXME(retry-limit): 재시도 횟수가 3으로 하드코딩돼 있음 — 설정으로 빼야 함
    for attempt in range(3):
        ok = _send_to_gateway(customer_id, amount)
        if ok:
            return True
    return False


def _send_to_gateway(customer_id, amount):
    return True
