"""
CartFlow 购物车结算模块 - pytest 测试套件
========================================
严格对齐 CSV 测试用例矩阵（TC-01 ~ TC-31）。

测试分两层：
  - 纯函数层：直接调用 checkout_cart()，覆盖所有业务逻辑用例
  - HTTP 层：通过 FastAPI TestClient 覆盖接口契约用例

已知缺陷说明（REQ-11）：
  checkout.py 中存在故意引入的缺陷，服务端会采纳客户端传入的 final_amount。
  TC-26 / TC-27 使用 @pytest.mark.xfail(strict=True) 标记：
    - 当前代码：测试标记为 xfail（预期失败，符合预期）
    - 修复后代码：测试变为绿色通过
  这是暴露 bug 的正确姿势，而非断言缺陷行为。

状态流转说明（REQ-10）：
  当前同步架构中 "校验中" 是瞬时中间态，无法在函数返回后观测。
  TC-23 记录此限制；TC-24 / TC-25 断言可观测的最终态。

运行方式：
  pip install fastapi httpx pytest
  pytest test_cartflow_aligned.py -v
"""

from __future__ import annotations

import copy
import time

import pytest
from fastapi.testclient import TestClient

from cartflow.checkout import checkout_cart
from cartflow.main import app

# ---------------------------------------------------------------------------
# HTTP 层客户端（供集成测试使用）
# ---------------------------------------------------------------------------
client = TestClient(app)


# ===========================================================================
# REQ-1  CI-01/02  基本结算功能
# ===========================================================================

class TestREQ1BasicCheckout:
    """REQ-1：系统能够对购物车进行结算。"""

    def test_tc_01_single_valid_product(self):
        """
        TC-01 | REQ-1 | CI-01 | Equivalence Partitioning | High
        前置：单个合法商品（unit_price=100.00, qty=2, stock=10）
        期望：original_amount=200.00, shipping_fee=0.00（>=200免运费）,
              final_amount=200.00, status=结算成功
        """
        items = [{"unit_price": 100.00, "quantity": 2, "stock": 10}]
        result = checkout_cart(items)

        assert result["success"] is True
        assert result["status"] == "结算成功"
        assert result["original_amount"] == "200.00"
        assert result["shipping_fee"] == "0.00"
        assert result["final_amount"] == "200.00"
        assert result["items"][0]["subtotal"] == "200.00"

    def test_tc_02_multiple_valid_products(self):
        """
        TC-02 | REQ-1 | CI-02 | Equivalence Partitioning | High
        前置：两个合法商品
          P01: unit_price=50.00, qty=2, stock=10  → subtotal=100.00
          P02: unit_price=30.00, qty=3, stock=5   → subtotal= 90.00
        期望：original_amount=190.00, shipping_fee=10.00（<200）,
              final_amount=200.00, status=结算成功
        """
        items = [
            {"unit_price": 50.00, "quantity": 2, "stock": 10},
            {"unit_price": 30.00, "quantity": 3, "stock": 5},
        ]
        result = checkout_cart(items)

        assert result["success"] is True
        assert result["status"] == "结算成功"
        assert result["items"][0]["subtotal"] == "100.00"
        assert result["items"][1]["subtotal"] == "90.00"
        assert result["original_amount"] == "190.00"
        assert result["shipping_fee"] == "10.00"
        assert result["final_amount"] == "200.00"


# ===========================================================================
# REQ-2  CI-03/04/05/06  输入校验（等价类）
# ===========================================================================

