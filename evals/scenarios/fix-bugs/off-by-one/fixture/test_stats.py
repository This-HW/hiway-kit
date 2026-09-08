from stats import total_count


def test_total_count_all_items():
    items = [{"qty": 1}, {"qty": 2}, {"qty": 3}]
    assert total_count(items) == 6


def test_total_count_empty():
    assert total_count([]) == 0


def test_total_count_single_item():
    assert total_count([{"qty": 5}]) == 5
