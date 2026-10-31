import { defineConfig, devices } from '@playwright/test'

/*
 * The real-stack tier: a browser, the built frontend, the forward-auth stub
 * (the production edge's trust boundary), and the REAL backend on a real
 * PostgreSQL. The mocked tier (`e2e/`) proves the frontend renders what it is
 * told; this proves the whole path works, including what the edge strips and
 * injects. It needs a running backend (`BACKEND_URL`, default
 * http://127.0.0.1:8000) with the manager username below in its
 * CALIBRATION_ADMIN_USERNAMES, and a built `dist/`.
 *
 * Run: npm run build && npm run test:e2e:stack
 */
const port = Number(process.env.STACK_PORT ?? 8080)

export default defineConfig({
  testDir: './e2e-stack',
  // The specs share one database and create uniquely named rows, but they are
  // few and ordered by intent, so run them one at a time and stay deterministic.
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'node e2e-stack/forward-auth-stub.mjs',
    url: `http://127.0.0.1:${port}/__stub/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
})
