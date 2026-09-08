from order_utils import calculate_total


def checkout(cart):
    total = calculate_total(cart)
    return {"total": total, "status": "ok"}
