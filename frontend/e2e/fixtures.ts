import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { test as base, expect, type Page } from '@playwright/test'

const PY = process.env.E2E_PYTHON ?? 'python'
const SEED = fileURLToPath(new URL('./seed.py', import.meta.url))

export type Creds = { email: string; password: string; teammate: string }

/** Runs e2e/seed.py (mock agents over the real API) and returns its JSON output. */
export function seed(mode: 'workspace' | 'drain' = 'workspace'): any {
  return JSON.parse(execFileSync(PY, [SEED, mode], { encoding: 'utf8', env: process.env }).trim().split('\n').pop()!)
}

export async function login(page: Page, c: Creds) {
  await page.goto('/login')
  await page.fill('input[type=email]', c.email)
  await page.fill('input[type=password]', c.password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForURL('/')
}

export const nav = (page: Page, label: string) => page.locator('nav').getByText(label, { exact: true }).click()

export async function requestChanges(page: Page, title: string, comment: string) {
  await nav(page, 'Approval center')
  await page.locator('button.card', { hasText: title }).click()
  await page.getByPlaceholder('Comment (optional)').fill(comment)
  await page.getByRole('button', { name: 'Request changes' }).click()
  await expect(page.locator('button.card', { hasText: title })).toHaveCount(0)
}

/** Fails the test on any uncaught page error or console error. HTTP error statuses are asserted
 * through the UI instead (the browser logs every 4xx as "Failed to load resource"). */
export const test = base.extend<{ creds: Creds; jsErrors: string[] }>({
  creds: async ({}, use) => { await use(seed('workspace')) },
  jsErrors: [async ({ page }, use) => {
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(String(e)))
    page.on('console', (m) => {
      if (m.type() === 'error' && !m.text().startsWith('Failed to load resource')) errors.push(m.text())
    })
    await use(errors)
    expect(errors, 'browser JS errors').toEqual([])
  }, { auto: true }],
})
export { expect }