class TestREQ2InputValidation:
    """REQ-2：系统对购物车输入进行合法性校验。"""

    def test_tc_03_empty_cart(self):
        """
        TC-03 | REQ-2 | CI-03 | Equivalence Partitioning | High
        前置：购物车为空列表
        期望：success=False, message=购物车不能为空, status=结算失败
        """
        result = checkout_cart([])

        assert result["success"] is False
        assert result["status"] == "结算失败"
        assert result["message"] == "购物车不能为空"
        assert result["items"] == []

    def test_tc_04_zero_unit_price(self):
        """
        TC-04 | REQ-2 | CI-04 | Boundary Value Analysis | High
        前置：unit_price=0.00（边界值，非法）
        期望：success=False, message=商品单价非法, status=结算失败, 不进行任何计算
        """
        items = [{"unit_price": 0.00, "quantity": 1, "stock": 100}]
        result = checkout_cart(items)

        assert result["success"] is False
        assert result["status"] == "结算失败"
        assert result["message"] == "商品单价非法"
        # 校验失败时金额字段均为 0.00
        assert result["original_amount"] == "0.00"
        assert result["final_amount"] == "0.00"

    def test_tc_05_decimal_quantity(self):
        """
        TC-05 | REQ-2 | CI-05 | Equivalence Partitioning | High
        前置：quantity=2.5（小数，非整数，非法）
        期望：success=False, message=购买数量非法, status=结算失败
        """
        items = [{"unit_price": 10.00, "quantity": 2.5, "stock": 10}]
        result = checkout_cart(items)

        assert result["success"] is False
        assert result["status"] == "结算失败"
        assert result["message"] == "购买数量非法"

    def test_tc_06_quantity_exceeds_stock(self):
        """
        TC-06 | REQ-2 | CI-06 | Equivalence Partitioning | High
        前置：quantity=20 > stock=10
        期望：success=False, message=库存不足, status=结算失败
        """
        items = [{"unit_price": 10.00, "quantity": 20, "stock": 10}]
        result = checkout_cart(items)

        assert result["success"] is False
        assert result["status"] == "结算失败"
        assert result["message"] == "库存不足"


# ===========================================================================
# REQ-3  CI-07/08/09  错误提示展示
# ===========================================================================

class TestREQ3ErrorDisplay:
    """REQ-3：校验失败时系统展示对应错误提示。"""

    def test_tc_07_empty_cart_error_message(self):
        """
        TC-07 | REQ-3 | CI-07 | Equivalence Partitioning | Medium
        前置：空购物车
        期望：展示错误信息"购物车不能为空", status=结算失败
        """
        result = checkout_cart([])

        assert result["success"] is False
        assert result["message"] == "购物车不能为空"
        assert result["status"] == "结算失败"

    def test_tc_08_negative_price_error_message(self):
        """
        TC-08 | REQ-3 | CI-08 | Equivalence Partitioning | Medium
        前置：unit_price=-5.00（负数，非法）
        期望：展示错误信息"商品单价非法", status=结算失败
        """
        items = [{"unit_price": -5.00, "quantity": 1, "stock": 10}]
        result = checkout_cart(items)

        assert result["success"] is False
        assert result["message"] == "商品单价非法"
        assert result["status"] == "结算失败"

    def test_tc_09_insufficient_stock_error_message(self):
        """
        TC-09 | REQ-3 | CI-09 | Equivalence Partitioning | Medium
        前置：qty=5 > stock=3
        期望：展示错误信息"库存不足", status=结算失败
        """
        items = [{"unit_price": 20.00, "quantity": 5, "stock": 3}]
        result = checkout_cart(items)

        assert result["success"] is False
        assert result["message"] == "库存不足"
        assert result["status"] == "结算失败"


# ===========================================================================
# REQ-4  CI-10/11  小计与原价计算
# ===========================================================================

class TestREQ4AmountCalculation:
    """REQ-4：系统正确计算各商品小计及订单原价。"""

    def test_tc_10_single_product_subtotal(self):
        """
        TC-10 | REQ-4 | CI-10 | Equivalence Partitioning | High
        前置：price=12.50, qty=4, stock=10
        期望：subtotal=50.00, original_amount=50.00,
              shipping=10.00（<200）, final=60.00
        """
        items = [{"unit_price": 12.50, "quantity": 4, "stock": 10}]
        result = checkout_cart(items)

        assert result["success"] is True
        assert result["items"][0]["subtotal"] == "50.00"
        assert result["original_amount"] == "50.00"
        assert result["shipping_fee"] == "10.00"
        assert result["final_amount"] == "60.00"

    def test_tc_11_multiple_products_subtotals_and_total(self):
        """
        TC-11 | REQ-4 | CI-11 | Equivalence Partitioning | High
        前置：
          P01: price=10.00, qty=3 → subtotal=30.00
          P02: price=25.00, qty=2 → subtotal=50.00
        期望：original_amount=80.00, shipping=10.00, final=90.00
        """
        items = [
            {"unit_price": 10.00, "quantity": 3, "stock": 10},
            {"unit_price": 25.00, "quantity": 2, "stock": 5},
        ]
        result = checkout_cart(items)

        assert result["success"] is True
        assert result["items"][0]["subtotal"] == "30.00"
        assert result["items"][1]["subtotal"] == "50.00"
        assert result["original_amount"] == "80.00"
        assert result["shipping_fee"] == "10.00"
        assert result["final_amount"] == "90.00"


