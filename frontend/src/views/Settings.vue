<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-bold text-gray-900">Settings</h1>

    <!-- System Status -->
    <div class="card">
      <h2 class="text-lg font-semibold text-gray-900 mb-4">System Status</h2>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div
          v-for="service in systemStatus?.services || []"
          :key="service.name"
          class="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
        >
          <span class="font-medium capitalize">{{ service.name }}</span>
          <span
            class="badge"
            :class="getStatusBadge(service.status)"
          >
            {{ service.status }}
          </span>
        </div>
      </div>
      <div class="mt-4 flex items-center justify-between">
        <span class="text-sm text-gray-500">
          Uptime: {{ formatUptime(systemStatus?.uptime_seconds) }}
        </span>
        <button @click="reloadConfig" class="btn btn-secondary text-sm">
          Reload Configuration
        </button>
      </div>
    </div>

    <!-- Risk Settings -->
    <div class="card">
      <h2 class="text-lg font-semibold text-gray-900 mb-4">Risk Management</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">
            Max Position Size (USD)
          </label>
          <input
            v-model.number="riskSettings.max_position_size_usd"
            type="number"
            class="input"
            step="100"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">
            Max Total Exposure (USD)
          </label>
          <input
            v-model.number="riskSettings.max_total_exposure_usd"
            type="number"
            class="input"
            step="1000"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">
            Daily Loss Limit (USD)
          </label>
          <input
            v-model.number="riskSettings.daily_loss_limit_usd"
            type="number"
            class="input"
            step="100"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">
            Max Open Orders
          </label>
          <input
            v-model.number="riskSettings.max_open_orders"
            type="number"
            class="input"
          />
        </div>
      </div>

      <!-- Current Risk Status -->
      <div class="mt-6 p-4 bg-gray-50 rounded-lg">
        <h3 class="font-medium text-gray-900 mb-3">Current Risk Status</h3>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <span class="text-gray-500">Daily P&L:</span>
            <span
              class="ml-2 font-medium"
              :class="(riskStatus?.daily_pnl || 0) >= 0 ? 'text-success-600' : 'text-danger-600'"
            >
              ${{ riskStatus?.daily_pnl?.toFixed(2) || '0.00' }}
            </span>
          </div>
          <div>
            <span class="text-gray-500">Exposure:</span>
            <span class="ml-2 font-medium">
              ${{ riskStatus?.total_exposure?.toFixed(2) || '0.00' }}
            </span>
          </div>
          <div>
            <span class="text-gray-500">Open Orders:</span>
            <span class="ml-2 font-medium">{{ riskStatus?.open_orders || 0 }}</span>
          </div>
          <div>
            <span class="text-gray-500">Positions:</span>
            <span class="ml-2 font-medium">{{ riskStatus?.open_positions || 0 }}</span>
          </div>
        </div>
      </div>

      <div class="mt-4 flex justify-end">
        <button @click="saveRiskSettings" class="btn btn-primary">
          Save Risk Settings
        </button>
      </div>
    </div>

    <!-- Strategy Settings -->
    <div class="card">
      <h2 class="text-lg font-semibold text-gray-900 mb-4">Strategy Configuration</h2>
      <div class="space-y-4">
        <div
          v-for="(config, name) in currentSettings?.strategies || {}"
          :key="name"
          class="p-4 border border-gray-200 rounded-lg"
        >
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center space-x-3">
              <span class="font-medium text-gray-900">{{ name }}</span>
              <span
                class="badge"
                :class="config.enabled ? 'badge-success' : 'badge-danger'"
              >
                {{ config.enabled ? 'Enabled' : 'Disabled' }}
              </span>
            </div>
            <button
              @click="toggleStrategy(name)"
              class="text-sm text-primary-600 hover:text-primary-700"
            >
              {{ config.enabled ? 'Disable' : 'Enable' }}
            </button>
          </div>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <div v-for="(value, key) in config.config" :key="key">
              <span class="text-gray-500">{{ formatKey(key) }}:</span>
              <span class="ml-1 font-medium">{{ formatValue(value) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- API Information -->
    <SettingsPanel />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useMainStore } from '../stores/main'
import { settings, strategies } from '../api/client'
import SettingsPanel from '../components/SettingsPanel.vue'

const mainStore = useMainStore()
const { currentSettings, riskStatus, systemStatus, loading } = storeToRefs(mainStore)

const riskSettings = reactive({
  max_position_size_usd: 1000,
  max_total_exposure_usd: 10000,
  daily_loss_limit_usd: 500,
  max_open_orders: 20,
})

function getStatusBadge(status) {
  const badges = {
    running: 'badge-success',
    stopped: 'badge-danger',
    error: 'badge-danger',
    unknown: 'badge-warning',
  }
  return badges[status] || 'badge-primary'
}

function formatUptime(seconds) {
  if (!seconds) return '0s'
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m`
}

function formatKey(key) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
}

function formatValue(value) {
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'number') {
    if (value < 1 && value > 0) return `${(value * 100).toFixed(1)}%`
    return value.toLocaleString()
  }
  return value
}

async function reloadConfig() {
  try {
    await settings.reload()
    await mainStore.fetchSettings()
  } catch (e) {
    console.error('Failed to reload config:', e)
  }
}

async function saveRiskSettings() {
  try {
    await mainStore.updateSettings({
      risk: { ...riskSettings },
    })
    alert('Risk settings saved! Restart services for changes to take effect.')
  } catch (e) {
    console.error('Failed to save settings:', e)
  }
}

async function toggleStrategy(name) {
  try {
    await strategies.toggle(name)
    await mainStore.fetchSettings()
  } catch (e) {
    console.error('Failed to toggle strategy:', e)
  }
}

onMounted(async () => {
  await mainStore.fetchSettings()

  // Populate risk settings from fetched data
  if (currentSettings.value?.risk) {
    Object.assign(riskSettings, currentSettings.value.risk)
  }
})
</script>
