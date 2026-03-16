<template>
  <div>
    <div v-if="loading" class="text-gray-500 text-center py-8">
      Loading markets...
    </div>
    <div v-else-if="markets.length === 0" class="text-gray-500 text-center py-8">
      No markets found
    </div>
    <div v-else class="overflow-x-auto">
      <table class="min-w-full">
        <thead>
          <tr class="text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
            <th class="pb-3 pr-4">Question</th>
            <th class="pb-3 px-4">YES</th>
            <th class="pb-3 px-4">NO</th>
            <th class="pb-3 px-4">Liquidity</th>
            <th class="pb-3 px-4">Volume 24h</th>
            <th class="pb-3 px-4">End Date</th>
            <th class="pb-3 pl-4"></th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          <tr
            v-for="market in markets"
            :key="market.id"
            class="hover:bg-gray-50 cursor-pointer"
            @click="$emit('select', market)"
          >
            <td class="py-4 pr-4">
              <div class="max-w-md truncate font-medium text-gray-900">
                {{ market.question }}
              </div>
              <div class="flex items-center space-x-2 mt-1">
                <span class="text-xs text-gray-500">{{ market.slug }}</span>
                <span
                  v-if="!market.active"
                  class="badge badge-danger text-xs"
                >
                  Inactive
                </span>
              </div>
            </td>
            <td class="py-4 px-4">
              <span class="text-success-600 font-medium">
                ${{ market.yes_price?.toFixed(3) || '—' }}
              </span>
            </td>
            <td class="py-4 px-4">
              <span class="text-danger-600 font-medium">
                ${{ market.no_price?.toFixed(3) || '—' }}
              </span>
            </td>
            <td class="py-4 px-4 text-sm">
              {{ formatCurrency(market.liquidity) }}
            </td>
            <td class="py-4 px-4 text-sm text-gray-600">
              {{ formatCurrency(market.volume_24h) }}
            </td>
            <td class="py-4 px-4 text-sm text-gray-500">
              {{ formatDate(market.end_date) }}
            </td>
            <td class="py-4 pl-4">
              <button class="text-primary-600 hover:text-primary-700 text-sm">
                View
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
defineProps({
  markets: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['select'])

function formatDate(date) {
  if (!date) return 'N/A'
  return new Date(date).toLocaleDateString()
}

function formatCurrency(value) {
  if (value === undefined || value === null) return '—'
  if (value >= 1000000) return `$${(value / 1000000).toFixed(1)}M`
  if (value >= 1000) return `$${(value / 1000).toFixed(1)}K`
  return `$${value.toFixed(0)}`
}
</script>
