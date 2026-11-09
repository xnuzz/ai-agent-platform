import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { expect, login, seed, test } from './fixtures'

const PY = process.env.E2E_PYTHON ?? 'python'
const SEED = fileURLToPath(new URL('./seed.py', import.meta.url))

/** Runs the MOCK streaming Agent 2 (e2e/seed.py stream) in the background; resolves with its exit code. */
function streamAgent(): Promise<number> {
  return new Promise((resolve) => {
    const p = spawn(PY, [SEED, 'stream'], { env: process.env, stdio: 'ignore' })
    p.on('exit', (code) => resolve(code ?? 1))
  })
}

test.use({ creds: async ({}, use) => { await use(seed('empty')) } })

test('Local Business Finder: configure, watch live discoveries, review and approve', async ({ page, creds }) => {
  test.setTimeout(120_000)
  await login(page, creds)
  await page.locator('nav').getByText('Local Business Finder', { exact: true }).click()
  await expect(page).toHaveURL('/local-finder')
  await expect(page.getByText('No businesses discovered yet')).toBeVisible()
  await expect(page.getByTestId('agent-state')).toHaveText(/Idle/i)

  // ---- configure + start (real POST research-tasks/)
  await page.getByRole('button', { name: 'Configure research' }).click()
  await page.selectOption('#cfg-country', 'BG')
  await page.fill('#cfg-city', 'Sofia')
  await page.getByRole('button', { name: '+ Restaurant' }).click()
  await page.getByRole('checkbox', { name: /Online booking/ }).click()
  await page.getByRole('button', { name: 'Start research' }).click()
  await expect(page.getByTestId('agent-state')).toHaveText(/Waiting for agent/i)

  // ---- mock agent streams 3 batches; the UI picks them up by polling
  const agent = streamAgent()
  await expect(page.getByTestId('agent-state')).toHaveText(/Scanning/i, { timeout: 15_000 })
  await expect(page.getByText('LIVE SCANNING')).toBeVisible()
  await expect(page.getByTestId('toast').filter({ hasText: 'E2E Bella Restaurant' })).toBeVisible({ timeout: 15_000 })
  await expect(page.getByTestId('toast').first()).toContainText('New business discovered')
  await expect(page.locator('.lbf-pin, .lbf-cluster-pin').first()).toBeVisible()
  await expect(page.getByTestId('agent-state')).toHaveText(/Completed/i, { timeout: 30_000 })
  expect(await agent).toBe(0)

  // ---- counters, list and "no coordinates" handling (no invented positions)
  await expect(page.getByTestId('visible-count')).toHaveText('4')
  await expect(page.getByTestId('kpi-discovered').locator('[data-value]')).toHaveText('4')
  await expect(page.getByTestId('kpi-qualified').locator('[data-value]')).toHaveText('3')
  await expect(page.getByTestId('kpi-high').locator('[data-value]')).toHaveText('2')
  await expect(page.getByTestId('unmapped-note')).toContainText('1 without coordinates')
  await expect(page.locator('[data-card]', { hasText: 'E2E Lyulin Pharmacy' })).toContainText('no map pin')
  await expect(page.getByTestId('progress-pct')).toHaveText('100%')

  // ---- filters + search
  await page.getByRole('radio', { name: /High potential/ }).click()
  await expect(page.locator('[data-card]')).toHaveCount(2)
  await page.getByRole('radio', { name: /All leads/ }).click()
  await page.getByPlaceholder('Search name, category, problem…').fill('dentist')
  await expect(page.locator('[data-card]')).toHaveCount(1)
  await page.getByPlaceholder('Search name, category, problem…').fill('')

  // ---- select → map popup → detail workspace
  await page.locator('[data-card]', { hasText: 'E2E Bella Restaurant' }).click()
  const popup = page.getByTestId('business-popup')
  await expect(popup).toContainText('E2E Bella Restaurant')
  await expect(page.locator('.lbf-pin.is-selected')).toHaveCount(1)
  await popup.getByRole('button', { name: 'Open details' }).click()
  const panel = page.getByTestId('detail-panel')
  await expect(panel).toContainText('42.69332, 23.32144')
  await panel.getByRole('tab', { name: 'Website analysis' }).click()
  await expect(panel).toContainText('No viewport meta tag')
  await expect(panel).toContainText('1 of 8 sampled links')
  await panel.getByRole('tab', { name: 'Opportunity' }).click()
  await expect(panel).toContainText('No online booking or reservation option')
  await panel.getByRole('tab', { name: 'Project' }).click()
  await expect(panel).toContainText('20–40 h')

  // Approve lead = approve the project brief; Approve outreach = approve the campaign (real decide endpoint)
  await page.getByTestId('approve-lead').click()
  await expect(panel).toContainText('Lead approved — project brief APPROVED.')
  await panel.getByRole('tab', { name: 'Outreach' }).click()
  await panel.getByRole('button', { name: 'Approve outreach' }).click()
  await expect(panel).toContainText('Outreach approved.')
  await page.keyboard.press('Escape')
  await expect(page.locator('[data-card]', { hasText: 'E2E Bella Restaurant' })).toContainText('Approved')

  // Request more research needs a comment, then returns the brief (CHANGES_REQUESTED → "Reviewed")
  await page.getByRole('button', { name: 'Open details for E2E Vitosha Dental' }).click()
  await page.getByTestId('request-more').click()
  await expect(panel).toContainText('Describe what more research is needed')
  await panel.getByLabel('Decision comment').fill('Check whether they already use a booking provider.')
  await page.getByTestId('request-more').click()
  await expect(panel).toContainText('More research requested')
  await page.keyboard.press('Escape')
  await expect(page.locator('[data-card]', { hasText: 'E2E Vitosha Dental' })).toContainText('Reviewed')

  // Agent-disqualified lead without a brief: Approve is unavailable (explained), Reject archives after confirm
  await page.getByRole('button', { name: 'Open details for E2E Studio Cut' }).click()
  await expect(page.getByTestId('approve-lead')).toBeDisabled()
  await expect(panel).toContainText('Agent 2 disqualified this lead')
  await page.getByTestId('reject-lead').click()
  await page.getByRole('button', { name: 'Confirm: archive lead' }).click()
  await expect(panel).toContainText('Lead archived.')
  await page.keyboard.press('Escape')
  await page.getByRole('radio', { name: /Rejected/ }).click()
  await expect(page.locator('[data-card]')).toHaveCount(1)
  await expect(page.locator('[data-card]')).toContainText('E2E Studio Cut')
})
