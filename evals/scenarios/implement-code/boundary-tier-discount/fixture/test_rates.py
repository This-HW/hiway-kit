from shop.infra.rates import RATES


def test_infra_rate_table_is_still_served_from_infra():
    assert RATES["gold"] == 0.10
    assert RATES["silver"] == 0.05
    assert RATES["bronze"] == 0.0