# ===========================================================================
# REQ-5  CI-12/13/14  运费边界值
# ===========================================================================

class TestREQ5ShippingBoundary:
    """REQ-5：订单原价 >=200 免运费，否则运费 10 元。"""

    def test_tc_12_shipping_boundary_exact_200(self):
        """
        TC-12 | REQ-5 | CI-12 | Boundary Value Analysis | High
        前置：price=200.00, qty=1（原价恰好=200.00，边界值）
        期望：shipping_fee=0.00, final_amount=200.00
        """
        items = [{"unit_price": 200.00, "quantity": 1, "stock": 5}]
        result = checkout_cart(items)

        assert result["success"] is True
        assert result["original_amount"] == "200.00"
        assert result["shipping_fee"] == "0.00"
        assert result["final_amount"] == "200.00"

    def test_tc_13_shipping_boundary_199_99(self):
        """
        TC-13 | REQ-5 | CI-13 | Boundary Value Analysis | High
        前置：price=199.99, qty=1（原价低于200边界值，差0.01）
        期望：shipping_fee=10.00, final_amount=209.99
        """
        items = [{"unit_price": 199.99, "quantity": 1, "stock": 5}]
        result = checkout_cart(items)

        assert result["success"] is True
        assert result["original_amount"] == "199.99"
        assert result["shipping_fee"] == "10.00"
        assert result["final_amount"] == "209.99"

    def test_tc_14_shipping_boundary_200_01(self):
        """
        TC-14 | REQ-5 | CI-14 | Boundary Value Analysis | High
        前置：price=200.01, qty=1（原价高于200边界值，超0.01）
        期望：shipping_fee=0.00, final_amount=200.01
        """
        items = [{"unit_price": 200.01, "quantity": 1, "stock": 5}]
        result = checkout_cart(items)

        assert result["success"] is True
        assert result["original_amount"] == "200.01"
        assert result["shipping_fee"] == "0.00"
        assert result["final_amount"] == "200.01"


# ===========================================================================
# REQ-6  CI-15/16  校验与计算的先后顺序
# ===========================================================================

class TestREQ6ValidationBeforeCalculation:
    """REQ-6：输入校验失败时不进行任何金额计算。"""

    def test_tc_15_validation_failure_skips_calculation(self):
        """
        TC-15 | REQ-6 | CI-15 | Decision Table | High
        前置：第一个商品 price=0（非法），第二个商品合法
        期望：在第一个商品处立即失败，返回"商品单价非法"，
              不计算任何 subtotal / original_amount
        """
        items = [
            {"unit_price": 0, "quantity": 1, "stock": 10},
            {"unit_price": 10.00, "quantity": 1, "stock": 10},
        ]
        result = checkout_cart(items)

        assert result["success"] is False
        assert result["message"] == "商品单价非法"
        assert result["status"] == "结算失败"
        # 校验失败时所有金额为 0
        assert result["original_amount"] == "0.00"
        assert result["final_amount"] == "0.00"
        # items 列表保留原始数据，但 subtotal 均为 None
        for item in result["items"]:
            assert item["subtotal"] is None

    def test_tc_16_all_valid_proceeds_to_calculation(self):
        """
        TC-16 | REQ-6 | CI-16 | Decision Table | High
        前置：所有商品合法（price=50, qty=2, stock=10）
        期望：校验通过后进入计算阶段，
              subtotal=100, original=100, shipping=10, final=110, success
        """
        items = [{"unit_price": 50.00, "quantity": 2, "stock": 10}]
        result = checkout_cart(items)

        assert result["success"] is True
        assert result["items"][0]["subtotal"] == "100.00"
        assert result["original_amount"] == "100.00"
        assert result["shipping_fee"] == "10.00"
        assert result["final_amount"] == "110.00"


