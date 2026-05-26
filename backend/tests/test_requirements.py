from __future__ import annotations

from time import perf_counter

from cartflow.checkout import checkout_cart


def test_r1_r8_single_item_checkout_success() -> None:
    result = checkout_cart([{"name": "智能手环", "unit_price": 99.99, "quantity": 1, "stock": 2}])

    assert result["success"] is True
    assert result["status"] == "结算成功"
    assert result["items"][0]["name"] == "智能手环"
    assert result["items"][0]["unit_price"] == "99.99"
    assert result["items"][0]["quantity"] == 1
    assert result["items"][0]["stock"] == 2
    assert result["items"][0]["subtotal"] == "99.99"
    assert result["original_amount"] == "99.99"
    assert result["shipping_fee"] == "10.00"
    assert result["final_amount"] == "109.99"


def test_r1_r4_r8_multiple_items_checkout_success() -> None:
    result = checkout_cart(
        [
            {"name": "商品A", "unit_price": 50, "quantity": 2, "stock": 3},
            {"name": "商品B", "unit_price": 25.50, "quantity": 4, "stock": 4},
        ]
    )

    assert result["success"] is True
    assert [item["subtotal"] for item in result["items"]] == ["100.00", "102.00"]
    assert result["original_amount"] == "202.00"
    assert result["shipping_fee"] == "0.00"
    assert result["final_amount"] == "202.00"


def test_r2_r3_empty_cart_is_rejected() -> None:
    result = checkout_cart([])

    assert result["success"] is False
    assert result["status"] == "结算失败"
    assert result["message"] == "购物车不能为空"
    assert result["original_amount"] == "0.00"
    assert result["shipping_fee"] == "0.00"
    assert result["final_amount"] == "0.00"
    assert result["items"] == []


def test_r2_r3_invalid_unit_price_is_rejected() -> None:
    result = checkout_cart([{"unit_price": 0, "quantity": 1, "stock": 2}])

    assert result["success"] is False
    assert result["message"] == "商品单价非法"
    assert result["items"][0]["subtotal"] is None


def test_r2_r3_invalid_quantity_is_rejected() -> None:
    result = checkout_cart([{"unit_price": 10, "quantity": 1.5, "stock": 2}])

    assert result["success"] is False
    assert result["message"] == "购买数量非法"
    assert result["items"][0]["subtotal"] is None


def test_r2_r3_insufficient_stock_is_rejected() -> None:
    result = checkout_cart([{"unit_price": 10, "quantity": 3, "stock": 2}])

    assert result["success"] is False
    assert result["message"] == "库存不足"
    assert result["items"][0]["subtotal"] is None


def test_r5_shipping_fee_charged_below_200() -> None:
    result = checkout_cart([{"unit_price": 199.99, "quantity": 1, "stock": 1}])

    assert result["success"] is True
    assert result["original_amount"] == "199.99"
    assert result["shipping_fee"] == "10.00"
    assert result["final_amount"] == "209.99"


def test_r5_shipping_fee_free_at_200() -> None:
    result = checkout_cart([{"unit_price": 100, "quantity": 2, "stock": 2}])

    assert result["success"] is True
    assert result["original_amount"] == "200.00"
    assert result["shipping_fee"] == "0.00"
    assert result["final_amount"] == "200.00"


def test_r6_validation_stops_before_amount_calculation() -> None:
    result = checkout_cart(
        [
            {"unit_price": 0, "quantity": 1, "stock": 5},
            {"unit_price": 999, "quantity": 1, "stock": 5},
        ]
    )

    assert result["success"] is False
    assert result["message"] == "商品单价非法"
    assert result["original_amount"] == "0.00"
    assert result["shipping_fee"] == "0.00"
    assert result["final_amount"] == "0.00"
    assert all(item["subtotal"] is None for item in result["items"])


def test_r7_amounts_keep_two_decimal_places_and_never_negative() -> None:
    result = checkout_cart([{"unit_price": "19.999", "quantity": 1, "stock": 1}])

    assert result["success"] is True
    assert result["original_amount"] == "20.00"
    assert result["shipping_fee"] == "10.00"
    assert result["final_amount"] == "30.00"
    assert float(result["final_amount"]) >= 0


def test_r9_failure_preserves_cart_content() -> None:
    result = checkout_cart([{"name": "商品A", "unit_price": 10, "quantity": 3, "stock": 2}])

    assert result["success"] is False
    assert result["items"] == [
        {
            "name": "商品A",
            "unit_price": "10",
            "quantity": 3,
            "stock": 2,
            "subtotal": None,
        }
    ]


def test_r10_backend_returns_success_or_failure_status() -> None:
    success = checkout_cart([{"unit_price": 10, "quantity": 1, "stock": 1}])
    failure = checkout_cart([])

    assert success["status"] == "结算成功"
    assert failure["status"] == "结算失败"


def test_r11_client_final_amount_must_be_ignored() -> None:
    result = checkout_cart(
        [{"unit_price": 100, "quantity": 1, "stock": 2}],
        client_final_amount="0.01",
    )

    assert result["success"] is True
    assert result["original_amount"] == "100.00"
    assert result["shipping_fee"] == "10.00"
    assert result["final_amount"] == "110.00"


def test_r12_checkout_finishes_under_200ms() -> None:
    items = [{"unit_price": 1.23, "quantity": 1, "stock": 1} for _ in range(100)]

    started_at = perf_counter()
    result = checkout_cart(items)
    elapsed_ms = (perf_counter() - started_at) * 1000

    assert result["success"] is True
    assert elapsed_ms < 200


def test_r13_same_input_returns_stable_result() -> None:
    items = [{"unit_price": "39.90", "quantity": "3", "stock": "9"}]

    assert checkout_cart(items) == checkout_cart(items)

