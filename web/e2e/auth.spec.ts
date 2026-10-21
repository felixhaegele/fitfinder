import { expect, test } from "./fixtures";

import { magicLinkFor } from "./helpers";

// Note: Next.js renders an empty role="alert" (its route announcer) on every page, so
// alerts are matched by their text.

test("log in with a magic link, see the account page, log out", async ({ page, request }) => {
  // Unique address per run, so earlier runs' emails don't interfere.
  const email = `e2e-${Date.now()}@example.com`;

  // Logged out: the account page sends us to login and remembers where we wanted to go
  await page.goto("/account");
  await expect(page).toHaveURL(/\/login\?next=%2Faccount/);

  await page.getByLabel("Email").fill(email);
  await page.getByRole("button", { name: "Send me a login link" }).click();
  await expect(page.getByRole("status")).toContainText(email);

  // Same browser (PKCE): follow the link from the email
  await page.goto(await magicLinkFor(request, email));

  await expect(page).toHaveURL(/\/account$/);
  await expect(page.getByText(`Logged in as ${email}`)).toBeVisible();
  await expect(page.getByRole("banner").getByRole("link", { name: email })).toBeVisible();

  // Session survives a reload (cookies, not just client state)
  await page.reload();
  await expect(page.getByText(`Logged in as ${email}`)).toBeVisible();

  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL("/");
  await expect(page.getByRole("banner").getByRole("link", { name: "Log in" })).toBeVisible();

  await page.goto("/account");
  await expect(page).toHaveURL(/\/login/);
});

test("the login link works in a different browser (cross-device)", async ({
  browser,
  page,
  request,
}) => {
  const email = `e2e-xdevice-${Date.now()}@example.com`;

  // "Laptop": request the link
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByRole("button", { name: "Send me a login link" }).click();
  await expect(page.getByRole("status")).toContainText(email);

  // "Phone": a fresh browser context shares no cookies with the one above
  const phone = await (await browser.newContext()).newPage();
  await phone.goto(await magicLinkFor(request, email));
  await expect(phone).toHaveURL(/\/account$/);
  await expect(phone.getByText(`Logged in as ${email}`)).toBeVisible();
});

test("an invalid login link shows a clear error", async ({ page }) => {
  for (const link of [
    "/auth/confirm?token_hash=not-a-real-token&type=email&next=%2Faccount",
    "/auth/confirm?next=%2Faccount",
    "/auth/confirm?code=not-a-real-code&next=%2Faccount",
    "/auth/callback?code=not-a-real-code",
  ]) {
    await page.goto(link);
    await expect(page).toHaveURL(/\/login\?error=link/);
    await expect(
      page.getByRole("alert").filter({ hasText: "invalid or has expired" }),
    ).toBeVisible();
  }
});

test("rejects an invalid email without sending anything", async ({ page }) => {
  await page.goto("/login");
  // Passes the browser's type=email check (no dot needed) but not the server's.
  await page.getByLabel("Email").fill("someone@localhost");
  await page.getByRole("button", { name: "Send me a login link" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "valid email address" })).toBeVisible();
});