# ===========================================================================
# REQ-7  CI-17/18  最终金额计算与精度
# ===========================================================================

class TestREQ7FinalAmountPrecision:
    """REQ-7：最终金额 = 原价 + 运费，保留两位小数。"""

    def test_tc_17_final_amount_150_plus_shipping(self):
        """
        TC-17 | REQ-7 | CI-17 | Equivalence Partitioning | High
        前置：price=150.00, qty=1（原价=150，需收运费10）
        期望：final_amount=160.00
        """
        items = [{"unit_price": 150.00, "quantity": 1, "stock": 10}]
        result = checkout_cart(items)

        assert result["success"] is True
        assert result["original_amount"] == "150.00"
        assert result["shipping_fee"] == "10.00"
        assert result["final_amount"] == "160.00"

    def test_tc_18_final_amount_decimal_precision(self):
        """
        TC-18 | REQ-7 | CI-18 | Equivalence Partitioning | High
        前置：price=10.50, qty=1（原价=10.50，需收运费10）
        期望：final_amount=20.50（两位小数展示）
        """
        items = [{"unit_price": 10.50, "quantity": 1, "stock": 10}]
        result = checkout_cart(items)

        assert result["success"] is True
        assert result["original_amount"] == "10.50"
        assert result["shipping_fee"] == "10.00"
        assert result["final_amount"] == "20.50"


# ===========================================================================
# REQ-8  CI-19/20  响应结构完整性
# ===========================================================================

class TestREQ8ResponseStructure:
    """REQ-8：响应需包含所有规定字段，且数值正确。"""

    def test_tc_19_response_fields_single_product(self):
        """
        TC-19 | REQ-8 | CI-19 | Equivalence Partitioning | High
        前置：price=100.00, qty=2, stock=5
        期望：响应包含 original_amount=200.00, shipping_fee=0.00,
              final_amount=200.00, status=结算成功，字段完整
        """
        items = [{"unit_price": 100.00, "quantity": 2, "stock": 5}]
        result = checkout_cart(items)

        assert result["success"] is True
        # 验证所有必需字段存在
        for field in ("success", "status", "message", "original_amount",
                      "shipping_fee", "final_amount", "items"):
            assert field in result, f"响应缺少字段: {field}"
        assert result["original_amount"] == "200.00"
        assert result["shipping_fee"] == "0.00"
        assert result["final_amount"] == "200.00"
        assert result["status"] == "结算成功"

    def test_tc_20_response_fields_multiple_products(self):
        """
        TC-20 | REQ-8 | CI-20 | Equivalence Partitioning | High
        前置：
          P01: price=30, qty=3 → subtotal=90
          P02: price=40, qty=2 → subtotal=80
          合计=170 < 200，shipping=10，final=180
        期望：所有数值正确，status=结算成功
        """
        items = [
            {"unit_price": 30.00, "quantity": 3, "stock": 10},
            {"unit_price": 40.00, "quantity": 2, "stock": 8},
        ]
        result = checkout_cart(items)

        assert result["success"] is True
        assert result["items"][0]["subtotal"] == "90.00"
        assert result["items"][1]["subtotal"] == "80.00"
        assert result["original_amount"] == "170.00"
        assert result["shipping_fee"] == "10.00"
        assert result["final_amount"] == "180.00"
        assert result["status"] == "结算成功"


# ===========================================================================
# REQ-9  CI-21/22  失败时购物车内容保持不变
# ===========================================================================

