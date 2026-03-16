<template>
  <div class="bg-white border-b border-gray-200">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div
        v-for="(alert, index) in visibleAlerts"
        :key="alert.id"
        class="py-2 flex items-center justify-between"
        :class="alertClasses(alert.type)"
      >
        <div class="flex items-center space-x-3">
          <span class="font-medium">{{ alert.title }}</span>
          <span class="text-sm opacity-80">{{ alert.message }}</span>
        </div>
        <button
          @click="$emit('dismiss', index)"
          class="opacity-60 hover:opacity-100"
        >
          <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  alerts: {
    type: Array,
    default: () => [],
  },
})

defineEmits(['dismiss'])

const visibleAlerts = computed(() =>
  props.alerts.filter((a) => !a.dismissed).slice(0, 3)
)

function alertClasses(type) {
  const classes = {
    success: 'bg-success-50 text-success-600',
    danger: 'bg-danger-50 text-danger-600',
    warning: 'bg-warning-50 text-warning-600',
    info: 'bg-primary-50 text-primary-600',
  }
  return classes[type] || classes.info
}
</script>
