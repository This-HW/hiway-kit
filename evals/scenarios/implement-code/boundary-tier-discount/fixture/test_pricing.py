import pytest

from shop.domain.pricing import final_price


def test_gold_discount():
    assert final_price(1000, "gold") == 900


def test_silver_discount_floors():
    assert final_price(999, "silver") == 949


def test_bronze_has_no_discount():
    assert final_price(500, "bronze") == 500


def test_unknown_tier_rejected():
    with pytest.raises(ValueError):
        final_price(1000, "platinum")
