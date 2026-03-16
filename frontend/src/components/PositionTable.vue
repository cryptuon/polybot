<template>
  <div>
    <div v-if="loading" class="text-gray-500 text-center py-8">
      Loading positions...
    </div>
    <div v-else-if="positions.length === 0" class="text-gray-500 text-center py-8">
      No positions found
    </div>
    <div v-else class="overflow-x-auto">
      <table class="min-w-full">
        <thead>
          <tr class="text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
            <th class="pb-3 pr-4">Market</th>
            <th class="pb-3 px-4">Side</th>
            <th class="pb-3 px-4">Size</th>
            <th class="pb-3 px-4">Entry</th>
            <th class="pb-3 px-4">Current</th>
            <th class="pb-3 px-4">P&L</th>
            <th class="pb-3 px-4">Strategy</th>
            <th v-if="showActions" class="pb-3 pl-4"></th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          <tr
            v-for="position in positions"
            :key="position.id"
            class="hover:bg-gray-50"
          >
            <td class="py-4 pr-4">
              <div class="font-mono text-sm">{{ truncateId(position.market_id) }}</div>
            </td>
            <td class="py-4 px-4">
              <span
                class="badge"
                :class="position.side === 'YES' ? 'badge-success' : 'badge-danger'"
              >
                {{ position.side }}
              </span>
            </td>
            <td class="py-4 px-4 font-medium">{{ position.size?.toFixed(2) }}</td>
            <td class="py-4 px-4">${{ position.entry_price?.toFixed(3) }}</td>
            <td class="py-4 px-4">${{ position.current_price?.toFixed(3) || '—' }}</td>
            <td class="py-4 px-4">
              <span
                class="font-medium"
                :class="getPnlClass(position)"
              >
                {{ formatPnl(position) }}
              </span>
            </td>
            <td class="py-4 px-4">
              <span class="badge badge-primary">{{ position.strategy }}</span>
            </td>
            <td v-if="showActions" class="py-4 pl-4">
              <button
                v-if="!position.closed_at"
                @click="$emit('close', position.id)"
                class="text-danger-600 hover:text-danger-700 text-sm"
              >
                Close
              </button>
              <span v-else class="text-gray-400 text-sm">Closed</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
defineProps({
  positions: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
  showActions: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['close'])

function truncateId(id) {
  if (!id) return '—'
  return `${id.slice(0, 8)}...${id.slice(-4)}`
}

function getPnlClass(position) {
  const pnl = position.pnl || position.unrealized_pnl || 0
  return pnl >= 0 ? 'text-success-600' : 'text-danger-600'
}

function formatPnl(position) {
  const pnl = position.pnl || position.unrealized_pnl || 0
  const sign = pnl >= 0 ? '+' : ''
  return `${sign}$${Math.abs(pnl).toFixed(2)}`
}
</script>
