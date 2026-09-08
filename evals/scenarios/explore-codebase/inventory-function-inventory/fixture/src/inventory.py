_stock = {}


def add_widget(name, qty):
    _stock[name] = _stock.get(name, 0) + qty


def remove_widget(name, qty):
    if _stock.get(name, 0) < qty:
        raise ValueError("insufficient stock")
    _stock[name] -= qty


def get_stock_level(name):
    return _stock.get(name, 0)
