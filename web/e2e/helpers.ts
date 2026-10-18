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

export const ONE_PIXEL_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

/** Fills and submits /upload with a new shoe model; returns the new submission's id. */
export async function uploadViaForm(page: Page, model = `E2E Model ${Date.now()}`) {
  await page.goto("/upload");
  await page.getByLabel("Shoe model").selectOption({ label: "My shoe isn't listed" });
  await page.getByLabel("Brand", { exact: true }).fill("Testbrand");
  await page.getByLabel("Model", { exact: true }).fill(model);
  await page.getByLabel("Model year").fill("2024");
  await page.getByLabel("Size", { exact: true }).fill("43");
  await page.getByLabel("New (never worn)").check();
  await page.getByLabel("Photo of the insole").setInputFiles({
    name: "insole.png",
    mimeType: "image/png",
    buffer: ONE_PIXEL_PNG,
  });
  await page.getByLabel(/I agree that FitFinder stores this photo/).check();
  await page.getByRole("button", { name: "Upload" }).click();
  await expect(page).toHaveURL(/\/submissions\/[0-9a-f-]{36}$/);
  return page.url().split("/").pop()!;
}

/** Plays the worker: changes rows directly, bypassing RLS like the service role does. */
export async function adminRest(
  request: APIRequestContext,
  method: "GET" | "PATCH" | "POST",
  path: string,
  data?: object,
) {
  const res = await request.fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    method,
    headers: { ...adminHeaders(), "Content-Type": "application/json", Prefer: "return=representation" },
    data,
  });
  expect(res.ok(), await res.text()).toBe(true);
  return (await res.json()) as Record<string, unknown>[];
}

export async function adminUpload(request: APIRequestContext, path: string, body: Buffer) {
  const res = await request.post(`${SUPABASE_URL}/storage/v1/object/insoles/${path}`, {
    headers: { ...adminHeaders(), "Content-Type": "image/png" },
    data: body,
  });
  expect(res.ok(), await res.text()).toBe(true);
}
