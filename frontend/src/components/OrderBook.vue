<template>
  <div>
    <div v-if="loading" class="text-gray-500 text-center py-4">Loading orderbook...</div>
    <div v-else-if="!orderbook" class="text-gray-500 text-center py-4">No orderbook data</div>
    <div v-else class="grid grid-cols-2 gap-4">
      <!-- Bids -->
      <div>
        <div class="text-sm font-medium text-gray-500 mb-2">Bids</div>
        <div class="space-y-1">
          <div
            v-for="(bid, index) in orderbook.bids?.slice(0, 10)"
            :key="`bid-${index}`"
            class="flex justify-between text-sm py-1 px-2 bg-success-50 rounded"
          >
            <span class="text-success-600 font-medium">${{ bid.price.toFixed(3) }}</span>
            <span class="text-gray-600">{{ bid.size.toFixed(2) }}</span>
          </div>
        </div>
      </div>

      <!-- Asks -->
      <div>
        <div class="text-sm font-medium text-gray-500 mb-2">Asks</div>
        <div class="space-y-1">
          <div
            v-for="(ask, index) in orderbook.asks?.slice(0, 10)"
            :key="`ask-${index}`"
            class="flex justify-between text-sm py-1 px-2 bg-danger-50 rounded"
          >
            <span class="text-danger-600 font-medium">${{ ask.price.toFixed(3) }}</span>
            <span class="text-gray-600">{{ ask.size.toFixed(2) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Spread Info -->
    <div v-if="orderbook" class="mt-4 pt-4 border-t border-gray-100 flex justify-center space-x-8 text-sm">
      <div>
        <span class="text-gray-500">Best Bid:</span>
        <span class="ml-2 font-medium text-success-600">
          ${{ orderbook.bids?.[0]?.price.toFixed(3) || '—' }}
        </span>
      </div>
      <div>
        <span class="text-gray-500">Best Ask:</span>
        <span class="ml-2 font-medium text-danger-600">
          ${{ orderbook.asks?.[0]?.price.toFixed(3) || '—' }}
        </span>
      </div>
      <div>
        <span class="text-gray-500">Spread:</span>
        <span class="ml-2 font-medium">{{ spreadDisplay }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { markets } from '../api/client'

const props = defineProps({
  marketId: {
    type: String,
    required: true,
  },
  tokenId: {
    type: String,
    required: true,
  },
})

const orderbook = ref(null)
const loading = ref(false)

const spreadDisplay = computed(() => {
  if (!orderbook.value?.bids?.[0] || !orderbook.value?.asks?.[0]) return '—'
  const spread = orderbook.value.asks[0].price - orderbook.value.bids[0].price
  return `$${spread.toFixed(3)}`
})

async function fetchOrderbook() {
  if (!props.tokenId) return
  loading.value = true
  try {
    const response = await markets.getOrderbook(props.marketId, props.tokenId)
    orderbook.value = response.data
  } catch (e) {
    console.error('Failed to fetch orderbook:', e)
  } finally {
    loading.value = false
  }
}

watch([() => props.marketId, () => props.tokenId], fetchOrderbook)

onMounted(fetchOrderbook)
</script>
