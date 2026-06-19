import { test, expect } from '@playwright/test'

test('homepage has login text', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('button', { name: '登录' })).toBeVisible()
})
