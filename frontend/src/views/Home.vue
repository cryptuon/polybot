<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-bold text-gray-900">Dashboard</h1>

    <!-- Stats Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      <div class="card">
        <div class="text-sm font-medium text-gray-500">Total P&L</div>
        <div
          class="mt-1 text-2xl font-semibold"
          :class="totalPnl >= 0 ? 'text-success-600' : 'text-danger-600'"
        >
          {{ formatCurrency(totalPnl) }}
        </div>
      </div>

      <div class="card">
        <div class="text-sm font-medium text-gray-500">Win Rate</div>
        <div class="mt-1 text-2xl font-semibold text-gray-900">
          {{ formatPercent(winRate) }}
        </div>
      </div>

      <div class="card">
        <div class="text-sm font-medium text-gray-500">Open Positions</div>
        <div class="mt-1 text-2xl font-semibold text-gray-900">
          {{ activePositions.length }}
        </div>
      </div>

      <div class="card">
        <div class="text-sm font-medium text-gray-500">Active Strategies</div>
        <div class="mt-1 text-2xl font-semibold text-gray-900">
          {{ enabledStrategies.length }}
        </div>
      </div>
    </div>

    <!-- Two Column Layout -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Active Strategies -->
      <div class="card">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">Active Strategies</h2>
        <div v-if="loading.strategies" class="text-gray-500">Loading...</div>
        <div v-else-if="strategyList.length === 0" class="text-gray-500">
          No strategies configured
        </div>
        <div v-else class="space-y-3">
          <div
            v-for="strategy in strategyList"
            :key="strategy.name"
            class="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
          >
            <div>
              <div class="font-medium text-gray-900">{{ strategy.name }}</div>
              <div class="text-sm text-gray-500">{{ strategy.description }}</div>
            </div>
            <span
              class="badge"
              :class="strategy.enabled ? 'badge-success' : 'badge-danger'"
            >
              {{ strategy.enabled ? 'Enabled' : 'Disabled' }}
            </span>
          </div>
        </div>
      </div>

      <!-- Recent Events -->
      <div class="card">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">Recent Events</h2>
        <div v-if="recentEvents.length === 0" class="text-gray-500">
          No recent events
        </div>
        <div v-else class="space-y-2 max-h-96 overflow-y-auto">
          <div
            v-for="(event, index) in recentEvents.slice(0, 15)"
            :key="index"
            class="flex items-start space-x-3 p-2 hover:bg-gray-50 rounded border-l-2"
            :class="getEventBorderColor(event.event_type)"
          >
            <span
              class="mt-1 h-2 w-2 rounded-full flex-shrink-0"
              :class="getEventColor(event.event_type)"
            ></span>
            <div class="flex-1 min-w-0">
              <div class="flex items-center justify-between">
                <div class="text-sm font-medium text-gray-900">
                  {{ formatEventType(event.event_type) }}
                </div>
                <div class="text-xs text-gray-400">
                  {{ formatTime(event.receivedAt) }}
                </div>
              </div>
              <div class="text-xs text-gray-600 mt-0.5">
                {{ event.source }}
              </div>
              <!-- Event details -->
              <div v-if="getEventDetails(event)" class="text-xs text-gray-500 mt-1">
                {{ getEventDetails(event) }}
              </div>
              <!-- Extra data for signals and trades -->
              <div v-if="event.data && (event.data.price || event.data.size)"
                   class="text-xs mt-1 flex items-center space-x-2">
                <span v-if="event.data.action"
                      class="px-1.5 py-0.5 rounded text-white text-[10px] font-medium"
                      :class="event.data.action === 'BUY' ? 'bg-success-500' : 'bg-danger-500'">
                  {{ event.data.action }}
                </span>
                <span v-if="event.data.size" class="text-gray-600">
                  {{ formatNumber(event.data.size) }} tokens
                </span>
                <span v-if="event.data.price" class="text-gray-600">
                  @ ${{ formatNumber(event.data.price) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Open Positions Table -->
    <div class="card">
      <h2 class="text-lg font-semibold text-gray-900 mb-4">Open Positions</h2>
      <PositionTable :positions="activePositions" :loading="loading.positions" />
    </div>
  </div>
</template>

<script setup>
import { onMounted, computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useMainStore } from '../stores/main'
import { useWebSocketStore } from '../stores/websocket'
import PositionTable from '../components/PositionTable.vue'

const mainStore = useMainStore()
const wsStore = useWebSocketStore()

const { strategyList, loading, activePositions, enabledStrategies, totalPnl, winRate } =
  storeToRefs(mainStore)
const { recentEvents } = storeToRefs(wsStore)

function formatCurrency(value) {
  const sign = value >= 0 ? '+' : ''
  return `${sign}$${Math.abs(value).toFixed(2)}`
}

function formatPercent(value) {
  return `${(value * 100).toFixed(1)}%`
}

function formatNumber(value) {
  if (value === null || value === undefined) return ''
  return Number(value).toFixed(2)
}

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString()
}

function formatEventType(eventType) {
  if (!eventType) return 'Unknown'
  return eventType
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (l) => l.toUpperCase())
}

