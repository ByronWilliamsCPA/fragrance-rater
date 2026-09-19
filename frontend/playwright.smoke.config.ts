import { defineConfig } from '@playwright/test'

// #ASSUME: external-resources: docker-compose.yml (repo root) publishes the
// backend "app" service on ${APP_PORT:-8000}:8000, not 8080. The task brief
// that seeded this file guessed 8080 (matching neither docker-compose.yml
// nor frontend/package.json's own `generate-client` script, which already
// points at http://localhost:8000). The default below was corrected to
// match the real stack; SMOKE_BASE_URL still overrides it for any
// environment that fronts the backend on a different port.
// #VERIFY: re-check docker-compose.yml's app.ports mapping if this default
// ever drifts from the real published port.
export default defineConfig({
  testDir: './e2e-smoke',
  fullyParallel: false,
  retries: 1,
  workers: 1,
  reporter: [['github'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.SMOKE_BASE_URL || 'http://localhost:8000',
  },
})
