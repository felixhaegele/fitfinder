import { type APIRequestContext, expect, type Page } from "@playwright/test";

// Local Supabase sends all email to Mailpit instead of real inboxes.
const MAILPIT = process.env.MAILPIT_URL ?? "http://127.0.0.1:54324";
export const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "http://127.0.0.1:54321";

type MailpitList = { messages: { ID: string }[] };

/** Polls Mailpit until an email for `to` arrives and returns the login link in it. */
export async function magicLinkFor(request: APIRequestContext, to: string): Promise<string> {
  let link: string | undefined;
  await expect
    .poll(
      async () => {
        const res = await request.get(
          `${MAILPIT}/api/v1/search?query=${encodeURIComponent(`to:${to}`)}`,
        );
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

/** A fresh user per test, logged in through the real magic-link flow. */
export async function logInAsNewUser(page: Page, request: APIRequestContext, next = "/account") {
  const email = `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
  await page.goto(`/login?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Email").fill(email);
  await page.getByRole("button", { name: "Send me a login link" }).click();
  await expect(page.getByRole("status")).toContainText(email);
  await page.goto(await magicLinkFor(request, email));
  return email;
}

/** Admin access to the local stack for assertions. Tests only; never in app code. */
export function adminHeaders() {
  const key = process.env.SUPABASE_SECRET_KEY;
  if (!key) throw new Error("SUPABASE_SECRET_KEY missing in web/.env.local (see .env.example)");
  return { apikey: key };
}
