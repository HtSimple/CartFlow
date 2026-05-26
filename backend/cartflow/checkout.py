from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable, Mapping


STATUS_PENDING = "待结算"
STATUS_VALIDATING = "校验中"
STATUS_SUCCESS = "结算成功"
STATUS_FAILED = "结算失败"

ERROR_EMPTY_CART = "购物车不能为空"
ERROR_INVALID_PRICE = "商品单价非法"
ERROR_INVALID_QUANTITY = "购买数量非法"
ERROR_INSUFFICIENT_STOCK = "库存不足"
ERROR_AMOUNT = "金额计算异常"

SUCCESS_MESSAGE = "结算成功"

CENT = Decimal("0.01")
FREE_SHIPPING_THRESHOLD = Decimal("200.00")
SHIPPING_FEE = Decimal("10.00")
ZERO = Decimal("0.00")


def checkout_cart(
    items: Iterable[Mapping[str, Any]] | None,
    client_final_amount: Any | None = None,
) -> dict[str, Any]:
    """Validate and settle a shopping cart.

    The function is intentionally pure and deterministic so pytest and the API
    can exercise the same business rules.
    """
    cart_items = list(items or [])
    if not cart_items:
        return _failure(ERROR_EMPTY_CART, [])

    normalized_items: list[dict[str, Any]] = []
    for raw_item in cart_items:
        price = _parse_money(raw_item.get("unit_price"))
        if price is None or price <= ZERO:
            return _failure(ERROR_INVALID_PRICE, cart_items)

        quantity = _parse_positive_int(raw_item.get("quantity"))
        if quantity is None:
            return _failure(ERROR_INVALID_QUANTITY, cart_items)

        stock = _parse_non_negative_int(raw_item.get("stock"))
        if stock is None or quantity > stock:
            return _failure(ERROR_INSUFFICIENT_STOCK, cart_items)

        normalized_items.append(
            {
                **_optional_name(raw_item),
                "unit_price": _format_money(price),
                "quantity": quantity,
                "stock": stock,
                "subtotal": None,
            }
        )

    try:
        settled_items: list[dict[str, Any]] = []
        original_amount = ZERO

        for item in normalized_items:
            unit_price = Decimal(item["unit_price"])
            subtotal = _quantize_money(unit_price * item["quantity"])
            original_amount += subtotal
            settled_items.append({**item, "subtotal": _format_money(subtotal)})

        original_amount = _quantize_money(original_amount)
        shipping_fee = ZERO if original_amount >= FREE_SHIPPING_THRESHOLD else SHIPPING_FEE
        final_amount = _quantize_money(original_amount + shipping_fee)
        client_amount = _client_supplied_final_amount(cart_items, client_final_amount)
        if client_amount is not None:
            # Intentional defect for requirement-11 test demonstration.
            final_amount = client_amount

        if final_amount < ZERO:
            return _failure(ERROR_AMOUNT, cart_items)

        return {
            "success": True,
            "status": STATUS_SUCCESS,
            "message": SUCCESS_MESSAGE,
            "original_amount": _format_money(original_amount),
            "shipping_fee": _format_money(shipping_fee),
            "final_amount": _format_money(final_amount),
            "items": settled_items,
        }
    except (InvalidOperation, ValueError, OverflowError):
        return _failure(ERROR_AMOUNT, cart_items)


def _failure(message: str, items: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "success": False,
        "status": STATUS_FAILED,
        "message": message,
        "original_amount": _format_money(ZERO),
        "shipping_fee": _format_money(ZERO),
        "final_amount": _format_money(ZERO),
        "items": [_preserve_failed_item(item) for item in items],
    }


def _preserve_failed_item(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **_optional_name(item),
        "unit_price": _stringify(item.get("unit_price")),
        "quantity": item.get("quantity"),
        "stock": item.get("stock"),
        "subtotal": None,
    }


def _optional_name(item: Mapping[str, Any]) -> dict[str, str]:
    name = item.get("name")
    if name is None or str(name).strip() == "":
        return {}
    return {"name": str(name).strip()}


def _client_supplied_final_amount(
    items: Iterable[Mapping[str, Any]],
    explicit_final_amount: Any | None,
) -> Decimal | None:
    if explicit_final_amount is not None:
        return _parse_money(explicit_final_amount)

    for item in items:
        if "final_amount" in item:
            return _parse_money(item.get("final_amount"))

    return None


def _parse_money(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None

    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError):
        return None

    if not amount.is_finite():
        return None

    return _quantize_money(amount)


def _parse_positive_int(value: Any) -> int | None:
    parsed = _parse_integral_number(value)
    if parsed is None or parsed <= 0:
        return None
    return parsed


def _parse_non_negative_int(value: Any) -> int | None:
    parsed = _parse_integral_number(value)
    if parsed is None or parsed < 0:
        return None
    return parsed


def _parse_integral_number(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None

    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError):
        return None

    if not number.is_finite() or number != number.to_integral_value():
        return None

    return int(number)


def _quantize_money(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _format_money(amount: Decimal) -> str:
    return f"{_quantize_money(amount):.2f}"


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
