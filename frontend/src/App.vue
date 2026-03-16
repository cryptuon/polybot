<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Navigation -->
    <nav class="bg-white border-b border-gray-200">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between h-16">
          <div class="flex">
            <!-- Logo -->
            <div class="flex-shrink-0 flex items-center">
              <span class="text-xl font-bold text-primary-600">PolyBot</span>
            </div>

            <!-- Navigation Links -->
            <div class="hidden sm:ml-8 sm:flex sm:space-x-4">
              <router-link
                v-for="link in navLinks"
                :key="link.to"
                :to="link.to"
                class="inline-flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-colors"
                :class="[
                  $route.path === link.to
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                ]"
              >
                {{ link.name }}
              </router-link>
            </div>
          </div>

          <!-- Status Indicator -->
          <div class="flex items-center space-x-4">
            <div class="flex items-center space-x-2">
              <span
                class="h-2 w-2 rounded-full"
                :class="connected ? 'bg-success-500' : 'bg-danger-500'"
              ></span>
              <span class="text-sm text-gray-600">
                {{ connected ? 'Connected' : 'Disconnected' }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </nav>

    <!-- Alert Banner -->
    <AlertBanner v-if="alerts.length > 0" :alerts="alerts" @dismiss="dismissAlert" />

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useWebSocketStore } from './stores/websocket'
import { storeToRefs } from 'pinia'
import AlertBanner from './components/AlertBanner.vue'

const wsStore = useWebSocketStore()
const { connected, alerts } = storeToRefs(wsStore)

const navLinks = [
  { name: 'Dashboard', to: '/' },
  { name: 'Markets', to: '/markets' },
  { name: 'Strategies', to: '/strategies' },
  { name: 'Positions', to: '/positions' },
  { name: 'Shadow', to: '/shadow' },
  { name: 'Analytics', to: '/analytics' },
  { name: 'Logs', to: '/strategy-logs' },
  { name: 'Settings', to: '/settings' },
]

function dismissAlert(index) {
  wsStore.dismissAlert(index)
}

onMounted(() => {
  wsStore.connect()
})

onUnmounted(() => {
  wsStore.disconnect()
})
</script>