function getEventColor(eventType) {
  const colors = {
    order_filled: 'bg-success-500',
    order_placed: 'bg-primary-500',
    order_cancelled: 'bg-gray-500',
    order_failed: 'bg-danger-500',
    trade_executed: 'bg-success-500',
    position_opened: 'bg-primary-500',
    position_closed: 'bg-warning-500',
    strategy_started: 'bg-primary-500',
    strategy_stopped: 'bg-gray-500',
    strategy_error: 'bg-danger-500',
    error: 'bg-danger-500',
    alert: 'bg-warning-500',
    signal: 'bg-primary-500',
    service_started: 'bg-success-500',
    service_stopped: 'bg-gray-500',
  }
  return colors[eventType] || 'bg-gray-400'
}

function getEventBorderColor(eventType) {
  const colors = {
    order_filled: 'border-success-500',
    order_placed: 'border-primary-500',
    order_cancelled: 'border-gray-400',
    order_failed: 'border-danger-500',
    trade_executed: 'border-success-500',
    position_opened: 'border-primary-500',
    position_closed: 'border-warning-500',
    strategy_started: 'border-primary-500',
    strategy_stopped: 'border-gray-400',
    strategy_error: 'border-danger-500',
    error: 'border-danger-500',
    alert: 'border-warning-500',
    signal: 'border-primary-500',
    service_started: 'border-success-500',
    service_stopped: 'border-gray-400',
  }
  return colors[eventType] || 'border-gray-300'
}

function getEventDetails(event) {
  if (!event.data) return null

  const data = event.data
  const parts = []

  // Strategy-specific details
  if (data.strategy) {
    parts.push(`Strategy: ${data.strategy}`)
  }

  // Reason for signals
  if (data.reason) {
    parts.push(data.reason)
  }

  // Market ID (truncated)
  if (data.market_id) {
    parts.push(`Market: ${data.market_id.substring(0, 8)}...`)
  }

  // Confidence for signals
  if (data.confidence !== undefined && data.confidence !== null) {
    parts.push(`Confidence: ${(data.confidence * 100).toFixed(0)}%`)
  }

  // PnL for position closes
  if (data.pnl !== undefined) {
    const sign = data.pnl >= 0 ? '+' : ''
    parts.push(`PnL: ${sign}$${data.pnl.toFixed(2)}`)
  }

  // Stats for strategy stopped
  if (data.scans_performed !== undefined) {
    parts.push(`Scans: ${data.scans_performed}, Signals: ${data.signals_sent || 0}`)
  }

  // Error message
  if (data.error) {
    parts.push(`Error: ${data.error}`)
  }

  if (data.message) {
    parts.push(data.message)
  }

  return parts.length > 0 ? parts.join(' | ') : null
}

onMounted(() => {
  mainStore.fetchStrategies()
  mainStore.fetchPositions()
  mainStore.fetchAnalytics()
})
</script>
