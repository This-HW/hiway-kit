from order_utils import calculate_total


def daily_report(orders):
    return [calculate_total(o) for o in orders]
