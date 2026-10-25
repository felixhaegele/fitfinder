import { expect, test } from "./fixtures";

test("home page loads", async ({ page }) => {
  await page.goto("/");

  await expect(page).toHaveTitle(/FitFinder/);
  await expect(page.getByRole("heading", { level: 1, name: "FitFinder" })).toBeVisible();
});
