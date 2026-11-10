import { expect, test } from "./fixtures";

import { logInAsNewUser } from "./helpers";

test("landing page shows the flow: template, upload, browse", async ({ page }) => {
  await page.goto("/");

  const steps = page.getByRole("main").getByRole("listitem");
  await expect(steps).toHaveCount(3);
  await expect(page.getByRole("link", { name: "Get the template" })).toHaveAttribute(
    "href",
    "/template",
  );
  await expect(page.getByRole("link", { name: "Browse shoes" })).toHaveAttribute("href", "/shoes");

  // Upload needs a login: logged out, the link leads to the login page and back.
  await page.getByRole("link", { name: "Upload a photo" }).click();
  await expect(page).toHaveURL(/\/login\?next=%2Fupload$/);
});

test("privacy page is linked from the footer and covers the essentials", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("contentinfo").getByRole("link", { name: "Privacy" }).click();

  await expect(page).toHaveURL(/\/privacy$/);
  await expect(page.getByRole("heading", { level: 1, name: "Privacy" })).toBeVisible();
  for (const heading of [
    "Who is responsible",
    "Why we use it and on what legal basis",
    "Where it is stored",
    "Transfers outside the EU and Switzerland",
    "Your consent",
    "Who can see your photos",
    "Location and camera data",
    "What is public",
    "How long we keep it",
    "Deleting your data",
    "Your rights",
    "Contact",
  ]) {
    await expect(page.getByRole("heading", { level: 2, name: heading })).toBeVisible();
  }
  await expect(page.getByText(/expire after 10 minutes/)).toBeVisible();
});

test("terms page is linked from the footer and covers the essentials", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("contentinfo").getByRole("link", { name: "Terms" }).click();

  await expect(page).toHaveURL(/\/terms$/);
  await expect(page.getByRole("heading", { level: 1, name: "Terms of use" })).toBeVisible();
  for (const heading of [
    "What you can upload",
    "Your content",
    "Measurements are estimates",
    "Liability",
    "Law and disputes",
  ]) {
    await expect(page.getByRole("heading", { level: 2, name: heading })).toBeVisible();
  }
});

test("the login page links to the terms and the privacy notice", async ({ page }) => {
  await page.goto("/login");

  const main = page.getByRole("main");
  await expect(main.getByRole("link", { name: "terms of use" })).toHaveAttribute("href", "/terms");
  await expect(main.getByRole("link", { name: "privacy notice" })).toHaveAttribute("href", "/privacy");
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
