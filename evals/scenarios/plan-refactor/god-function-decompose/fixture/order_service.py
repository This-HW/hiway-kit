def process_everything(order_data, inventory, customer_db, notifier):
    # 1) 검증
    if not order_data.get("items"):
        raise ValueError("no items")
    for item in order_data["items"]:
        if inventory.get(item["sku"], 0) < item["qty"]:
            raise ValueError("insufficient stock")
    # 2) 재고 차감
    for item in order_data["items"]:
        inventory[item["sku"]] -= item["qty"]
    # 3) 결제 총액 계산
    total = sum(i["price"] * i["qty"] for i in order_data["items"])
    # 4) 고객 DB 갱신
    customer = customer_db.get(order_data["customer_id"], {"orders": []})
    customer["orders"].append(order_data)
    customer_db[order_data["customer_id"]] = customer
    # 5) 알림 발송
    notifier.send(order_data["customer_id"], f"주문 완료: {total}원")
    return total
