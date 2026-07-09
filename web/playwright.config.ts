import { defineConfig, devices } from '@playwright/test'

// Backend port is baked into the frontend build via VITE_API_BASE_URL (see
// e2e/global-setup.ts's comment) — run/run_e2e_tests.sh sets it before `npm run build`.
const FRONTEND_PORT = 5183

export default defineConfig({
  testDir: './e2e/specs',
  globalSetup: './e2e/global-setup.ts',
  globalTeardown: './e2e/global-teardown.ts',
  // One shared backend + mock gateway for the whole run (started once in global setup),
  // so specs run sequentially rather than racing each other against that shared state.
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: `http://127.0.0.1:${FRONTEND_PORT}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: {
    // Requires a prior `npm run build` (run_e2e_tests.sh does this) — previewing the
    // production build is more representative than the dev server for E2E purposes.
    command: `npm run preview -- --host 127.0.0.1 --port ${FRONTEND_PORT} --strictPort`,
    url: `http://127.0.0.1:${FRONTEND_PORT}`,
    reuseExistingServer: false,
    timeout: 30_000,
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
})
