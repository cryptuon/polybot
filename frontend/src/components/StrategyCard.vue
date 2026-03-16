<template>
  <div class="card">
    <div class="flex items-start justify-between">
      <div>
        <h3 class="text-lg font-semibold text-gray-900 capitalize">
          {{ strategy.name }}
        </h3>
        <p class="text-sm text-gray-500 mt-1">{{ strategy.description }}</p>
      </div>
      <div class="flex items-center space-x-2">
        <span
          v-if="runnerStatus"
          class="px-2 py-0.5 text-xs font-medium rounded-full"
          :class="statusClass"
        >
          {{ runnerStatus.status }}
        </span>
        <span
          v-if="strategy.shadow"
          class="badge badge-warning"
          title="Shadow mode: signals logged but not executed"
        >
          Shadow
        </span>
        <span
          class="badge"
          :class="strategy.enabled ? 'badge-success' : 'badge-danger'"
        >
          {{ strategy.enabled ? 'Enabled' : 'Disabled' }}
        </span>
      </div>
    </div>

    <!-- Strategy Stats -->
    <div class="mt-4 grid grid-cols-3 gap-4 text-center">
      <div>
        <div class="text-sm text-gray-500">Trades</div>
        <div class="text-lg font-semibold">{{ strategy.stats?.trades || 0 }}</div>
      </div>
      <div>
        <div class="text-sm text-gray-500">Win Rate</div>
        <div class="text-lg font-semibold">
          {{ formatPercent(strategy.stats?.win_rate) }}
        </div>
      </div>
      <div>
        <div class="text-sm text-gray-500">P&L</div>
        <div
          class="text-lg font-semibold"
          :class="(strategy.stats?.pnl || 0) >= 0 ? 'text-success-600' : 'text-danger-600'"
        >
          {{ formatCurrency(strategy.stats?.pnl) }}
        </div>
      </div>
    </div>

    <!-- Config Preview -->
    <div v-if="strategy.config && Object.keys(strategy.config).length > 0" class="mt-4 pt-4 border-t border-gray-100">
      <div class="text-xs text-gray-500 uppercase tracking-wider mb-2">Configuration</div>
      <div class="grid grid-cols-2 gap-2 text-sm">
        <div v-for="(value, key) in displayConfig" :key="key" class="flex justify-between">
          <span class="text-gray-500">{{ formatKey(key) }}</span>
          <span class="font-medium">{{ formatValue(value) }}</span>
        </div>
      </div>
    </div>

    <!-- Actions -->
    <div class="mt-4 pt-4 border-t border-gray-100 flex justify-between items-center">
      <div class="flex space-x-2">
        <button
          @click="$emit('toggle', strategy.name)"
          class="btn text-sm"
          :class="strategy.enabled ? 'btn-danger' : 'btn-success'"
        >
          {{ strategy.enabled ? 'Disable' : 'Enable' }}
        </button>
        <button
          @click="$emit('toggleShadow', strategy.name)"
          class="btn text-sm"
          :class="strategy.shadow ? 'btn-warning' : 'btn-secondary'"
          :title="strategy.shadow ? 'Disable shadow mode (execute trades)' : 'Enable shadow mode (log only)'"
        >
          {{ strategy.shadow ? 'Live Mode' : 'Shadow' }}
        </button>
        <button
          @click="$emit('configure', strategy)"
          class="btn btn-secondary text-sm"
        >
          Configure
        </button>
      </div>
      <div class="flex space-x-2">
        <button
          v-if="isRunning"
          @click="$emit('stop', strategy.name)"
          class="btn btn-danger text-sm"
          :disabled="loading"
        >
          Stop
        </button>
        <button
          v-else-if="strategy.enabled"
          @click="$emit('start', strategy.name)"
          class="btn btn-success text-sm"
          :disabled="loading"
        >
          Start
        </button>
        <button
          v-if="isRunning"
          @click="$emit('restart', strategy.name)"
          class="btn btn-secondary text-sm"
          :disabled="loading"
        >
          Restart
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  strategy: {
    type: Object,
    required: true,
  },
  runnerStatus: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['toggle', 'toggleShadow', 'configure', 'start', 'stop', 'restart'])

const isRunning = computed(() => props.runnerStatus?.status === 'running')

const statusClass = computed(() => {
  const status = props.runnerStatus?.status
  switch (status) {
    case 'running':
      return 'bg-success-100 text-success-800'
    case 'starting':
    case 'stopping':
      return 'bg-warning-100 text-warning-800'
    case 'failed':
      return 'bg-danger-100 text-danger-800'
    default:
      return 'bg-gray-100 text-gray-600'
  }
})

const displayConfig = computed(() => {
  if (!props.strategy.config) return {}
  // Show first 4 config items
  const entries = Object.entries(props.strategy.config).slice(0, 4)
  return Object.fromEntries(entries)
})

function formatKey(key) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
}

function formatValue(value) {
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'number') {
    if (value < 1 && value > 0) return `${(value * 100).toFixed(0)}%`
    return value.toLocaleString()
  }
  return value
}

function formatPercent(value) {
  if (value === undefined || value === null) return '0%'
  return `${(value * 100).toFixed(1)}%`
}

function formatCurrency(value) {
  if (value === undefined || value === null) return '$0'
  const sign = value >= 0 ? '+' : ''
  return `${sign}$${Math.abs(value).toFixed(2)}`
}
</script>
