<script setup>
import { computed, ref } from 'vue'

const STATUS_PENDING = '待结算'
const STATUS_VALIDATING = '校验中'
const STATUS_FAILED = '结算失败'

const PRODUCTS = [
  {
    id: 'band',
    name: '智能手环',
    category: '数码配件',
    unit_price: 129,
    stock: 18,
    accent: 'mint',
  },
  {
    id: 'earbuds',
    name: '蓝牙耳机',
    category: '影音设备',
    unit_price: 199,
    stock: 12,
    accent: 'blue',
  },
  {
    id: 'keyboard',
    name: '机械键盘',
    category: '办公外设',
    unit_price: 369,
    stock: 8,
    accent: 'violet',
  },
  {
    id: 'power-bank',
    name: '便携充电宝',
    category: '出行补能',
    unit_price: 89.9,
    stock: 25,
    accent: 'amber',
  },
  {
    id: 'cup',
    name: '保温杯',
    category: '生活日用',
    unit_price: 59.9,
    stock: 30,
    accent: 'rose',
  },
  {
    id: 'mouse',
    name: '无线鼠标',
    category: '办公外设',
    unit_price: 79,
    stock: 16,
    accent: 'cyan',
  },
  {
    id: 'backpack',
    name: '双肩背包',
    category: '通勤收纳',
    unit_price: 149.5,
    stock: 10,
    accent: 'slate',
  },
]

const products = ref(PRODUCTS.map((product) => ({ ...product, quantity: 0 })))
const status = ref(STATUS_PENDING)
const result = ref(null)
const submitting = ref(false)

const selectedProducts = computed(() =>
  products.value
    .map((product) => {
      const quantity = normalizeQuantity(product.quantity, product.stock)
      return {
        ...product,
        quantity,
        subtotal: formatMoney(product.unit_price * quantity),
      }
    })
    .filter((product) => product.quantity > 0),
)

const selectedUnits = computed(() =>
  selectedProducts.value.reduce((total, product) => total + Number(product.quantity), 0),
)

const liveOriginalAmount = computed(() =>
  formatMoney(selectedProducts.value.reduce((total, product) => total + Number(product.subtotal), 0)),
)

const liveShippingFee = computed(() =>
  selectedProducts.value.length === 0 || Number(liveOriginalAmount.value) >= 200 ? '0.00' : '10.00',
)

const liveFinalAmount = computed(() =>
  formatMoney(Number(liveOriginalAmount.value) + Number(liveShippingFee.value)),
)

const isFailure = computed(() => result.value && result.value.success === false)
const isSuccess = computed(() => result.value && result.value.success === true)
const displayItems = computed(() => (result.value?.success ? result.value.items : selectedProducts.value))

function formatMoney(value) {
  return Number(value).toFixed(2)
}

function normalizeQuantity(value, stock) {
  const quantity = Number(value)

  if (!Number.isFinite(quantity)) {
    return 0
  }

  return Math.min(stock, Math.max(0, Math.trunc(quantity)))
}

function resetResult() {
  result.value = null
  status.value = STATUS_PENDING
}

function clearCart() {
  products.value = products.value.map((product) => ({ ...product, quantity: 0 }))
  resetResult()
}

function updateQuantity(product, nextValue) {
  product.quantity = normalizeQuantity(nextValue, product.stock)
  resetResult()
}

function handleQuantityInput(product) {
  if (product.quantity === '') {
    resetResult()
    return
  }

  updateQuantity(product, product.quantity)
}

function decreaseQuantity(product) {
  updateQuantity(product, Number(product.quantity) - 1)
}

function increaseQuantity(product) {
  updateQuantity(product, Number(product.quantity) + 1)
}

