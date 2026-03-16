<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold text-gray-900">Analytics</h1>
      <div class="flex items-center space-x-4">
        <select v-model="selectedDays" class="input w-32">
          <option :value="7">7 days</option>
          <option :value="30">30 days</option>
          <option :value="90">90 days</option>
          <option :value="365">1 year</option>
        </select>
        <select v-model="selectedStrategy" class="input w-40">
          <option value="">All Strategies</option>
          <option v-for="s in strategyList" :key="s.name" :value="s.name">
            {{ s.name }}
          </option>
        </select>
      </div>
    </div>

    <!-- Summary Stats -->
    <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
      <div class="card text-center">
        <div class="text-sm text-gray-500">Total Trades</div>
        <div class="text-2xl font-semibold">{{ summary?.total_trades || 0 }}</div>
      </div>
      <div class="card text-center">
        <div class="text-sm text-gray-500">Win Rate</div>
        <div class="text-2xl font-semibold">{{ formatPercent(summary?.win_rate) }}</div>
      </div>
      <div class="card text-center">
        <div class="text-sm text-gray-500">Total P&L</div>
        <div
          class="text-2xl font-semibold"
          :class="(summary?.total_pnl || 0) >= 0 ? 'text-success-600' : 'text-danger-600'"
        >
          {{ formatCurrency(summary?.total_pnl) }}
        </div>
      </div>
      <div class="card text-center">
        <div class="text-sm text-gray-500">Volume</div>
        <div class="text-2xl font-semibold">{{ formatCurrency(summary?.total_volume) }}</div>
      </div>
      <div class="card text-center">
        <div class="text-sm text-gray-500">Fees</div>
        <div class="text-2xl font-semibold text-gray-600">
          {{ formatCurrency(summary?.total_fees) }}
        </div>
      </div>
    </div>

    <!-- Charts -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="card">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">P&L Over Time</h2>
        <AnalyticsCharts
          v-if="historyData.length > 0"
          type="pnl"
          :data="historyData"
        />
        <div v-else class="text-gray-500 text-center py-8">No data available</div>
      </div>

      <div class="card">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">Daily Trades</h2>
        <AnalyticsCharts
          v-if="historyData.length > 0"
          type="trades"
          :data="historyData"
        />
        <div v-else class="text-gray-500 text-center py-8">No data available</div>
      </div>
    </div>

    <!-- Strategy Breakdown -->
    <div class="card">
      <h2 class="text-lg font-semibold text-gray-900 mb-4">Strategy Performance</h2>
      <div v-if="loading.analytics" class="text-gray-500">Loading...</div>
      <table v-else class="min-w-full">
        <thead>
          <tr class="text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
            <th class="pb-3">Strategy</th>
            <th class="pb-3">Trades</th>
            <th class="pb-3">Win Rate</th>
            <th class="pb-3">P&L</th>
            <th class="pb-3">Volume</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          <tr v-for="(data, name) in strategyStats" :key="name">
            <td class="py-3 font-medium">{{ name }}</td>
            <td class="py-3">{{ data.summary?.total_trades || 0 }}</td>
            <td class="py-3">{{ formatPercent(data.summary?.win_rate) }}</td>
            <td
              class="py-3"
              :class="(data.summary?.total_pnl || 0) >= 0 ? 'text-success-600' : 'text-danger-600'"
            >
              {{ formatCurrency(data.summary?.total_pnl) }}
            </td>
            <td class="py-3">{{ formatCurrency(data.summary?.total_volume) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Trade History -->
    <div class="card">
      <h2 class="text-lg font-semibold text-gray-900 mb-4">Recent Daily Stats</h2>
      <TradeHistory :days="historyData.slice(0, 14)" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useMainStore } from '../stores/main'
import { analytics } from '../api/client'
import AnalyticsCharts from '../components/AnalyticsCharts.vue'
import TradeHistory from '../components/TradeHistory.vue'

const mainStore = useMainStore()
const { strategyList, loading, performanceSummary } = storeToRefs(mainStore)

const selectedDays = ref(30)
const selectedStrategy = ref('')
const historyData = ref([])
const strategyStats = ref({})

const summary = computed(() => performanceSummary.value)

function formatCurrency(value) {
  if (value === undefined || value === null) return '$0.00'
  const sign = value >= 0 ? '+' : ''
  return `${sign}$${Math.abs(value).toFixed(2)}`
}

function formatPercent(value) {
  if (value === undefined || value === null) return '0.0%'
  return `${(value * 100).toFixed(1)}%`
}

async function fetchData() {
  loading.value.analytics = true
  try {
    const params = {
      days: selectedDays.value,
      ...(selectedStrategy.value && { strategy: selectedStrategy.value }),
    }

    const [historyRes, strategyRes] = await Promise.all([
      analytics.history(params),
      analytics.strategies({ days: selectedDays.value }),
    ])

    historyData.value = historyRes.data.days || []
    strategyStats.value = strategyRes.data || {}

    mainStore.fetchAnalytics(params)
  } catch (e) {
    console.error('Failed to fetch analytics:', e)
  } finally {
    loading.value.analytics = false
  }
}

watch([selectedDays, selectedStrategy], fetchData)

onMounted(() => {
  mainStore.fetchStrategies()
  fetchData()
})
</script>
