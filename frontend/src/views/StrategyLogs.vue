<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div class="flex items-center space-x-4">
        <h1 class="text-2xl font-bold text-gray-900">Strategy Logs</h1>
        <span
          v-if="currentRun"
          class="px-2 py-1 text-xs font-medium rounded-full bg-success-100 text-success-800"
        >
          Running
        </span>
      </div>
      <div class="flex items-center space-x-4">
        <select v-model="selectedStrategy" class="input w-40">
          <option value="">All Strategies</option>
          <option v-for="s in strategyList" :key="s.name" :value="s.name">
            {{ s.name }}
          </option>
        </select>
        <select v-model="selectedLogType" class="input w-32">
          <option value="">All Types</option>
          <option value="scan">Scan</option>
          <option value="signal">Signal</option>
          <option value="entry">Entry</option>
          <option value="exit">Exit</option>
          <option value="error">Error</option>
          <option value="start">Start</option>
          <option value="stop">Stop</option>
        </select>
        <select v-model="selectedLevel" class="input w-32">
          <option value="">All Levels</option>
          <option value="DEBUG">Debug</option>
          <option value="INFO">Info</option>
          <option value="WARNING">Warning</option>
          <option value="ERROR">Error</option>
          <option value="SIGNAL">Signal</option>
        </select>
      </div>
    </div>

    <!-- Tab Navigation -->
    <div class="border-b border-gray-200">
      <nav class="flex space-x-8">
        <button
          @click="activeTab = 'runs'"
          class="py-4 px-1 border-b-2 font-medium text-sm"
          :class="activeTab === 'runs'
            ? 'border-primary-500 text-primary-600'
            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'"
        >
          Run History
        </button>
        <button
          @click="activeTab = 'logs'"
          class="py-4 px-1 border-b-2 font-medium text-sm"
          :class="activeTab === 'logs'
            ? 'border-primary-500 text-primary-600'
            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'"
        >
          Log Entries
        </button>
        <button
          v-if="selectedStrategy"
          @click="activeTab = 'scans'"
          class="py-4 px-1 border-b-2 font-medium text-sm"
          :class="activeTab === 'scans'
            ? 'border-primary-500 text-primary-600'
            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'"
        >
          Scan Activity
        </button>
      </nav>
    </div>

    <!-- Run History Tab -->
    <div v-if="activeTab === 'runs'" class="space-y-4">
      <div v-if="loading" class="text-gray-500 text-center py-8">Loading runs...</div>
      <div v-else-if="runs.length === 0" class="text-gray-500 text-center py-8">
        No run history available
      </div>
      <div v-else class="space-y-3">
        <div
          v-for="run in runs"
          :key="run.id"
          class="card hover:shadow-md transition-shadow"
        >
          <div class="flex items-start justify-between">
            <div>
              <div class="flex items-center space-x-3">
                <span class="font-semibold text-gray-900">{{ run.strategy }}</span>
                <span
                  class="px-2 py-0.5 text-xs font-medium rounded-full"
                  :class="getStatusClass(run.status)"
                >
                  {{ run.status }}
                </span>
              </div>
              <div class="text-sm text-gray-500 mt-1">
                Started: {{ formatDateTime(run.start_time) }}
                <span v-if="run.end_time"> | Ended: {{ formatDateTime(run.end_time) }}</span>
                <span v-if="run.duration_seconds">
                  | Duration: {{ formatDuration(run.duration_seconds) }}
                </span>
              </div>
            </div>
            <div class="text-right">
              <div class="grid grid-cols-4 gap-4 text-sm">
                <div>
                  <div class="text-gray-500">Scans</div>
                  <div class="font-semibold">{{ run.scans_performed }}</div>
                </div>
                <div>
                  <div class="text-gray-500">Signals</div>
                  <div class="font-semibold">{{ run.signals_generated }}</div>
                </div>
                <div>
                  <div class="text-gray-500">Entries</div>
                  <div class="font-semibold text-success-600">{{ run.entries }}</div>
                </div>
                <div>
                  <div class="text-gray-500">Errors</div>
                  <div class="font-semibold" :class="run.errors > 0 ? 'text-danger-600' : ''">
                    {{ run.errors }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Log Entries Tab -->
    <div v-if="activeTab === 'logs'" class="space-y-4">
      <div v-if="loading" class="text-gray-500 text-center py-8">Loading logs...</div>
      <div v-else-if="logs.length === 0" class="text-gray-500 text-center py-8">
        No log entries found
      </div>
      <div v-else class="card overflow-hidden">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Strategy</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Level</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Message</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Details</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200">
            <tr v-for="log in logs" :key="log.id" class="hover:bg-gray-50">
              <td class="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">
                {{ formatTime(log.timestamp) }}
              </td>
              <td class="px-4 py-3 text-sm font-medium text-gray-900">
                {{ log.strategy }}
              </td>
              <td class="px-4 py-3">
                <span
                  class="px-2 py-0.5 text-xs font-medium rounded-full"
                  :class="getLogTypeClass(log.log_type)"
                >
                  {{ log.log_type }}
                </span>
              </td>
              <td class="px-4 py-3">
                <span
                  class="px-2 py-0.5 text-xs font-medium rounded-full"
                  :class="getLevelClass(log.level)"
                >
                  {{ log.level }}
                </span>
              </td>
              <td class="px-4 py-3 text-sm text-gray-600 max-w-md truncate">
                {{ log.message }}
              </td>
              <td class="px-4 py-3 text-sm text-gray-500">
                <div v-if="log.action" class="text-xs">
                  <span class="font-medium">{{ log.action }}</span>
                  <span v-if="log.price"> @ {{ log.price.toFixed(4) }}</span>
                  <span v-if="log.size"> ({{ log.size.toFixed(2) }})</span>
                </div>
                <div v-if="log.confidence" class="text-xs text-gray-400">
                  Confidence: {{ (log.confidence * 100).toFixed(1) }}%
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- Pagination -->
        <div class="px-4 py-3 border-t border-gray-200 flex items-center justify-between bg-gray-50">
          <div class="text-sm text-gray-500">
            Showing {{ offset + 1 }} - {{ Math.min(offset + limit, totalLogs) }} of {{ totalLogs }}
          </div>
          <div class="flex space-x-2">
            <button
              @click="prevPage"
              :disabled="offset === 0"
              class="btn btn-secondary btn-sm"
              :class="{ 'opacity-50 cursor-not-allowed': offset === 0 }"
            >
              Previous
            </button>
            <button
              @click="nextPage"
              :disabled="offset + limit >= totalLogs"
              class="btn btn-secondary btn-sm"
              :class="{ 'opacity-50 cursor-not-allowed': offset + limit >= totalLogs }"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Scan Activity Tab -->
    <div v-if="activeTab === 'scans' && selectedStrategy" class="space-y-4">
      <div class="flex items-center space-x-4">
        <select v-model="scanHours" class="input w-32">
          <option :value="1">1 hour</option>
          <option :value="6">6 hours</option>
          <option :value="24">24 hours</option>
          <option :value="72">3 days</option>
          <option :value="168">7 days</option>
        </select>
      </div>

      <div v-if="loading" class="text-gray-500 text-center py-8">Loading scan data...</div>
      <div v-else-if="scanSummaries.length === 0" class="text-gray-500 text-center py-8">
        No scan activity data available
      </div>
      <div v-else class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="card text-center">
          <div class="text-sm text-gray-500">Total Scans</div>
          <div class="text-2xl font-semibold">{{ totalScans.toLocaleString() }}</div>
        </div>
        <div class="card text-center">
          <div class="text-sm text-gray-500">Opportunities</div>
          <div class="text-2xl font-semibold text-primary-600">{{ totalOpportunities }}</div>
        </div>
        <div class="card text-center">
          <div class="text-sm text-gray-500">Signals</div>
          <div class="text-2xl font-semibold text-success-600">{{ totalSignals }}</div>
        </div>
        <div class="card text-center">
          <div class="text-sm text-gray-500">Avg Scan Time</div>
          <div class="text-2xl font-semibold">{{ avgScanTime.toFixed(1) }}ms</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useMainStore } from '../stores/main'