async function submitCheckout() {
  status.value = STATUS_VALIDATING
  result.value = null
  submitting.value = true

  try {
    const response = await fetch('/api/checkout', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        items: selectedProducts.value.map(({ name, unit_price, quantity, stock }) => ({
          name,
          unit_price,
          quantity: Number(quantity),
          stock,
        })),
      }),
    })

    const data = await response.json()
    result.value = data
    status.value = data.status || STATUS_FAILED
  } catch (error) {
    result.value = {
      success: false,
      status: STATUS_FAILED,
      message: '服务暂不可用',
      original_amount: '0.00',
      shipping_fee: '0.00',
      final_amount: '0.00',
      items: selectedProducts.value.map((product) => ({
        name: product.name,
        unit_price: formatMoney(product.unit_price),
        quantity: product.quantity,
        stock: product.stock,
        subtotal: null,
      })),
    }
    status.value = STATUS_FAILED
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main class="app-shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">CartFlow</p>
        <h1>购物车结算</h1>
      </div>
      <div class="status-pill" :class="{ success: isSuccess, failure: isFailure }">
        <span></span>
        {{ status }}
      </div>
    </header>

    <div class="checkout-layout">
      <section class="catalog-section" aria-labelledby="catalog-title">
        <div class="section-header">
          <div>
            <p class="section-kicker">7 件可选商品</p>
            <h2 id="catalog-title">商品明细</h2>
          </div>
          <div class="selection-counter">
            <strong>{{ selectedUnits }}</strong>
            <span>件已选</span>
          </div>
          <button
            class="clear-button"
            type="button"
            :disabled="selectedUnits === 0"
            @click="clearCart"
          >
            清空购物车
          </button>
        </div>

        <div class="product-list">
          <article
            v-for="product in products"
            :key="product.id"
            class="product-row"
            :class="product.accent"
          >
            <div class="product-mark" aria-hidden="true">{{ product.name.slice(0, 1) }}</div>
            <div class="product-main">
              <div>
                <h3>{{ product.name }}</h3>
                <p>{{ product.category }}</p>
              </div>
              <div class="product-meta">
                <span>￥{{ formatMoney(product.unit_price) }}</span>
                <span>库存 {{ product.stock }}</span>
              </div>
            </div>
            <label class="quantity-select">
              <span>购买量</span>
              <div class="quantity-stepper">
                <button
                  aria-label="减少购买量"
                  class="qty-button"
                  type="button"
                  :disabled="normalizeQuantity(product.quantity, product.stock) <= 0"
                  @click="decreaseQuantity(product)"
                >
                  -
                </button>
                <input
                  v-model="product.quantity"
                  aria-label="购买量"
                  inputmode="numeric"
                  min="0"
                  :max="product.stock"
                  step="1"
                  type="number"
                  @input="handleQuantityInput(product)"
                  @blur="updateQuantity(product, product.quantity)"
                />
                <button
                  aria-label="增加购买量"
                  class="qty-button"
                  type="button"
                  :disabled="normalizeQuantity(product.quantity, product.stock) >= product.stock"
                  @click="increaseQuantity(product)"
                >
                  +
                </button>
              </div>
            </label>
          </article>
        </div>
      </section>

      <aside class="result-section" aria-labelledby="result-title">
        <div class="section-header compact">
          <div>
            <p class="section-kicker">Checkout</p>
            <h2 id="result-title">结算结果</h2>
          </div>
          <p v-if="result" class="result-message" :class="{ success: isSuccess, failure: isFailure }">
            {{ result.message }}
          </p>
        </div>

        <div class="amount-board">
          <div class="amount-line">
            <span>订单原价</span>
            <strong>￥{{ liveOriginalAmount }}</strong>
          </div>
          <div class="amount-line">
            <span>运费</span>
            <strong>￥{{ liveShippingFee }}</strong>
          </div>
          <div class="amount-line total">
            <span>最终金额</span>
            <strong>￥{{ liveFinalAmount }}</strong>
          </div>
        </div>

        <button class="primary-button" type="button" :disabled="submitting" @click="submitCheckout">
          {{ submitting ? '校验中' : '提交结算' }}
        </button>

        <div class="selected-list">
          <div v-if="selectedProducts.length === 0" class="empty-selection">尚未选择商品</div>
          <template v-else>
            <div
              v-for="item in displayItems"
              :key="item.name"
              class="selected-row"
            >
              <div>
                <span>{{ item.name }}</span>
                <small>￥{{ formatMoney(item.unit_price) }} x {{ item.quantity }}</small>
              </div>
              <strong>￥{{ item.subtotal }}</strong>
            </div>
          </template>
        </div>
      </aside>
    </div>
  </main>
</template>
