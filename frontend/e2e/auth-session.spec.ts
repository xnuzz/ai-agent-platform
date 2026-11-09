import { expect, login, nav, test } from './fixtures'

test('session survives reload via httpOnly cookie; nothing sensitive in web storage; sign out revokes', async ({ page, context, creds }) => {
  await login(page, creds)
  const cookie = (await context.cookies()).find((c) => c.name === 'platform_refresh')
  expect(cookie?.httpOnly).toBe(true)
  const stored = await page.evaluate(() => JSON.stringify({ ...sessionStorage }) + JSON.stringify({ ...localStorage }))
  expect(stored).not.toMatch(/eyJ/) // no JWT in web storage

  await page.reload()
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible() // restored from cookie

  await page.getByRole('button', { name: 'Sign out' }).click()
  await page.waitForURL(/\/login/)
  await page.goto('/')
  await expect(page).toHaveURL(/\/login/) // cookie revoked: no silent re-login
})

test('forgot password never reveals whether an account exists', async ({ page }) => {
  await page.goto('/login')
  await page.getByRole('button', { name: 'Forgot password?' }).click()
  await page.fill('input[type=email]', 'nobody-here@example.com')
  await page.getByRole('button', { name: 'Send reset link' }).click()
  await expect(page.getByText('If an account exists for nobody-here@example.com')).toBeVisible()
})

test('reset page rejects an invalid link', async ({ page }) => {
  await page.goto('/reset-password?uid=abc&token=bad')
  await page.locator('input[type=password]').nth(0).fill('Another-pass-789')
  await page.locator('input[type=password]').nth(1).fill('Another-pass-789')
  await page.getByRole('button', { name: 'Set password' }).click()
  await expect(page.getByText('Invalid input.')).toBeVisible()
})

test('change password signs out and the new password works', async ({ page, creds }) => {
  await login(page, creds)
  await nav(page, 'Settings')
  await page.getByRole('button', { name: 'account' }).click()
  await page.locator('label:has-text("Current password") + input').fill(creds.password)
  await page.locator('label:text-is("New password") + input').fill('Changed-pass-2468')
  await page.locator('label:has-text("Repeat new password") + input').fill('Changed-pass-2468')
  await page.getByRole('button', { name: 'Change password' }).click()
  await page.waitForURL(/\/login/)
  await login(page, { ...creds, password: 'Changed-pass-2468' })
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
})
