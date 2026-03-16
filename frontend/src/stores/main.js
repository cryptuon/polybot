import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { markets, strategies, positions, orders, analytics, settings } from '../api/client'

export const useMainStore = defineStore('main', () => {
  // State
  const marketList = ref([])
  const strategyList = ref([])
  const positionList = ref([])
  const orderList = ref([])
  const performanceSummary = ref(null)
  const currentSettings = ref(null)
  const systemStatus = ref(null)
  const riskStatus = ref(null)
  const loading = ref({
    markets: false,
    strategies: false,
    positions: false,
    orders: false,
    analytics: false,
    settings: false,
  })
  const error = ref(null)

  // Getters
  const activePositions = computed(() =>
    positionList.value.filter((p) => !p.closed_at)
  )

  const openOrders = computed(() =>
    orderList.value.filter((o) => o.status === 'OPEN' || o.status === 'PENDING')
  )

  const enabledStrategies = computed(() =>
    strategyList.value.filter((s) => s.enabled)
  )

  const totalPnl = computed(() => {
    if (!performanceSummary.value) return 0
    return performanceSummary.value.total_pnl || 0
  })

  const winRate = computed(() => {
    if (!performanceSummary.value) return 0
    return performanceSummary.value.win_rate || 0
  })

  // Actions
  async function fetchMarkets(params = {}) {
    loading.value.markets = true
    try {
      const response = await markets.list(params)
      marketList.value = response.data.markets || []
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value.markets = false
    }
  }

  async function fetchStrategies() {
    loading.value.strategies = true
    try {
      const response = await strategies.list()
      strategyList.value = response.data.strategies || []
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value.strategies = false
    }
  }

  async function fetchPositions(params = {}) {
    loading.value.positions = true
    try {
      const response = await positions.list(params)
      positionList.value = response.data.positions || []
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value.positions = false
    }
  }

  async function fetchOrders(params = {}) {
    loading.value.orders = true
    try {
      const response = await orders.list(params)
      orderList.value = response.data.orders || []
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value.orders = false
    }
  }

  async function fetchAnalytics(params = {}) {
    loading.value.analytics = true
    try {
      const response = await analytics.summary(params)
      performanceSummary.value = response.data
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value.analytics = false
    }
  }

  async function fetchSettings() {
    loading.value.settings = true
    try {
      const [settingsRes, riskRes, systemRes] = await Promise.all([
        settings.get(),
        settings.risk(),
        settings.system(),
      ])
      currentSettings.value = settingsRes.data
      riskStatus.value = riskRes.data
      systemStatus.value = systemRes.data
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value.settings = false
    }
  }

  async function toggleStrategy(name) {
    try {
      // Find current state and toggle it
      const strategy = strategyList.value.find((s) => s.name === name)
      const newEnabled = strategy ? !strategy.enabled : true

      const response = await strategies.toggle(name, newEnabled)
      // Update local state
      const index = strategyList.value.findIndex((s) => s.name === name)
      if (index !== -1) {
        strategyList.value[index] = response.data
      }
      return response.data
    } catch (e) {
      error.value = e.message
      throw e
    }
  }

  async function createOrder(orderData) {
    try {
      const response = await orders.create(orderData)
      orderList.value.unshift(response.data)
      return response.data
    } catch (e) {
      error.value = e.message
      throw e
    }
  }

  async function cancelOrder(orderId) {
    try {
      await orders.cancel(orderId)
      const index = orderList.value.findIndex((o) => o.id === orderId)
      if (index !== -1) {
        orderList.value[index].status = 'CANCELLED'
      }
    } catch (e) {
      error.value = e.message
      throw e
    }
  }

  async function closePosition(positionId) {
    try {
      const response = await positions.close(positionId)
      const index = positionList.value.findIndex((p) => p.id === positionId)
      if (index !== -1) {
        positionList.value[index] = response.data
      }
      return response.data
    } catch (e) {
      error.value = e.message
      throw e
    }
  }

  async function updateSettings(data) {
    try {
      const response = await settings.update(data)
      currentSettings.value = response.data
      return response.data
    } catch (e) {
      error.value = e.message
      throw e
    }
  }

  function clearError() {
    error.value = null
  }

  return {
    // State
    marketList,
    strategyList,
    positionList,
    orderList,
    performanceSummary,
    currentSettings,
    systemStatus,
    riskStatus,
    loading,
    error,
    // Getters
    activePositions,
    openOrders,
    enabledStrategies,
    totalPnl,
    winRate,
    // Actions
    fetchMarkets,
    fetchStrategies,
    fetchPositions,
    fetchOrders,
    fetchAnalytics,
    fetchSettings,
    toggleStrategy,
    createOrder,
    cancelOrder,
    closePosition,
    updateSettings,
    clearError,
  }
})
