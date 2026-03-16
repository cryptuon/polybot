<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold text-gray-900">Strategies</h1>
      <div class="flex space-x-2">
        <button
          @click="startAll"
          class="btn btn-success text-sm"
          :disabled="actionLoading"
        >
          Start All
        </button>
        <button
          @click="stopAll"
          class="btn btn-danger text-sm"
          :disabled="actionLoading"
        >
          Stop All
        </button>
      </div>
    </div>

    <div v-if="loading.strategies" class="text-gray-500">Loading strategies...</div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <StrategyCard
        v-for="strategy in strategyList"
        :key="strategy.name"
        :strategy="strategy"
        :runner-status="runnerStatus[strategy.name]"
        :loading="actionLoading"
        @toggle="handleToggle"
        @toggle-shadow="handleToggleShadow"
        @configure="openConfig"
        @start="handleStart"
        @stop="handleStop"
        @restart="handleRestart"
      />
    </div>

    <!-- Configuration Modal -->
    <div
      v-if="configuring"
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      @click.self="configuring = null"
    >
      <div class="bg-white rounded-xl shadow-xl max-w-2xl w-full mx-4">
        <div class="p-6 border-b border-gray-200 flex items-center justify-between">
          <h2 class="text-xl font-semibold text-gray-900">
            Configure {{ configuring.name }}
          </h2>
          <button
            @click="configuring = null"
            class="text-gray-400 hover:text-gray-600"
          >
            <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div class="p-6 space-y-4">
          <div v-for="(value, key) in configuring.config" :key="key">
            <label class="block text-sm font-medium text-gray-700 mb-1">
              {{ formatConfigKey(key) }}
            </label>
            <input
              v-if="typeof value === 'number'"
              type="number"
              v-model.number="editConfig[key]"
              class="input"
              :step="key.includes('pct') || key.includes('rate') ? '0.01' : '1'"
            />
            <input
              v-else-if="typeof value === 'boolean'"
              type="checkbox"
              v-model="editConfig[key]"
              class="h-4 w-4 text-primary-600 rounded"
            />
            <input
              v-else
              type="text"
              v-model="editConfig[key]"
              class="input"
            />
          </div>
        </div>

        <div class="p-6 border-t border-gray-200 flex justify-end space-x-3">
          <button @click="configuring = null" class="btn btn-secondary">
            Cancel
          </button>
          <button @click="saveConfig" class="btn btn-primary">
            Save Changes
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useMainStore } from '../stores/main'
import { strategies } from '../api/client'
import StrategyCard from '../components/StrategyCard.vue'

const mainStore = useMainStore()
const { strategyList, loading } = storeToRefs(mainStore)

const configuring = ref(null)
const editConfig = reactive({})
const runnerStatus = ref({})
const actionLoading = ref(false)
let statusInterval = null

async function fetchRunnerStatus() {
  try {
    const res = await strategies.runnerStatus()
    if (res.data.success) {
      runnerStatus.value = res.data.strategies || {}
    }
  } catch (e) {
    console.error('Failed to fetch runner status:', e)
  }
}

async function handleToggle(strategyName) {
  try {
    await mainStore.toggleStrategy(strategyName)
  } catch (e) {
    console.error('Failed to toggle strategy:', e)
  }
}

async function handleToggleShadow(strategyName) {
  try {
    const strategy = strategyList.value.find(s => s.name === strategyName)
    const newShadow = !strategy?.shadow
    await strategies.toggleShadow(strategyName, newShadow)
    await mainStore.fetchStrategies()
  } catch (e) {
    console.error('Failed to toggle shadow mode:', e)
  }
}

async function handleStart(strategyName) {
  actionLoading.value = true
  try {
    await strategies.start(strategyName)
    await fetchRunnerStatus()
  } catch (e) {
    console.error('Failed to start strategy:', e)
  } finally {
    actionLoading.value = false
  }
}

async function handleStop(strategyName) {
  actionLoading.value = true
  try {
    await strategies.stop(strategyName)
    await fetchRunnerStatus()
  } catch (e) {
    console.error('Failed to stop strategy:', e)
  } finally {
    actionLoading.value = false
  }
}

async function handleRestart(strategyName) {
  actionLoading.value = true
  try {
    await strategies.restart(strategyName)
    await fetchRunnerStatus()
  } catch (e) {
    console.error('Failed to restart strategy:', e)
  } finally {
    actionLoading.value = false
  }
}

async function startAll() {
  actionLoading.value = true
  try {
    await strategies.startAll()
    await fetchRunnerStatus()
  } catch (e) {
    console.error('Failed to start all strategies:', e)
  } finally {
    actionLoading.value = false
  }
}

async function stopAll() {
  actionLoading.value = true
  try {
    await strategies.stopAll()
    await fetchRunnerStatus()
  } catch (e) {
    console.error('Failed to stop all strategies:', e)
  } finally {
    actionLoading.value = false
  }
}

function openConfig(strategy) {
  configuring.value = strategy
  Object.assign(editConfig, strategy.config || {})
}

async function saveConfig() {
  if (!configuring.value) return

  try {
    await strategies.update(configuring.value.name, {
      enabled: configuring.value.enabled,
      config: { ...editConfig },
    })
    await mainStore.fetchStrategies()
    configuring.value = null
  } catch (e) {
    console.error('Failed to save config:', e)
  }
}

function formatConfigKey(key) {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (l) => l.toUpperCase())
}

onMounted(() => {
  mainStore.fetchStrategies()
  fetchRunnerStatus()
  // Poll for status updates every 5 seconds
  statusInterval = setInterval(fetchRunnerStatus, 5000)
})

onUnmounted(() => {
  if (statusInterval) {
    clearInterval(statusInterval)
  }
})
</script>