import { strategyLogs, strategies } from '../api/client'

const route = useRoute()
const router = useRouter()
const mainStore = useMainStore()
const { strategyList } = storeToRefs(mainStore)

const activeTab = ref('runs')
const loading = ref(false)
const selectedStrategy = ref('')
const selectedLogType = ref('')
const selectedLevel = ref('')
const scanHours = ref(24)

// Data
const runs = ref([])
const logs = ref([])
const totalLogs = ref(0)
const scanSummaries = ref([])
const currentRun = ref(null)

// Pagination
const limit = ref(50)
const offset = ref(0)

// Computed totals for scans
const totalScans = computed(() => scanSummaries.value.reduce((sum, s) => sum + s.scan_count, 0))
const totalOpportunities = computed(() => scanSummaries.value.reduce((sum, s) => sum + s.opportunities, 0))
const totalSignals = computed(() => scanSummaries.value.reduce((sum, s) => sum + s.signals, 0))
const avgScanTime = computed(() => {
  const withTime = scanSummaries.value.filter(s => s.avg_scan_duration_ms)
  if (withTime.length === 0) return 0
  return withTime.reduce((sum, s) => sum + s.avg_scan_duration_ms, 0) / withTime.length
})

// Initialize from route params
onMounted(() => {
  if (route.params.strategy) {
    selectedStrategy.value = route.params.strategy
  }
  mainStore.fetchStrategies()
  fetchData()
})

