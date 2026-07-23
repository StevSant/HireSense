import { expect, test } from 'playwright/test';

test('renders the login form without an API', async ({ page }) => {
  await page.goto('/login');

  await expect(page.getByRole('heading', { name: 'HireSense' })).toBeVisible();
  await expect(page.getByLabel('Username')).toBeVisible();
  await expect(page.getByLabel('Password')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Sign In' })).toBeEnabled();
});