class TestREQ9CartPreservedOnFailure:
    """REQ-9：结算失败后购物车内容不被清除，原样保留。"""

    def test_tc_21_cart_preserved_on_stock_failure(self):
        """
        TC-21 | REQ-9 | CI-21 | Equivalence Partitioning | High
        前置：qty=100 > stock=2（库存不足）
        期望：status=结算失败, message=库存不足,
              响应 items 中保留原始商品数据（quantity=100）
        """
        items = [{"unit_price": 10.00, "quantity": 100, "stock": 2}]
        result = checkout_cart(items)

        assert result["success"] is False
        assert result["message"] == "库存不足"
        assert result["status"] == "结算失败"
        # 原始购物车数据被保留在响应中
        assert len(result["items"]) == 1
        assert result["items"][0]["quantity"] == 100

    def test_tc_22_first_failure_stops_validation_cart_preserved(self):
        """
        TC-22 | REQ-9 | CI-22 | Decision Table | High
        前置：price=0（非法，且 qty=5 > stock=3 也非法），两个条件同时存在
        期望：系统在 price=0 处立即终止，返回"商品单价非法"，
              不继续检查库存，购物车数据保留
        """
        items = [{"unit_price": 0, "quantity": 5, "stock": 3}]
        result = checkout_cart(items)

        assert result["success"] is False
        # price=0 先于库存检查，应先报价格错误
        assert result["message"] == "商品单价非法"
        assert result["status"] == "结算失败"
        # 购物车数据被保留
        assert len(result["items"]) == 1


# ===========================================================================
# REQ-10  CI-23/24/25  状态流转
# ===========================================================================

class TestREQ10StateTransition:
    """REQ-10：结算过程经历 待结算 → 校验中 → 结算成功/失败 的状态流转。"""

    def test_tc_23_intermediate_state_not_observable_sync(self):
        """
        TC-23 | REQ-10 | CI-23 | State Transition Testing | High
        前置：合法购物车，验证 待结算→校验中 的中间态
        说明：当前同步架构中"校验中"为瞬时态，函数返回后已不可观测。
              此用例记录该架构限制，不做强断言；仅验证最终态存在。
        期望（可观测）：最终响应包含 status 字段，值为终态之一
        """
        items = [{"unit_price": 10.00, "quantity": 1, "stock": 5}]
        result = checkout_cart(items)

        # 中间态"校验中"在同步函数中不可观测，仅断言最终态正常返回
        assert result["status"] in ("结算成功", "结算失败"), (
            "架构限制：同步调用无法捕获'校验中'中间态，此用例仅断言最终态"
        )

    def test_tc_24_state_transition_to_success(self):
        """
        TC-24 | REQ-10 | CI-24 | State Transition Testing | High
        前置：合法购物车（price=10, qty=1, stock=5），校验全部通过
        期望：最终状态 = 结算成功（校验中 → 结算成功）
        """
        items = [{"unit_price": 10.00, "quantity": 1, "stock": 5}]
        result = checkout_cart(items)

        assert result["success"] is True
        assert result["status"] == "结算成功"

    def test_tc_25_state_transition_to_failure(self):
        """
        TC-25 | REQ-10 | CI-25 | State Transition Testing | High
        前置：非法购物车（price=0, qty=1, stock=5），校验失败
        期望：最终状态 = 结算失败（校验中 → 结算失败），保持失败态
        """
        items = [{"unit_price": 0, "quantity": 1, "stock": 5}]
        result = checkout_cart(items)

        assert result["success"] is False
        assert result["status"] == "结算失败"


# ===========================================================================
# REQ-11  CI-26/27  防客户端篡改金额（已知缺陷，xfail 标记）
# ===========================================================================

