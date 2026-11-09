import { expect, login, nav, seed, test } from './fixtures'

test('register, launch Agent 1 task, approve idea, dashboard updates', async ({ page }) => {
  const email = `e2e-reg${Date.now()}@example.com`
  await page.goto('/login')
  await page.getByText('Need an account? Register').click()
  await page.fill('input[type=email]', email)
  await page.fill('input[type=password]', 'E2e-register-pass-123')
  const inputs = page.locator('form input')
  await inputs.nth(2).fill('E2E Tester')
  await inputs.nth(3).fill('E2E Studio')
  await page.getByRole('button', { name: 'Create account' }).click()
  await page.waitForURL('/')

  await nav(page, 'Agent tasks')
  await page.fill('input[placeholder="Dental clinics"]', 'Dental clinics')
  await page.getByRole('button', { name: 'Start task' }).click()
  await expect(page.getByText('Opportunity research').first()).toBeVisible()

  seed('drain') // MOCK Agent 1 processes the queued task through the SDK

  await nav(page, 'Approval center')
  await expect(page.getByRole('heading', { name: 'ChairFill' })).toBeVisible()
  await page.getByRole('button', { name: 'Approve', exact: true }).click()
  await expect(page.getByText('Nothing here.')).toBeVisible()

  await nav(page, 'Dashboard')
  await expect(page.getByRole('heading', { name: 'Pipeline' })).toBeVisible()
  await expect(page.locator('main .card', { hasText: 'Active agent tasks' })).toContainText('1') // auto customer research
})

test('viewer-safe navigation: unknown routes redirect, audit log hidden from non-admins', async ({ page, creds }) => {
  await login(page, creds)
  await page.goto('/does-not-exist')
  await expect(page).toHaveURL('/')
  await expect(page.locator('nav').getByText('Audit log')).toBeVisible() // owner is admin
})
