import { readFileSync } from 'node:fs'
import { expect, login, nav, test } from './fixtures'

test('GDPR: export downloads JSON; erasure redacts, suppresses and is confirmed twice', async ({ page, creds }) => {
  await login(page, creds)
  await nav(page, 'Settings')
  await page.getByRole('button', { name: 'privacy' }).click()

  await page.locator('form', { hasText: 'Access request' }).getByPlaceholder('person@company.com').fill('hello@bakery.test')
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export JSON' }).click()
  const file = await (await download).path()
  const data = JSON.parse(readFileSync(file, 'utf8'))
  expect(data.leads[0].business).toBe('Corner Bakery')

  const erase = page.locator('form', { hasText: 'Erasure request' })
  await erase.getByPlaceholder('person@company.com').fill('hello@bakery.test')
  await expect(erase.getByRole('button', { name: 'Erase personal data' })).toBeDisabled() // confirm not typed
  await erase.getByPlaceholder('Type the address again').fill('hello@bakery.test')
  await erase.getByRole('button', { name: 'Erase personal data' }).click()
  await expect(page.getByText('1 lead(s), 1 message(s), 1 business(es) updated.')).toBeVisible()

  await nav(page, 'Suppression list')
  await expect(page.getByRole('cell', { name: 'hello@bakery.test' })).toBeVisible()
  await expect(page.getByRole('cell', { name: 'LEGAL_REQUEST' })).toBeVisible()
})
