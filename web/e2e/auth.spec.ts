import { expect, type APIRequestContext, test } from "@playwright/test";

// Note: Next.js renders an empty role="alert" (its route announcer) on every page, so
// alerts are matched by their text.

// Local Supabase sends all email to Mailpit instead of real inboxes.
const MAILPIT = process.env.MAILPIT_URL ?? "http://127.0.0.1:54324";

type MailpitList = { messages: { ID: string; To: { Address: string }[] }[] };

/** Polls Mailpit until an email for `to` arrives and returns the login link in it. */
async function magicLinkFor(request: APIRequestContext, to: string): Promise<string> {
  let link: string | undefined;
  await expect
    .poll(
      async () => {
        const res = await request.get(`${MAILPIT}/api/v1/search?query=${encodeURIComponent(`to:${to}`)}`);
        const { messages } = (await res.json()) as MailpitList;
        if (messages.length === 0) return false;
        const msg = await (await request.get(`${MAILPIT}/api/v1/message/${messages[0].ID}`)).json();
        link = /href="([^"]+\/auth\/v1\/verify[^"]+)"/.exec(msg.HTML as string)?.[1];
        return Boolean(link);
      },
      { timeout: 15_000, message: `no login email for ${to}` },
    )
    .toBe(true);
  // The email HTML escapes & as &amp;
  return link!.replaceAll("&amp;", "&");
}

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

test("an invalid login link shows a clear error", async ({ page }) => {
  await page.goto("/auth/callback?code=not-a-real-code");
  await expect(page).toHaveURL(/\/login\?error=link/);
  await expect(page.getByRole("alert").filter({ hasText: "invalid or has expired" })).toBeVisible();
});

test("rejects an invalid email without sending anything", async ({ page }) => {
  await page.goto("/login");
  // Passes the browser's type=email check (no dot needed) but not the server's.
  await page.getByLabel("Email").fill("someone@localhost");
  await page.getByRole("button", { name: "Send me a login link" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "valid email address" })).toBeVisible();
});
