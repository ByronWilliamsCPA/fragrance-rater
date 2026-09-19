import path from 'node:path'
import react from '@vitejs/plugin-react-swc'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      // Proxy API requests to backend during development
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
      '/openapi.json': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    // Playwright's own spec files live under e2e/ and e2e-smoke/ and match
    // Vitest's default `*.spec.ts` include glob; without this exclude,
    // Vitest tries to import and collect them, and errors on the first
    // `test.describe()` call since that's Playwright's test runner, not
    // Vitest's.
    exclude: ['**/node_modules/**', 'e2e/**', 'e2e-smoke/**'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html', 'lcov'],
      exclude: ['node_modules/', 'src/test/', 'src/client/', '**/*.d.ts', '**/*.config.*'],
    },
  },
})
