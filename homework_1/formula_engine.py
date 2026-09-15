"""Tiered discount calculations for order positions."""

from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


MONEY_QUANTUM = Decimal("0.01")

# Each position is calculated independently. The upper bound of None means
# that the tier continues for all remaining units.
DISCOUNT_TIERS: tuple[tuple[int, int | None, Decimal], ...] = (
    (1, 9, Decimal("0.00")),
    (10, 49, Decimal("0.05")),
    (50, 99, Decimal("0.10")),
    (100, None, Decimal("0.15")),
)


class OrderItem(BaseModel):
    """One order position accepted by the MCP discount tool."""

    model_config = ConfigDict(extra="forbid")

    product_name: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    unit_price: float = Field(ge=0)

    @field_validator("product_name")
    @classmethod
    def product_name_must_not_be_blank(cls, value: str) -> str:
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("product_name must not be blank")
        return cleaned_value

    @field_validator("unit_price")
    @classmethod
    def unit_price_must_be_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("unit_price must be finite")
        return value


def _money(value: Decimal) -> str:
    """Format a Decimal as a two-decimal monetary string."""

    return f"{value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP):.2f}"


def _calculate_position(item: OrderItem) -> tuple[dict[str, Any], Decimal, Decimal]:
    unit_price = Decimal(str(item.unit_price))
    gross_subtotal = (unit_price * item.quantity).quantize(
        MONEY_QUANTUM,
        rounding=ROUND_HALF_UP,
    )
    discount_total = Decimal("0.00")
    tier_breakdown: list[dict[str, Any]] = []

    for lower_bound, upper_bound, rate in DISCOUNT_TIERS:
        if upper_bound is None:
            units = max(0, item.quantity - lower_bound + 1)
            displayed_upper_bound: int | None = None
        else:
            units = max(0, min(item.quantity, upper_bound) - lower_bound + 1)
            displayed_upper_bound = upper_bound

        if units == 0:
            continue

        base_amount = unit_price * units
        discount_amount = (base_amount * rate).quantize(
            MONEY_QUANTUM,
            rounding=ROUND_HALF_UP,
        )
        discount_total += discount_amount

        tier_breakdown.append(
            {
                "from_quantity": lower_bound,
                "to_quantity": displayed_upper_bound,
                "units": units,
                "rate_percent": int(rate * 100),
                "base_amount": _money(base_amount),
                "discount_amount": _money(discount_amount),
            }
        )

    net_total = gross_subtotal - discount_total
    position_result = {
        "product_name": item.product_name,
        "quantity": item.quantity,
        "unit_price": _money(unit_price),
        "gross_subtotal": _money(gross_subtotal),
        "discount_amount": _money(discount_total),
        "net_total": _money(net_total),
        "tiers": tier_breakdown,
    }
    return position_result, gross_subtotal, discount_total


def calculate_tiered_discount(items: list[OrderItem]) -> dict[str, Any]:
    """Calculate progressive discounts independently for each order position."""

    if not items:
        raise ValueError("items must contain at least one order position")

    item_results: list[dict[str, Any]] = []
    total_units = 0
    gross_subtotal = Decimal("0.00")
    discount_total = Decimal("0.00")

    for item in items:
        position_result, position_gross, position_discount = _calculate_position(item)
        item_results.append(position_result)
        total_units += item.quantity
        gross_subtotal += position_gross
        discount_total += position_discount

    return {
        "currency": "EUR",
        "total_units": total_units,
        "gross_subtotal": _money(gross_subtotal),
        "discount_amount": _money(discount_total),
        "net_total": _money(gross_subtotal - discount_total),
        "items": item_results,
    }
