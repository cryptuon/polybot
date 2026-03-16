import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('./views/Home.vue'),
  },
  {
    path: '/markets',
    name: 'markets',
    component: () => import('./views/Markets.vue'),
  },
  {
    path: '/strategies',
    name: 'strategies',
    component: () => import('./views/Strategies.vue'),
  },
  {
    path: '/positions',
    name: 'positions',
    component: () => import('./views/Positions.vue'),
  },
  {
    path: '/analytics',
    name: 'analytics',
    component: () => import('./views/Analytics.vue'),
  },
  {
    path: '/strategy-logs',
    name: 'strategy-logs',
    component: () => import('./views/StrategyLogs.vue'),
  },
  {
    path: '/strategy-logs/:strategy',
    name: 'strategy-logs-detail',
    component: () => import('./views/StrategyLogs.vue'),
  },
  {
    path: '/shadow',
    name: 'shadow',
    component: () => import('./views/Shadow.vue'),
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('./views/Settings.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
