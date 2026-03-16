<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Markets</h1>
        <p class="text-sm text-gray-500 mt-1">
          {{ filteredMarkets.length }} of {{ marketList.length }} markets
        </p>
      </div>
      <div class="flex items-center space-x-4">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search markets..."
          class="input w-64"
        />
        <select v-model="activeFilter" class="input w-40">
          <option value="">All Markets</option>
          <option value="true">Active Only</option>
          <option value="false">Inactive</option>
        </select>
        <button
          @click="mainStore.fetchMarkets()"
          :disabled="loading.markets"
          class="btn btn-secondary"
        >
          {{ loading.markets ? 'Loading...' : 'Refresh' }}
        </button>
      </div>
    </div>

    <div class="card">
      <MarketList
        :markets="filteredMarkets"
        :loading="loading.markets"
        @select="selectMarket"
      />
    </div>

    <!-- Market Detail Modal -->
    <div
      v-if="selectedMarket"
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      @click.self="selectedMarket = null"
    >
      <div class="bg-white rounded-xl shadow-xl max-w-4xl w-full mx-4 max-h-[90vh] overflow-hidden">
        <div class="p-6 border-b border-gray-200 flex items-center justify-between">
          <h2 class="text-xl font-semibold text-gray-900">{{ selectedMarket.question }}</h2>
          <button
            @click="selectedMarket = null"
            class="text-gray-400 hover:text-gray-600"
          >
            <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div class="p-6 overflow-y-auto max-h-[calc(90vh-100px)]">
          <div class="grid grid-cols-2 gap-6">
            <!-- Market Info -->
            <div class="space-y-4">
              <div>
                <div class="text-sm font-medium text-gray-500">Market ID</div>
                <div class="font-mono text-sm">{{ selectedMarket.id }}</div>
              </div>
              <div>
                <div class="text-sm font-medium text-gray-500">End Date</div>
                <div>{{ formatDate(selectedMarket.end_date) }}</div>
              </div>
              <div>
                <div class="text-sm font-medium text-gray-500">Status</div>
                <span
                  class="badge"
                  :class="selectedMarket.active ? 'badge-success' : 'badge-danger'"
                >
                  {{ selectedMarket.active ? 'Active' : 'Inactive' }}
                </span>
              </div>
            </div>

            <!-- Current Prices -->
            <div class="space-y-4">
              <div>
                <div class="text-sm font-medium text-gray-500">YES Price</div>
                <div class="text-2xl font-semibold text-success-600">
                  ${{ selectedMarket.yes_price?.toFixed(3) || currentPrice?.mid?.toFixed(3) || '—' }}
                </div>
              </div>
              <div>
                <div class="text-sm font-medium text-gray-500">NO Price</div>
                <div class="text-2xl font-semibold text-danger-600">
                  ${{ selectedMarket.no_price?.toFixed(3) || (currentPrice?.mid ? (1 - currentPrice.mid).toFixed(3) : '—') }}
                </div>
              </div>
              <div v-if="currentPrice">
                <div class="text-sm font-medium text-gray-500">Live Spread</div>
                <div class="text-lg font-medium text-gray-700">
                  ${{ currentPrice.bid?.toFixed(3) }} / ${{ currentPrice.ask?.toFixed(3) }}
                </div>
              </div>
            </div>
          </div>

          <!-- Order Book -->
          <div class="mt-6">
            <h3 class="text-lg font-semibold text-gray-900 mb-4">Order Book (YES Token)</h3>
            <OrderBook
              :market-id="selectedMarket.id"
              :token-id="selectedMarket.outcome_yes_token"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useMainStore } from '../stores/main'
import { useWebSocketStore } from '../stores/websocket'
import MarketList from '../components/MarketList.vue'
import OrderBook from '../components/OrderBook.vue'

const mainStore = useMainStore()
const wsStore = useWebSocketStore()

const { marketList, loading } = storeToRefs(mainStore)
const { priceForMarket } = storeToRefs(wsStore)

const searchQuery = ref('')
const activeFilter = ref('')
const selectedMarket = ref(null)

const filteredMarkets = computed(() => {
  let markets = marketList.value

  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    markets = markets.filter(
      (m) =>
        m.question?.toLowerCase().includes(query) ||
        m.slug?.toLowerCase().includes(query)
    )
  }

  if (activeFilter.value !== '') {
    const isActive = activeFilter.value === 'true'
    markets = markets.filter((m) => m.active === isActive)
  }

  return markets
})

const currentPrice = computed(() => {
  if (!selectedMarket.value) return null
  return priceForMarket.value(selectedMarket.value.id)
})

function selectMarket(market) {
  selectedMarket.value = market
}

function formatDate(date) {
  if (!date) return 'N/A'
  return new Date(date).toLocaleDateString()
}

onMounted(() => {
  mainStore.fetchMarkets()
})
</script>
