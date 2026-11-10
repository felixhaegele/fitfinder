import { expect, test } from "./fixtures";

import { logInAsNewUser } from "./helpers";

test("landing page leads to upload, browsing and the template", async ({ page }) => {
  await page.goto("/");

  const main = page.getByRole("main");
  await expect(main.getByRole("listitem")).toHaveCount(3);
  await expect(main.getByRole("link", { name: "View shoes" })).toHaveAttribute("href", "/shoes");
  await expect(main.getByRole("link", { name: "printed A4 template" })).toHaveAttribute(
    "href",
    "/template",
  );

  // Upload needs a login: logged out, the primary button leads to the login page and back.
  await main.getByRole("link", { name: "Upload a shoe" }).click();
  await expect(page).toHaveURL(/\/login\?next=%2Fupload$/);
});

test("privacy page is linked from the footer and covers the essentials", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("contentinfo").getByRole("link", { name: "Privacy" }).click();

  await expect(page).toHaveURL(/\/privacy$/);
  await expect(page.getByRole("heading", { level: 1, name: "Privacy" })).toBeVisible();
  for (const heading of [
    "Where it is stored",
    "Your consent",
    "Who can see your photos",
    "Location and camera data",
    "What is public",
    "Deleting your data",
    "Contact",
  ]) {
    await expect(page.getByRole("heading", { level: 2, name: heading })).toBeVisible();
  }
  await expect(page.getByText(/expire after 10 minutes/)).toBeVisible();
});

test("the upload consent links to the privacy page in a new tab", async ({ page, request }) => {
  await logInAsNewUser(page, request, "/upload");

  const link = page.getByRole("link", { name: "How we handle your data" });
  await expect(link).toHaveAttribute("target", "_blank");
  const [privacy] = await Promise.all([page.waitForEvent("popup"), link.click()]);
  await expect(privacy.getByRole("heading", { level: 1, name: "Privacy" })).toBeVisible();
  // The form stays where it was
  await expect(page).toHaveURL(/\/upload$/);
});