// Watch for filter changes
watch([selectedStrategy, selectedLogType, selectedLevel], () => {
  offset.value = 0
  fetchData()

  // Update URL when strategy changes
  if (selectedStrategy.value) {
    router.replace({ name: 'strategy-logs-detail', params: { strategy: selectedStrategy.value } })
  } else {
    router.replace({ name: 'strategy-logs' })
  }
})

watch([activeTab, scanHours], fetchData)
watch([offset], fetchLogs)

async function fetchData() {
  loading.value = true
  try {
    await Promise.all([
      fetchRuns(),
      fetchLogs(),
      selectedStrategy.value ? fetchScans() : Promise.resolve(),
      selectedStrategy.value ? fetchCurrentRun() : Promise.resolve(),
    ])
  } finally {
    loading.value = false
  }
}

async function fetchRuns() {
  try {
    const params = { limit: 50 }
    const res = selectedStrategy.value
      ? await strategyLogs.runs(selectedStrategy.value, params)
      : await strategyLogs.allRuns(params)
    runs.value = res.data.runs || []
  } catch (e) {
    console.error('Failed to fetch runs:', e)
    runs.value = []
  }
}

async function fetchLogs() {
  try {
    const params = {
      limit: limit.value,
      offset: offset.value,
      ...(selectedLogType.value && { log_type: selectedLogType.value }),
      ...(selectedLevel.value && { level: selectedLevel.value }),
    }
    const res = selectedStrategy.value
      ? await strategyLogs.logs(selectedStrategy.value, params)
      : await strategyLogs.allLogs(params)
    logs.value = res.data.logs || []
    totalLogs.value = res.data.total || 0
  } catch (e) {
    console.error('Failed to fetch logs:', e)
    logs.value = []
    totalLogs.value = 0
  }
}

async function fetchScans() {
  if (!selectedStrategy.value) return
  try {
    const res = await strategyLogs.scans(selectedStrategy.value, { hours: scanHours.value })
    scanSummaries.value = res.data.summaries || []
  } catch (e) {
    console.error('Failed to fetch scans:', e)
    scanSummaries.value = []
  }
}

async function fetchCurrentRun() {
  if (!selectedStrategy.value) return
  try {
    const res = await strategyLogs.currentRun(selectedStrategy.value)
    currentRun.value = res.data.running ? res.data.run_id : null
  } catch (e) {
    currentRun.value = null
  }
}

function prevPage() {
  if (offset.value > 0) {
    offset.value = Math.max(0, offset.value - limit.value)
  }
}

function nextPage() {
  if (offset.value + limit.value < totalLogs.value) {
    offset.value += limit.value
  }
}

function formatDateTime(dt) {
  if (!dt) return ''
  const date = new Date(dt)
  return date.toLocaleString()
}

function formatTime(dt) {
  if (!dt) return ''
  const date = new Date(dt)
  return date.toLocaleTimeString()
}

function formatDuration(seconds) {
  if (!seconds) return ''
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  return `${hours}h ${mins}m`
}

function getStatusClass(status) {
  switch (status) {
    case 'running':
      return 'bg-success-100 text-success-800'
    case 'stopped':
      return 'bg-gray-100 text-gray-800'
    case 'error':
      return 'bg-danger-100 text-danger-800'
    default:
      return 'bg-gray-100 text-gray-600'
  }
}

function getLogTypeClass(type) {
  switch (type) {
    case 'signal':
      return 'bg-primary-100 text-primary-800'
    case 'entry':
      return 'bg-success-100 text-success-800'
    case 'exit':
      return 'bg-warning-100 text-warning-800'
    case 'error':
      return 'bg-danger-100 text-danger-800'
    case 'start':
    case 'stop':
      return 'bg-blue-100 text-blue-800'
    default:
      return 'bg-gray-100 text-gray-600'
  }
}

function getLevelClass(level) {
  switch (level) {
    case 'ERROR':
      return 'bg-danger-100 text-danger-800'
    case 'WARNING':
      return 'bg-warning-100 text-warning-800'
    case 'SIGNAL':
      return 'bg-primary-100 text-primary-800'
    case 'DEBUG':
      return 'bg-gray-100 text-gray-600'
    default:
      return 'bg-gray-100 text-gray-800'
  }
}
</script>
