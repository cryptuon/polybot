export class WebSocketClient {
  constructor(url = '/ws') {
    this.url = url
    this.ws = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
    this.reconnectDelay = 1000
    this.handlers = new Map()
    this.pingInterval = null
  }

  connect() {
    return new Promise((resolve, reject) => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}${this.url}`

      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        this.reconnectAttempts = 0
        this.startPing()
        resolve()
      }

      this.ws.onclose = () => {
        this.stopPing()
        this.attemptReconnect()
      }

      this.ws.onerror = (error) => {
        reject(error)
      }

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          this.handleMessage(message)
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e)
        }
      }
    })
  }

  disconnect() {
    this.stopPing()
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  send(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message))
    }
  }

  subscribe(channels) {
    this.send({ type: 'subscribe', channels })
  }

  unsubscribe(channels) {
    this.send({ type: 'unsubscribe', channels })
  }

  on(event, handler) {
    if (!this.handlers.has(event)) {
      this.handlers.set(event, [])
    }
    this.handlers.get(event).push(handler)
  }

  off(event, handler) {
    if (this.handlers.has(event)) {
      const handlers = this.handlers.get(event)
      const index = handlers.indexOf(handler)
      if (index > -1) {
        handlers.splice(index, 1)
      }
    }
  }

  handleMessage(message) {
    const { type, channel, data } = message

    // Handle system messages
    if (type) {
      const handlers = this.handlers.get(type) || []
      handlers.forEach((handler) => handler(message))
    }

    // Handle channel messages
    if (channel) {
      const handlers = this.handlers.get(channel) || []
      handlers.forEach((handler) => handler(data))
    }
  }

  startPing() {
    this.pingInterval = setInterval(() => {
      this.send({ type: 'ping' })
    }, 30000)
  }

  stopPing() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
      this.pingInterval = null
    }
  }

  attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)

      setTimeout(() => {
        this.connect().catch(() => {
          // Reconnection failed, will try again
        })
      }, delay)
    }
  }

  get isConnected() {
    return this.ws && this.ws.readyState === WebSocket.OPEN
  }
}

export default new WebSocketClient()
