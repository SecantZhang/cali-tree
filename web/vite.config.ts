import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // e2e/specs/*.spec.ts are Playwright tests (run via `npm run test:e2e`), not vitest's —
    // vitest's default include glob matches them too and errors on the bare test.describe().
    exclude: ['**/node_modules/**', 'e2e/**'],
  },
})
