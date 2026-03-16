<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold text-gray-900">Positions</h1>
      <div class="flex items-center space-x-4">
        <select v-model="statusFilter" class="input w-40">
          <option value="">All Positions</option>
          <option value="open">Open Only</option>
          <option value="closed">Closed</option>
        </select>
        <select v-model="strategyFilter" class="input w-40">
          <option value="">All Strategies</option>
          <option v-for="s in strategyList" :key="s.name" :value="s.name">
            {{ s.name }}
          </option>
        </select>
      </div>
    </div>

    <!-- Summary Cards -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <div class="card">
        <div class="text-sm text-gray-500">Open Positions</div>
        <div class="text-2xl font-semibold">{{ openCount }}</div>
      </div>
      <div class="card">
        <div class="text-sm text-gray-500">Total Exposure</div>
        <div class="text-2xl font-semibold">${{ totalExposure.toFixed(2) }}</div>
      </div>
      <div class="card">
        <div class="text-sm text-gray-500">Unrealized P&L</div>
        <div
          class="text-2xl font-semibold"
          :class="unrealizedPnl >= 0 ? 'text-success-600' : 'text-danger-600'"
        >
          {{ unrealizedPnl >= 0 ? '+' : '' }}${{ unrealizedPnl.toFixed(2) }}
        </div>
      </div>
      <div class="card">
        <div class="text-sm text-gray-500">Realized P&L</div>
        <div
          class="text-2xl font-semibold"
          :class="realizedPnl >= 0 ? 'text-success-600' : 'text-danger-600'"
        >
          {{ realizedPnl >= 0 ? '+' : '' }}${{ realizedPnl.toFixed(2) }}
        </div>
      </div>
    </div>

    <!-- Positions Table -->
    <div class="card">
      <PositionTable
        :positions="filteredPositions"
        :loading="loading.positions"
        show-actions
        @close="handleClose"
      />
    </div>

    <!-- Orders Section -->
    <div class="card">
      <h2 class="text-lg font-semibold text-gray-900 mb-4">Open Orders</h2>
      <div v-if="loading.orders" class="text-gray-500">Loading...</div>
      <div v-else-if="openOrders.length === 0" class="text-gray-500">
        No open orders
      </div>
      <table v-else class="min-w-full">
        <thead>
          <tr class="text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
            <th class="pb-3">Market</th>
            <th class="pb-3">Side</th>
            <th class="pb-3">Price</th>
            <th class="pb-3">Size</th>
            <th class="pb-3">Status</th>
            <th class="pb-3">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          <tr v-for="order in openOrders" :key="order.id">
            <td class="py-3 font-medium">{{ order.market_id?.slice(0, 8) }}...</td>
            <td class="py-3">
              <span
                class="badge"
                :class="order.side === 'BUY' ? 'badge-success' : 'badge-danger'"
              >
                {{ order.side }}
              </span>
            </td>
            <td class="py-3">${{ order.price?.toFixed(3) }}</td>
            <td class="py-3">{{ order.size?.toFixed(2) }}</td>
            <td class="py-3">
              <span class="badge badge-primary">{{ order.status }}</span>
            </td>
            <td class="py-3">
              <button
                @click="handleCancelOrder(order.id)"
                class="text-danger-600 hover:text-danger-700 text-sm"
              >
                Cancel
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useMainStore } from '../stores/main'
import PositionTable from '../components/PositionTable.vue'

const mainStore = useMainStore()
const { positionList, orderList, strategyList, loading, openOrders } = storeToRefs(mainStore)

const statusFilter = ref('')
const strategyFilter = ref('')

const filteredPositions = computed(() => {
  let positions = positionList.value

  if (statusFilter.value === 'open') {
    positions = positions.filter((p) => !p.closed_at)
  } else if (statusFilter.value === 'closed') {
    positions = positions.filter((p) => p.closed_at)
  }

  if (strategyFilter.value) {
    positions = positions.filter((p) => p.strategy === strategyFilter.value)
  }

  return positions
})

const openCount = computed(() =>
  positionList.value.filter((p) => !p.closed_at).length
)

const totalExposure = computed(() =>
  positionList.value
    .filter((p) => !p.closed_at)
    .reduce((sum, p) => sum + (p.size || 0) * (p.entry_price || 0), 0)
)

const unrealizedPnl = computed(() =>
  positionList.value
    .filter((p) => !p.closed_at)
    .reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0)
)

const realizedPnl = computed(() =>
  positionList.value
    .filter((p) => p.closed_at)
    .reduce((sum, p) => sum + (p.pnl || 0), 0)
)

async function handleClose(positionId) {
  if (confirm('Are you sure you want to close this position?')) {
    try {
      await mainStore.closePosition(positionId)
    } catch (e) {
      console.error('Failed to close position:', e)
    }
  }
}

async function handleCancelOrder(orderId) {
  if (confirm('Are you sure you want to cancel this order?')) {
    try {
      await mainStore.cancelOrder(orderId)
    } catch (e) {
      console.error('Failed to cancel order:', e)
    }
  }
}

onMounted(() => {
  mainStore.fetchPositions()
  mainStore.fetchOrders()
  mainStore.fetchStrategies()
})
</script>
