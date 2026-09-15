import pytest
from pydantic import ValidationError

from formula_engine import OrderItem, calculate_tiered_discount


@pytest.mark.parametrize(
    ("quantity", "expected_discount"),
    [
        (9, "0.00"),
        (10, "0.50"),
        (49, "20.00"),
        (50, "21.00"),
        (99, "70.00"),
        (100, "71.50"),
    ],
)
def test_discount_boundaries(quantity: int, expected_discount: str) -> None:
    result = calculate_tiered_discount(
        [OrderItem(product_name="Test Product", quantity=quantity, unit_price=10.00)]
    )

    assert result["discount_amount"] == expected_discount


def test_progressive_discount_contains_all_tiers() -> None:
    result = calculate_tiered_discount(
        [OrderItem(product_name="Industrial Sensor", quantity=120, unit_price=10.00)]
    )

    assert result["total_units"] == 120
    assert result["gross_subtotal"] == "1200.00"
    assert result["discount_amount"] == "101.50"
    assert result["net_total"] == "1098.50"
    assert [tier["rate_percent"] for tier in result["items"][0]["tiers"]] == [
        0,
        5,
        10,
        15,
    ]


def test_multiple_positions_are_calculated_independently() -> None:
    result = calculate_tiered_discount(
        [
            OrderItem(product_name="Product A", quantity=10, unit_price=10.00),
            OrderItem(product_name="Product B", quantity=50, unit_price=20.00),
        ]
    )

    assert result["total_units"] == 60
    assert result["gross_subtotal"] == "1100.00"
    assert result["discount_amount"] == "42.50"
    assert result["net_total"] == "1057.50"


def test_empty_order_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one"):
        calculate_tiered_discount([])


def test_invalid_order_item_is_rejected() -> None:
    with pytest.raises(ValidationError):
        OrderItem(product_name="", quantity=0, unit_price=-1.0)
