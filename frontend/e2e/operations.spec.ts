import { expect, login, nav, test } from './fixtures'

test('operations page shows real agent state from the backend', async ({ page, creds }) => {
  await login(page, creds)
  await nav(page, 'Operations')
  await expect(page.getByRole('heading', { name: 'Operations' })).toBeVisible()
  // Both agents are always listed; values come from dashboard/operations/ (no client-side metrics).
  await expect(page.getByRole('region', { name: 'Agent 1 · SaaS research' })).toBeVisible()
  const a2 = page.getByRole('region', { name: 'Agent 2 · Local leads' })
  await expect(a2).toBeVisible()
  await expect(a2.getByText('Last successful run')).toBeVisible()
  await expect(a2.getByText('Businesses found')).toBeVisible()
})
