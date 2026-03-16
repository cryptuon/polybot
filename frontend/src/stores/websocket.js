import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { WebSocketClient } from '../api/websocket'

export const useWebSocketStore = defineStore('websocket', () => {
  // State
  const client = ref(null)
  const connected = ref(false)
  const prices = ref({})
  const alerts = ref([])
  const recentEvents = ref([])
  const subscribedChannels = ref([])

  // Getters
  const priceForMarket = computed(() => (marketId) => {
    return prices.value[marketId] || null
  })

  const unreadAlerts = computed(() => {
    return alerts.value.filter((a) => !a.dismissed)
  })

  // Actions
  function connect() {
    client.value = new WebSocketClient()

    client.value.on('subscribed', (message) => {
      subscribedChannels.value = [
        ...new Set([...subscribedChannels.value, ...message.channels]),
      ]
    })

    client.value.on('unsubscribed', (message) => {
      subscribedChannels.value = subscribedChannels.value.filter(
        (c) => !message.channels.includes(c)
      )
    })

    client.value.on('prices', (data) => {
      if (data.market_id) {
        prices.value[data.market_id] = {
          bid: data.bid,
          ask: data.ask,
          mid: data.mid,
          timestamp: data.timestamp,
        }
      }
    })

    client.value.on('events', (data) => {
      // Skip heartbeat messages - they have 'type: heartbeat' not 'type: event'
      if (data.type === 'heartbeat') {
        return
      }

      // Normalize the event structure
      const event = {
        source: data.source || data.service || 'unknown',
        event_type: data.event_type || data.type || 'unknown',
        data: data.data || {},
        timestamp: data.timestamp,
        receivedAt: new Date().toISOString(),
      }

      recentEvents.value.unshift(event)

      // Keep only last 100 events
      if (recentEvents.value.length > 100) {
        recentEvents.value = recentEvents.value.slice(0, 100)
      }

      // Handle alert events
      if (event.event_type === 'alert' || event.event_type === 'error') {
        addAlert({
          type: event.event_type === 'error' ? 'danger' : 'warning',
          title: event.source || 'System',
          message: event.data?.message || JSON.stringify(event.data),
        })
      }

      // Handle order/trade events
      if (event.event_type === 'order_filled' || event.event_type === 'trade_executed') {
        addAlert({
          type: 'success',
          title: event.event_type === 'order_filled' ? 'Order Filled' : 'Trade Executed',
          message: `${event.data?.side} ${event.data?.size} @ ${event.data?.price}`,
        })
      }
    })

    client.value.on('error', (message) => {
      addAlert({
        type: 'danger',
        title: 'WebSocket Error',
        message: message.message,
      })
    })

    return client.value
      .connect()
      .then(() => {
        connected.value = true
        // Subscribe to default channels
        subscribe(['prices', 'events'])
      })
      .catch((error) => {
        connected.value = false
        console.error('WebSocket connection failed:', error)
      })
  }

  function disconnect() {
    if (client.value) {
      client.value.disconnect()
      connected.value = false
    }
  }

  function subscribe(channels) {
    if (client.value && connected.value) {
      client.value.subscribe(channels)
    }
  }

  function unsubscribe(channels) {
    if (client.value && connected.value) {
      client.value.unsubscribe(channels)
    }
  }

  function addAlert(alert) {
    alerts.value.unshift({
      ...alert,
      id: Date.now(),
      createdAt: new Date().toISOString(),
      dismissed: false,
    })

    // Keep only last 50 alerts
    if (alerts.value.length > 50) {
      alerts.value = alerts.value.slice(0, 50)
    }
  }

  function dismissAlert(index) {
    if (alerts.value[index]) {
      alerts.value[index].dismissed = true
    }
  }

  function clearAlerts() {
    alerts.value = []
  }

  return {
    // State
    connected,
    prices,
    alerts,
    recentEvents,
    subscribedChannels,
    // Getters
    priceForMarket,
    unreadAlerts,
    // Actions
    connect,
    disconnect,
    subscribe,
    unsubscribe,
    addAlert,
    dismissAlert,
    clearAlerts,
  }
})
