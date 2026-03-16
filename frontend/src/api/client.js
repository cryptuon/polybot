import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Markets
export const markets = {
  list: (params = {}) => api.get('/markets', { params }),
  get: (id) => api.get(`/markets/${id}`),
  getOrderbook: (marketId, tokenId) => api.get(`/markets/${marketId}/orderbook`, { params: { token: tokenId } }),
}

// Strategies
export const strategies = {
  list: () => api.get('/strategies'),
  get: (name) => api.get(`/strategies/${name}`),
  update: (name, config) => api.put(`/strategies/${name}`, config),
  toggle: (name, enabled) => api.post(`/strategies/${name}/toggle`, { enabled }),
  toggleShadow: (name, shadow) => api.post(`/strategies/${name}/shadow`, { shadow }),
  // Runtime control
  runnerStatus: () => api.get('/strategies/runner/status'),
  start: (name) => api.post(`/strategies/${name}/start`),
  stop: (name) => api.post(`/strategies/${name}/stop`),
  restart: (name) => api.post(`/strategies/${name}/restart`),
  startAll: () => api.post('/strategies/runner/start-all'),
  stopAll: () => api.post('/strategies/runner/stop-all'),
}

// Orders
export const orders = {
  list: (params = {}) => api.get('/orders', { params }),
  get: (id) => api.get(`/orders/${id}`),
  create: (order) => api.post('/orders', order),
  cancel: (id) => api.delete(`/orders/${id}`),
}

// Positions
export const positions = {
  list: (params = {}) => api.get('/positions', { params }),
  get: (id) => api.get(`/positions/${id}`),
  close: (id) => api.post(`/positions/${id}/close`),
}

// Analytics
export const analytics = {
  summary: (params = {}) => api.get('/analytics/summary', { params }),
  history: (params = {}) => api.get('/analytics/history', { params }),
  prices: (marketId, params = {}) => api.get(`/analytics/prices/${marketId}`, { params }),
  strategies: (params = {}) => api.get('/analytics/strategies', { params }),
  correlations: (marketId, params = {}) => api.get(`/analytics/correlations/${marketId}`, { params }),
  trades: (params = {}) => api.get('/analytics/trades', { params }),
}

// Settings
export const settings = {
  get: () => api.get('/settings'),
  update: (data) => api.put('/settings', data),
  risk: () => api.get('/settings/risk'),
  system: () => api.get('/settings/system'),
  reload: () => api.post('/settings/reload'),
}

// Strategy Logs
export const strategyLogs = {
  logs: (strategy, params = {}) => api.get(`/strategy-logs/${strategy}/logs`, { params }),
  allLogs: (params = {}) => api.get('/strategy-logs/all/logs', { params }),
  runs: (strategy, params = {}) => api.get(`/strategy-logs/${strategy}/runs`, { params }),
  allRuns: (params = {}) => api.get('/strategy-logs/all/runs', { params }),
  currentRun: (strategy) => api.get(`/strategy-logs/${strategy}/runs/current`),
  scans: (strategy, params = {}) => api.get(`/strategy-logs/${strategy}/scans`, { params }),
}

// Shadow Trading
export const shadow = {
  summary: () => api.get('/shadow/summary'),
  stats: (strategy = null) => api.get('/shadow/stats', { params: { strategy } }),
  positions: (strategy = null) => api.get('/shadow/positions', { params: { strategy } }),
  trades: (strategy = null, limit = 100) => api.get('/shadow/trades', { params: { strategy, limit } }),
  performance: () => api.get('/shadow/performance'),
  reset: (strategy = null) => api.post('/shadow/reset', null, { params: { strategy } }),
  strategyStats: (strategy) => api.get(`/shadow/strategies/${strategy}/stats`),
  strategyPositions: (strategy) => api.get(`/shadow/strategies/${strategy}/positions`),
  strategyTrades: (strategy, limit = 100) => api.get(`/shadow/strategies/${strategy}/trades`, { params: { limit } }),
}

export default api
