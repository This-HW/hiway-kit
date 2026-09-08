_stock = {}


def add_widget(name, qty):
    _stock[name] = _stock.get(name, 0) + qty


def remove_widget(name, qty):
    if _stock.get(name, 0) < qty:
        raise ValueError("insufficient stock")
    _stock[name] -= qty


def get_stock_level(name):
    return _stock.get(name, 0)

# TODO: remove_all_widgets() 함수가 필요하다 — 특정 위젯의 재고를 전량 0으로
# 만드는 기능. 아직 구현되지 않았다.
