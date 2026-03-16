<template>
  <div class="h-64">
    <Line v-if="type === 'pnl'" :data="pnlChartData" :options="chartOptions" />
    <Bar v-else-if="type === 'trades'" :data="tradesChartData" :options="chartOptions" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import { Line, Bar } from 'vue-chartjs'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

const props = defineProps({
  type: {
    type: String,
    required: true,
    validator: (v) => ['pnl', 'trades'].includes(v),
  },
  data: {
    type: Array,
    default: () => [],
  },
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: false,
    },
  },
  scales: {
    x: {
      grid: {
        display: false,
      },
    },
    y: {
      grid: {
        color: '#f3f4f6',
      },
    },
  },
}

const pnlChartData = computed(() => {
  const sortedData = [...props.data].sort(
    (a, b) => new Date(a.date) - new Date(b.date)
  )

  // Calculate cumulative P&L
  let cumulative = 0
  const cumulativePnl = sortedData.map((d) => {
    cumulative += d.pnl || 0
    return cumulative
  })

  return {
    labels: sortedData.map((d) => formatDate(d.date)),
    datasets: [
      {
        label: 'Cumulative P&L',
        data: cumulativePnl,
        borderColor: cumulativePnl[cumulativePnl.length - 1] >= 0 ? '#22c55e' : '#ef4444',
        backgroundColor: cumulativePnl[cumulativePnl.length - 1] >= 0
          ? 'rgba(34, 197, 94, 0.1)'
          : 'rgba(239, 68, 68, 0.1)',
        fill: true,
        tension: 0.4,
      },
    ],
  }
})

const tradesChartData = computed(() => {
  const sortedData = [...props.data].sort(
    (a, b) => new Date(a.date) - new Date(b.date)
  )

  return {
    labels: sortedData.map((d) => formatDate(d.date)),
    datasets: [
      {
        label: 'Wins',
        data: sortedData.map((d) => d.wins || 0),
        backgroundColor: '#22c55e',
      },
      {
        label: 'Losses',
        data: sortedData.map((d) => d.losses || 0),
        backgroundColor: '#ef4444',
      },
    ],
  }
})

function formatDate(date) {
  if (!date) return ''
  const d = new Date(date)
  return `${d.getMonth() + 1}/${d.getDate()}`
}
</script>
