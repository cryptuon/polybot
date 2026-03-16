<template>
  <div class="card">
    <h2 class="text-lg font-semibold text-gray-900 mb-4">API Information</h2>

    <div class="space-y-4">
      <!-- API Endpoints -->
      <div>
        <div class="text-sm font-medium text-gray-700 mb-2">API Endpoints</div>
        <div class="bg-gray-50 rounded-lg p-4 space-y-2 font-mono text-sm">
          <div class="flex justify-between">
            <span class="text-gray-500">REST API:</span>
            <span>http://localhost:8000/api</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">WebSocket:</span>
            <span>ws://localhost:8000/ws</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">API Docs:</span>
            <a href="/docs" target="_blank" class="text-primary-600 hover:underline">
              /docs
            </a>
          </div>
        </div>
      </div>

      <!-- Polymarket URLs -->
      <div>
        <div class="text-sm font-medium text-gray-700 mb-2">Polymarket API</div>
        <div class="bg-gray-50 rounded-lg p-4 space-y-2 font-mono text-sm">
          <div class="flex justify-between">
            <span class="text-gray-500">CLOB:</span>
            <span>clob.polymarket.com</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">Gamma:</span>
            <span>gamma-api.polymarket.com</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">Data:</span>
            <span>data-api.polymarket.com</span>
          </div>
        </div>
      </div>

      <!-- Rate Limits -->
      <div>
        <div class="text-sm font-medium text-gray-700 mb-2">Rate Limits (per 10s)</div>
        <div class="grid grid-cols-2 gap-2 text-sm">
          <div class="bg-gray-50 rounded p-2 flex justify-between">
            <span class="text-gray-500">CLOB General:</span>
            <span class="font-medium">9,000</span>
          </div>
          <div class="bg-gray-50 rounded p-2 flex justify-between">
            <span class="text-gray-500">CLOB Book:</span>
            <span class="font-medium">1,500</span>
          </div>
          <div class="bg-gray-50 rounded p-2 flex justify-between">
            <span class="text-gray-500">Order POST:</span>
            <span class="font-medium">3,500</span>
          </div>
          <div class="bg-gray-50 rounded p-2 flex justify-between">
            <span class="text-gray-500">Order DELETE:</span>
            <span class="font-medium">3,000</span>
          </div>
          <div class="bg-gray-50 rounded p-2 flex justify-between">
            <span class="text-gray-500">Gamma Events:</span>
            <span class="font-medium">300</span>
          </div>
          <div class="bg-gray-50 rounded p-2 flex justify-between">
            <span class="text-gray-500">Data Trades:</span>
            <span class="font-medium">200</span>
          </div>
        </div>
      </div>

      <!-- Quick Links -->
      <div>
        <div class="text-sm font-medium text-gray-700 mb-2">Resources</div>
        <div class="flex flex-wrap gap-2">
          <a
            href="https://docs.polymarket.com"
            target="_blank"
            class="btn btn-secondary text-sm"
          >
            Polymarket Docs
          </a>
          <a
            href="https://polymarket.com"
            target="_blank"
            class="btn btn-secondary text-sm"
          >
            Polymarket
          </a>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// Static component, no logic needed
</script>