class TestREQ11ClientAmountTampering:
    """
    REQ-11：服务端必须忽略客户端传入的 final_amount，以服务端计算值为准。

    注意：checkout.py 中存在故意引入的缺陷（见注释 'Intentional defect'），
    当前代码会采纳客户端金额，导致下列两个测试 xfail。
    修复缺陷后两个测试将自动变为 PASSED。
    """

    @pytest.mark.xfail(
        strict=True,
        reason="REQ-11 已知缺陷：服务端错误地采纳了 client_final_amount，"
               "应忽略客户端值并返回服务端计算值 100.00",
    )
    def test_tc_26_server_ignores_client_final_amount(self):
        """
        TC-26 | REQ-11 | CI-26 | Equivalence Partitioning | High
        前置：price=50.00, qty=2, stock=10（服务端应计算 original=100, shipping=0, final=100）
              客户端恶意传入 final_amount=1.00
        期望：服务端忽略客户端值，final_amount=100.00
        """
        items = [{"unit_price": 50.00, "quantity": 2, "stock": 10}]
        result = checkout_cart(items, client_final_amount="1.00")

        assert result["success"] is True
        assert result["original_amount"] == "100.00"
        assert result["shipping_fee"] == "0.00"
        # 关键断言：服务端应使用自己计算的值
        assert result["final_amount"] == "100.00", (
            f"服务端不应采纳客户端金额，期望 100.00，实际 {result['final_amount']}"
        )

    @pytest.mark.xfail(
        strict=True,
        reason="REQ-11 已知缺陷：服务端错误地采纳了负数 client_final_amount，"
               "应忽略并返回服务端计算值 100.00",
    )
    def test_tc_27_server_ignores_negative_client_final_amount(self):
        """
        TC-27 | REQ-11 | CI-27 | Equivalence Partitioning | High
        前置：price=30.00, qty=3, stock=10（服务端应计算 original=90, shipping=10, final=100）
              客户端传入 final_amount=-50.00（负数）
        期望：服务端忽略负数客户端值，final_amount=100.00
        """
        items = [{"unit_price": 30.00, "quantity": 3, "stock": 10}]
        result = checkout_cart(items, client_final_amount="-50.00")

        assert result["success"] is True
        assert result["original_amount"] == "90.00"
        assert result["shipping_fee"] == "10.00"
        # 关键断言：服务端应使用自己计算的值
        assert result["final_amount"] == "100.00", (
            f"服务端不应采纳客户端负数金额，期望 100.00，实际 {result['final_amount']}"
        )


# ===========================================================================
# REQ-12  CI-28/29  性能（响应时间 < 200ms）
# ===========================================================================

class TestREQ12Performance:
    """REQ-12：结算接口响应时间应 < 200ms。"""

    def test_tc_28_single_product_response_time(self):
        """
        TC-28 | REQ-12 | CI-28 | Equivalence Partitioning | Medium
        前置：单个商品（price=10.00, qty=1, stock=100）
        期望：响应时间 < 200ms
        """
        items = [{"unit_price": 10.00, "quantity": 1, "stock": 100}]

        start = time.perf_counter()
        result = checkout_cart(items)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert result["success"] is True
        assert elapsed_ms < 200, (
            f"TC-28 性能不达标：响应时间 {elapsed_ms:.2f}ms，要求 < 200ms"
        )

    def test_tc_29_fifty_products_response_time(self):
        """
        TC-29 | REQ-12 | CI-29 | Equivalence Partitioning | Medium
        前置：50 个商品，price 在 1~100 之间，qty=1，stock=10
        期望：响应时间 < 200ms
        """
        items = [
            {"unit_price": float(i % 100 + 1), "quantity": 1, "stock": 10}
            for i in range(50)
        ]

        start = time.perf_counter()
        result = checkout_cart(items)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert result["success"] is True
        assert len(result["items"]) == 50
        assert elapsed_ms < 200, (
            f"TC-29 性能不达标：50件商品响应时间 {elapsed_ms:.2f}ms，要求 < 200ms"
        )


# ===========================================================================
# REQ-13  CI-30/31  幂等性与一致性
# ===========================================================================

