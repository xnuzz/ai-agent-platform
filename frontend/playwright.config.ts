import { defineConfig, devices } from '@playwright/test'

/**
 * Browser e2e suite. Starts the real Django API and the Vite dev server, seeds data through the
 * real API with MOCK agents (tests/support/bundles.py) — see e2e/seed.py.
 * Requires: Postgres reachable via DATABASE_URL (migrated), backend Python deps + platform_sdk importable.
 */
const API_PORT = Number(process.env.E2E_API_PORT ?? 8000)
const WEB_PORT = Number(process.env.E2E_WEB_PORT ?? 5173)
const PY = process.env.E2E_PYTHON ?? 'python'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1, // mock agents claim tasks FIFO across workspaces; keep runs sequential
  retries: 0,
  timeout: 60_000,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: 'off',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1400, height: 1000 } } }],
  webServer: [
    {
      command: `${PY} manage.py runserver 127.0.0.1:${API_PORT} --noreload`,
      cwd: '../backend',
      url: `http://127.0.0.1:${API_PORT}/healthz`,
      reuseExistingServer: !process.env.CI,
      env: { DJANGO_DEBUG: 'true', CELERY_TASK_ALWAYS_EAGER: 'true', CORS_ALLOWED_ORIGINS: `http://localhost:${WEB_PORT}` },
      timeout: 60_000,
    },
    {
      command: `npx vite --port ${WEB_PORT} --strictPort`,
      url: `http://localhost:${WEB_PORT}`,
      reuseExistingServer: !process.env.CI,
      env: { VITE_API_URL: `http://127.0.0.1:${API_PORT}` },
      timeout: 60_000,
    },
  ],
})
