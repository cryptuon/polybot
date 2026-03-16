<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Shadow Trading</h1>
        <p class="text-sm text-gray-500 mt-1">
          Paper trading performance for strategies running in shadow mode
        </p>
      </div>
      <button
        @click="resetAll"
        class="btn btn-danger text-sm"
        :disabled="loading"
      >
        Reset All Data
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="text-gray-500">Loading shadow trading data...</div>

    <!-- Summary Cards -->
    <div v-else class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <div class="card text-center">
        <div class="text-sm text-gray-500">Total P&L</div>
        <div
          class="text-2xl font-bold"
          :class="summary.total_pnl >= 0 ? 'text-success-600' : 'text-danger-600'"
        >
          {{ formatCurrency(summary.total_pnl) }}
        </div>
        <div class="text-xs text-gray-400 mt-1">
          Realized: {{ formatCurrency(summary.realized_pnl) }}
        </div>
      </div>

      <div class="card text-center">
        <div class="text-sm text-gray-500">Win Rate</div>
        <div class="text-2xl font-bold text-gray-900">
          {{ formatPercent(summary.win_rate) }}
        </div>
        <div class="text-xs text-gray-400 mt-1">
          {{ summary.total_trades }} total trades
        </div>
      </div>

      <div class="card text-center">
        <div class="text-sm text-gray-500">Open Positions</div>
        <div class="text-2xl font-bold text-gray-900">
          {{ summary.open_positions || 0 }}
        </div>
        <div class="text-xs text-gray-400 mt-1">
          Unrealized: {{ formatCurrency(summary.unrealized_pnl) }}
        </div>
      </div>

      <div class="card text-center">
        <div class="text-sm text-gray-500">Shadow Mode</div>
        <div class="text-2xl font-bold text-gray-900">
          {{ summary.strategies_in_shadow_mode || 0 }}
        </div>
        <div class="text-xs text-gray-400 mt-1">
          {{ (summary.shadow_mode_strategies || []).join(', ') || 'None configured' }}
        </div>
      </div>
    </div>

    <!-- Shadow Mode Strategies Info -->
    <div v-if="summary.shadow_mode_strategies?.length > 0" class="card bg-warning-50 border border-warning-200">
      <div class="flex items-start space-x-3">
        <div class="flex-shrink-0">
          <svg class="h-5 w-5 text-warning-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <div>
          <h3 class="text-sm font-medium text-warning-800">Strategies in Shadow Mode</h3>
          <p class="text-sm text-warning-700 mt-1">
            The following strategies are running in shadow (paper trading) mode:
            <strong>{{ summary.shadow_mode_strategies.join(', ') }}</strong>
          </p>
          <p class="text-xs text-warning-600 mt-2">
            Trades will be simulated but not executed. Data appears here once strategies generate signals.
          </p>
        </div>
      </div>
    </div>

    <!-- Strategy Performance -->
    <div v-if="performance.strategies && Object.keys(performance.strategies).length > 0" class="card">
      <h2 class="text-lg font-semibold text-gray-900 mb-4">Strategy Performance</h2>
      <div class="overflow-x-auto">
        <table class="min-w-full">
          <thead>
            <tr class="border-b border-gray-200">
              <th class="text-left py-2 text-sm font-medium text-gray-500">Strategy</th>
              <th class="text-right py-2 text-sm font-medium text-gray-500">Trades</th>
              <th class="text-right py-2 text-sm font-medium text-gray-500">Win Rate</th>
              <th class="text-right py-2 text-sm font-medium text-gray-500">Realized P&L</th>
              <th class="text-right py-2 text-sm font-medium text-gray-500">Unrealized</th>
              <th class="text-right py-2 text-sm font-medium text-gray-500">Total P&L</th>
              <th class="text-right py-2 text-sm font-medium text-gray-500">Open</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(stats, name) in performance.strategies"
              :key="name"
              class="border-b border-gray-100 hover:bg-gray-50"
            >
              <td class="py-3 font-medium capitalize">{{ name }}</td>
              <td class="py-3 text-right">{{ stats.total_trades }}</td>
              <td class="py-3 text-right">{{ formatPercent(stats.win_rate) }}</td>
              <td
                class="py-3 text-right"
                :class="stats.total_realized_pnl >= 0 ? 'text-success-600' : 'text-danger-600'"
              >
                {{ formatCurrency(stats.total_realized_pnl) }}
              </td>
              <td
                class="py-3 text-right"
                :class="stats.total_unrealized_pnl >= 0 ? 'text-success-600' : 'text-danger-600'"
              >
                {{ formatCurrency(stats.total_unrealized_pnl) }}
              </td>
              <td
                class="py-3 text-right font-semibold"
                :class="stats.total_pnl >= 0 ? 'text-success-600' : 'text-danger-600'"
              >
                {{ formatCurrency(stats.total_pnl) }}
              </td>
              <td class="py-3 text-right">{{ stats.open_positions }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Best/Worst Performing -->
      <div v-if="performance.best_performing?.strategy" class="mt-4 grid grid-cols-2 gap-4">
        <div class="p-3 bg-success-50 rounded-lg">
          <div class="text-xs text-success-600 uppercase tracking-wider">Best Performing</div>
          <div class="font-semibold text-success-800 capitalize">
            {{ performance.best_performing.strategy }}
          </div>
          <div class="text-sm text-success-700">
            {{ formatCurrency(performance.best_performing.pnl) }}
          </div>
        </div>
        <div class="p-3 bg-danger-50 rounded-lg" v-if="performance.worst_performing?.strategy">
          <div class="text-xs text-danger-600 uppercase tracking-wider">Worst Performing</div>
          <div class="font-semibold text-danger-800 capitalize">
            {{ performance.worst_performing.strategy }}
          </div>
          <div class="text-sm text-danger-700">
            {{ formatCurrency(performance.worst_performing.pnl) }}
          </div>
        </div>
      </div>
    </div>

    <!-- Open Positions -->
    <div v-if="positions.length > 0" class="card">
      <h2 class="text-lg font-semibold text-gray-900 mb-4">Open Shadow Positions</h2>
      <div class="overflow-x-auto">
        <table class="min-w-full">
          <thead>
            <tr class="border-b border-gray-200">
              <th class="text-left py-2 text-sm font-medium text-gray-500">Strategy</th>
              <th class="text-left py-2 text-sm font-medium text-gray-500">Market</th>
              <th class="text-left py-2 text-sm font-medium text-gray-500">Side</th>
              <th class="text-right py-2 text-sm font-medium text-gray-500">Size</th>
              <th class="text-right py-2 text-sm font-medium text-gray-500">Entry</th>
              <th class="text-right py-2 text-sm font-medium text-gray-500">Current</th>
              <th class="text-right py-2 text-sm font-medium text-gray-500">Unrealized P&L</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="pos in positions"
              :key="pos.id"
              class="border-b border-gray-100 hover:bg-gray-50"
            >
              <td class="py-3 capitalize">{{ pos.strategy }}</td>
              <td class="py-3 text-gray-600 text-sm font-mono">
                {{ pos.market_id?.substring(0, 8) }}...
              </td>
              <td class="py-3">
                <span
                  class="px-2 py-0.5 text-xs font-medium rounded"
                  :class="pos.side === 'BUY' ? 'bg-success-100 text-success-700' : 'bg-danger-100 text-danger-700'"
                >
                  {{ pos.side }}
                </span>
              </td>
              <td class="py-3 text-right">{{ pos.size?.toFixed(2) }}</td>
              <td class="py-3 text-right">${{ pos.entry_price?.toFixed(4) }}</td>
              <td class="py-3 text-right">${{ pos.current_price?.toFixed(4) }}</td>
              <td
                class="py-3 text-right font-semibold"
                :class="pos.unrealized_pnl >= 0 ? 'text-success-600' : 'text-danger-600'"
              >
                {{ formatCurrency(pos.unrealized_pnl) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Recent Trades -->
    <div class="card">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold text-gray-900">Recent Shadow Trades</h2>
        <select v-model="selectedStrategy" class="input w-48 text-sm">
          <option value="">All Strategies</option>
          <option v-for="s in strategyNames" :key="s" :value="s">{{ s }}</option>
        </select>
      </div>

      <div v-if="trades.length === 0" class="text-gray-500 text-center py-8">
        No shadow trades yet. Enable shadow mode on a strategy to start paper trading.
      </div>

      <div v-else class="overflow-x-auto">
        <table class="min-w-full">
          <thead>
            <tr class="border-b border-gray-200">
              <th class="text-left py-2 text-sm font-medium text-gray-500">Time</th>
              <th class="text-left py-2 text-sm font-medium text-gray-500">Strategy</th>
              <th class="text-left py-2 text-sm font-medium text-gray-500">Side</th>
              <th class="text-right py-2 text-sm font-medium text-gray-500">Size</th>
              <th class="text-right py-2 text-sm font-medium text-gray-500">Signal Price</th>
              <th class="text-right py-2 text-sm font-medium text-gray-500">Fill Price</th>
              <th class="text-right py-2 text-sm font-medium text-gray-500">Slippage</th>
              <th class="text-right py-2 text-sm font-medium text-gray-500">Confidence</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="trade in trades"
              :key="trade.id"
              class="border-b border-gray-100 hover:bg-gray-50"
            >
              <td class="py-3 text-sm text-gray-600">
                {{ formatTime(trade.timestamp) }}
              </td>
              <td class="py-3 capitalize">{{ trade.strategy }}</td>
              <td class="py-3">
                <span
                  class="px-2 py-0.5 text-xs font-medium rounded"
                  :class="trade.side === 'BUY' ? 'bg-success-100 text-success-700' : 'bg-danger-100 text-danger-700'"
                >
                  {{ trade.side }}
                </span>
              </td>
              <td class="py-3 text-right">{{ trade.size?.toFixed(2) }}</td>
              <td class="py-3 text-right">${{ trade.price?.toFixed(4) }}</td>
              <td class="py-3 text-right">${{ trade.simulated_fill_price?.toFixed(4) }}</td>
              <td class="py-3 text-right text-gray-500">
                ${{ trade.slippage?.toFixed(4) }}
              </td>
              <td class="py-3 text-right">
                {{ (trade.signal_confidence * 100).toFixed(0) }}%
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { shadow } from '../api/client'

const loading = ref(true)
const summary = ref({})
const performance = ref({})
const positions = ref([])
const trades = ref([])
const selectedStrategy = ref('')

const strategyNames = computed(() => {
  if (!performance.value.strategies) return []
  return Object.keys(performance.value.strategies)
})

async function fetchData() {
  loading.value = true
  try {
    const [summaryRes, perfRes, posRes, tradesRes] = await Promise.all([
      shadow.summary(),
      shadow.performance(),
      shadow.positions(),
      shadow.trades(selectedStrategy.value || null, 50),
    ])

    summary.value = summaryRes.data || {}
    performance.value = perfRes.data || {}
    positions.value = posRes.data?.positions || []
    trades.value = tradesRes.data?.trades || []
  } catch (e) {
    console.error('Failed to fetch shadow data:', e)
  } finally {
    loading.value = false
  }
}

async function resetAll() {
  if (!confirm('Are you sure you want to reset all shadow trading data?')) {
    return
  }
  try {
    await shadow.reset()
    await fetchData()
  } catch (e) {
    console.error('Failed to reset shadow data:', e)
  }
}

watch(selectedStrategy, () => {
  fetchData()
})

function formatCurrency(value) {
  if (value === undefined || value === null) return '$0.00'
  const sign = value >= 0 ? '+' : ''
  return `${sign}$${Math.abs(value).toFixed(2)}`
}

function formatPercent(value) {
  if (value === undefined || value === null) return '0%'
  return `${(value * 100).toFixed(1)}%`
}

function formatTime(isoString) {
  if (!isoString) return ''
  const date = new Date(isoString)
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

onMounted(() => {
  fetchData()
  // Refresh every 30 seconds
  setInterval(fetchData, 30000)
})
</script>