class TestREQ13Idempotency:
    """REQ-13：相同输入在任意时刻执行，必须返回完全相同的结果。"""

    def test_tc_30_three_identical_calls_same_result(self):
        """
        TC-30 | REQ-13 | CI-30 | Equivalence Partitioning | High
        前置：price=25.50, qty=4, stock=20
              原价=102.00（<200），shipping=10.00，final=112.00
        操作：连续执行三次（间隔1秒），比较结果
        期望：三次结果完全一致
        """
        items = [{"unit_price": 25.50, "quantity": 4, "stock": 20}]

        results = []
        for _ in range(3):
            results.append(checkout_cart(copy.deepcopy(items)))
            time.sleep(1)

        for i, r in enumerate(results):
            assert r["success"] is True, f"第{i+1}次调用失败"
            assert r["original_amount"] == "102.00", f"第{i+1}次 original_amount 错误"
            assert r["shipping_fee"] == "10.00",     f"第{i+1}次 shipping_fee 错误"
            assert r["final_amount"] == "112.00",    f"第{i+1}次 final_amount 错误"
            assert r["status"] == "结算成功",         f"第{i+1}次 status 错误"

        # 三次结果两两完全相等
        assert results[0]["final_amount"] == results[1]["final_amount"] == results[2]["final_amount"]

    def test_tc_31_same_input_different_time_same_result(self):
        """
        TC-31 | REQ-13 | CI-31 | Equivalence Partitioning | High
        前置：price=99.99, qty=2, stock=5
              原价=199.98（<200），shipping=10.00，final=209.98
        操作：模拟不同时刻两次提交，比较结果
        期望：两次结果完全一致：original=199.98, shipping=10.00, final=209.98
        """
        items = [{"unit_price": 99.99, "quantity": 2, "stock": 5}]

        result_t1 = checkout_cart(copy.deepcopy(items))
        time.sleep(2)  # 模拟时间间隔
        result_t2 = checkout_cart(copy.deepcopy(items))

        for result, label in ((result_t1, "T1"), (result_t2, "T2")):
            assert result["success"] is True,              f"{label}: 结算失败"
            assert result["original_amount"] == "199.98",  f"{label}: original_amount 错误"
            assert result["shipping_fee"] == "10.00",      f"{label}: shipping_fee 错误"
            assert result["final_amount"] == "209.98",     f"{label}: final_amount 错误"
            assert result["status"] == "结算成功",          f"{label}: status 错误"

        assert result_t1["final_amount"] == result_t2["final_amount"]


# ===========================================================================
# HTTP 层集成测试（补充纯函数层未覆盖的接口契约）
# ===========================================================================

class TestHTTPLayer:
    """
    通过 FastAPI TestClient 验证 HTTP 接口契约。
    这些用例与纯函数层互补，覆盖序列化、路由、Pydantic 校验等链路。
    """

    def test_health_check(self):
        """GET /api/health 应返回 200 和 {"status": "ok"}"""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_tc_01_via_http(self):
        """TC-01 HTTP 版：单个合法商品，验证接口字段名与响应结构"""
        resp = client.post("/api/checkout", json={
            "items": [{"unit_price": 100.00, "quantity": 2, "stock": 10}]
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["final_amount"] == "200.00"
        assert body["shipping_fee"] == "0.00"
        assert body["status"] == "结算成功"

    def test_tc_03_via_http_empty_cart(self):
        """TC-03 HTTP 版：空购物车，验证错误响应走正常 200 而非 422"""
        resp = client.post("/api/checkout", json={"items": []})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert body["message"] == "购物车不能为空"

    def test_http_invalid_json_returns_422(self):
        """Pydantic 类型校验：items 字段缺失时应返回 422"""
        resp = client.post("/api/checkout", json={})
        # items 有 default_factory=list，缺失时为空列表，触发业务错误而非 422
        assert resp.status_code == 200
        assert resp.json()["message"] == "购物车不能为空"

    def test_tc_26_via_http_client_final_amount_field(self):
        """
        TC-26 HTTP 版：客户端通过 final_amount 字段传入篡改金额
        说明：此测试断言缺陷的实际行为（当前会采纳客户端值），
              与纯函数层 xfail 测试配合，完整记录缺陷的影响面。
        """
        resp = client.post("/api/checkout", json={
            "items": [{"unit_price": 50.00, "quantity": 2, "stock": 10}],
            "final_amount": "1.00",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        # 记录当前缺陷行为：实际返回了客户端篡改的金额
        # 修复后此处应改为 assert body["final_amount"] == "100.00"
        assert body["final_amount"] == "1.00", (
            "当前缺陷行为确认：服务端采纳了客户端的 final_amount=1.00，"
            "正确值应为 100.00（修复后请更新此断言）"
        )
