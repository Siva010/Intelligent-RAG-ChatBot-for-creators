import { test, expect } from '@playwright/test';

test('has title and inputs', async ({ page }) => {
  await page.goto('/');

  // Check title
  await expect(page).toHaveTitle(/CreatorJoy/);

  // Check heading
  const heading = page.getByRole('heading', { name: /Audit Social Video/i });
  await expect(heading).toBeVisible();

  // Check URL inputs
  const urlInputs = page.getByRole('textbox');
  
  await expect(urlInputs.nth(0)).toBeVisible();
  await expect(urlInputs.nth(1)).toBeVisible();
});
