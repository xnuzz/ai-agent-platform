import { expect, login, nav, requestChanges, test } from './fixtures'

test.beforeEach(async ({ page, creds }) => { await login(page, creds) })

test('software idea: changes requested -> edit -> resubmit', async ({ page }) => {
  await requestChanges(page, 'ChairFill', 'Narrow the ICP to 1-3 chair clinics')
  await nav(page, 'Software ideas')
  await page.getByRole('heading', { name: 'ChairFill' }).click()
  await expect(page.getByText('Narrow the ICP to 1-3 chair clinics')).toBeVisible()
  await page.locator('label:has-text("Target customers") + textarea').fill('Independent clinics with 1-3 chairs')
  await page.locator('label:has-text("Key features") + textarea').fill('Waitlist\nSMS\nAuto-fill cancelled slots')
  await page.getByRole('button', { name: 'Save draft' }).click()
  await expect(page.getByText('Saved.')).toBeVisible()
  await page.getByRole('button', { name: /submit for approval/ }).click()
  await expect(page.getByText('Submitted for approval.')).toBeVisible()
  await expect(page.getByText('WAITING FOR APPROVAL').first()).toBeVisible()
  await expect(page.locator('label:has-text("Name") + input')).toBeDisabled()
})

test('opportunity curation', async ({ page }) => {
  await nav(page, 'Software ideas')
  await page.getByRole('button', { name: 'Shortlist' }).click()
  await expect(page.locator('article span', { hasText: 'SHORTLISTED' }).first()).toBeVisible()
})

test('project brief + lead legal basis editing', async ({ page }) => {
  await requestChanges(page, 'Secure, fast website for Corner Bakery', 'Budget too high for a bakery')
  await nav(page, 'Leads & briefs')
  await page.getByText('Corner Bakery').first().click()
  await expect(page.getByText('Budget too high for a bakery')).toBeVisible()
  await page.locator('label:has-text("Budget max") + input').fill('1100')
  await page.locator('form', { hasText: 'Project brief' }).getByRole('button', { name: /submit for approval/ }).click()
  await expect(page.getByText('Submitted for approval.')).toBeVisible()
  await page.locator('label:has-text("Legal basis note") + textarea').fill('LIA: B2B offer to public business address')
  await page.locator('form', { hasText: 'Contact & legal basis' }).getByRole('button', { name: 'Save' }).click()
  await expect(page.getByText('Saved.')).toBeVisible()
})

test('campaign: edit offer and message, resubmit, approve, launch blocked until brief approved', async ({ page }) => {
  await requestChanges(page, 'Corner Bakery website offer', 'Mention the free audit')
  await nav(page, 'Campaigns')
  await page.getByText('Corner Bakery website offer').click()
  await expect(page.getByText('Mention the free audit')).toBeVisible()
  await page.locator('label:has-text("Offer headline") + input').fill('Free website security audit')
  await page.getByRole('button', { name: 'Save campaign' }).click()
  await expect(page.getByText('Saved.')).toBeVisible()
  await page.getByRole('button', { name: 'Edit', exact: true }).click()
  await page.locator('label:has-text("Body") + textarea').fill('Hello Corner Bakery,\n\nWe offer a free security audit.')
  await page.getByRole('button', { name: 'Save message' }).click()
  await expect(page.getByText('We offer a free security audit.')).toBeVisible()
  await page.getByRole('button', { name: /Submit 1 message/ }).click()
  await expect(page.locator('text=Latest review').locator('..').getByText('PENDING')).toBeVisible()

  // Approve only the campaign: launch must be refused because the brief is still pending.
  await nav(page, 'Approval center')
  await page.locator('button.card', { hasText: 'Corner Bakery website offer' }).click()
  await page.getByRole('button', { name: 'Approve', exact: true }).click()
  await nav(page, 'Campaigns')
  await page.getByText('Corner Bakery website offer').click()
  await page.getByRole('button', { name: 'Launch' }).click()
  await expect(page.getByText(/project_brief_not_approved/)).toBeVisible()
})

test('settings: members and integrations (secret never rendered)', async ({ page, creds }) => {
  await nav(page, 'Settings')
  await page.getByRole('button', { name: 'members' }).click()
  await page.locator('label:has-text("Add existing user") + input').fill(creds.teammate)
  await page.getByRole('button', { name: 'Add member' }).click()
  await expect(page.getByText(creds.teammate)).toBeVisible()

  await page.getByRole('button', { name: 'integrations' }).click()
  await page.getByRole('button', { name: 'Add integration' }).click()
  await page.locator('label:has-text("Name") + input').fill('Test SMTP')
  await page.locator('input[type=password]').fill('smtp-secret-value')
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.getByText('stored (hidden)')).toBeVisible()
  expect(await page.content()).not.toContain('smtp-secret-value')
  page.once('dialog', (d) => d.accept())
  await page.getByText('Delete').click()
  await expect(page.getByText('Integration deleted.')).toBeVisible()
})

test('audit log shows decisions', async ({ page }) => {
  await requestChanges(page, 'ChairFill', 'audit me')
  await nav(page, 'Audit log')
  await expect(page.getByText('approval.changes_requested').first()).toBeVisible()
})
