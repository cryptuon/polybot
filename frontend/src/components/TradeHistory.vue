<template>
  <div>
    <div v-if="days.length === 0" class="text-gray-500 text-center py-4">
      No trade history available
    </div>
    <div v-else class="overflow-x-auto">
      <table class="min-w-full">
        <thead>
          <tr class="text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
            <th class="pb-3 pr-4">Date</th>
            <th class="pb-3 px-4">Strategy</th>
            <th class="pb-3 px-4">Trades</th>
            <th class="pb-3 px-4">Wins</th>
            <th class="pb-3 px-4">Losses</th>
            <th class="pb-3 px-4">P&L</th>
            <th class="pb-3 px-4">Volume</th>
            <th class="pb-3 pl-4">Fees</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          <tr v-for="day in days" :key="`${day.date}-${day.strategy}`" class="hover:bg-gray-50">
            <td class="py-3 pr-4 font-medium">{{ formatDate(day.date) }}</td>
            <td class="py-3 px-4">
              <span class="badge badge-primary">{{ day.strategy || 'all' }}</span>
            </td>
            <td class="py-3 px-4">{{ day.trades }}</td>
            <td class="py-3 px-4 text-success-600">{{ day.wins }}</td>
            <td class="py-3 px-4 text-danger-600">{{ day.losses }}</td>
            <td class="py-3 px-4">
              <span
                class="font-medium"
                :class="day.pnl >= 0 ? 'text-success-600' : 'text-danger-600'"
              >
                {{ formatCurrency(day.pnl) }}
              </span>
            </td>
            <td class="py-3 px-4">${{ day.volume?.toFixed(2) || '0.00' }}</td>
            <td class="py-3 pl-4 text-gray-500">${{ day.fees?.toFixed(2) || '0.00' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
defineProps({
  days: {
    type: Array,
    default: () => [],
  },
})

function formatDate(date) {
  if (!date) return '—'
  return new Date(date).toLocaleDateString()
}

function formatCurrency(value) {
  if (value === undefined || value === null) return '$0.00'
  const sign = value >= 0 ? '+' : ''
  return `${sign}$${Math.abs(value).toFixed(2)}`
}
</script>
