import { type APIRequestContext, expect, type Page, test } from "@playwright/test";

import { adminHeaders, logInAsNewUser, SUPABASE_URL } from "./helpers";

const ONE_PIXEL_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

/**
 * Uploads a photo through the real form, so the stored object is owned by the user
 * (Supabase won't delete a user who still owns storage objects). Returns the user id.
 */
async function uploadPhoto(page: Page, request: APIRequestContext): Promise<string> {
  const model = `E2E Delete ${Date.now()}`;
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
  await expect(page).not.toHaveURL(/\/upload/);

  const res = await request.get(
    `${SUPABASE_URL}/rest/v1/submissions?select=id,user_id,shoe_models!inner(model)&shoe_models.model=eq.${encodeURIComponent(model)}`,
    { headers: adminHeaders() },
  );
  const rows = (await res.json()) as { id: string; user_id: string }[];
  expect(rows).toHaveLength(1);
  return rows[0].user_id;
}

async function filesOf(request: APIRequestContext, folder: string): Promise<string[]> {
  const res = await request.post(`${SUPABASE_URL}/storage/v1/object/list/insoles`, {
    headers: adminHeaders(),
    data: { prefix: folder, limit: 100 },
  });
  expect(res.ok(), await res.text()).toBe(true);
  return ((await res.json()) as { name: string }[]).map((f) => f.name);
}

test("delete account removes the user, their rows and all their photos", async ({
  page,
  request,
}) => {
  await logInAsNewUser(page, request, "/upload");
  const userId = await uploadPhoto(page, request);

  // Plays the worker: a processed copy in a subfolder, written with the secret key
  const processed = await request.post(
    `${SUPABASE_URL}/storage/v1/object/insoles/${userId}/processed/copy.png`,
    { headers: { ...adminHeaders(), "Content-Type": "image/png" }, data: ONE_PIXEL_PNG },
  );
  expect(processed.ok(), await processed.text()).toBe(true);
  expect(await filesOf(request, userId)).toHaveLength(2); // the photo + "processed" folder

  // Account page → confirmation page
  await page.goto("/account");
  await page.getByRole("link", { name: "Delete my account…" }).click();
  await expect(page).toHaveURL(/\/account\/delete$/);

  // A wrong confirmation word changes nothing
  await page.getByLabel(/Type DELETE to confirm/).fill("delete");
  await page.getByRole("button", { name: "Delete my account" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Please type DELETE" })).toBeVisible();
  expect(await filesOf(request, userId)).toHaveLength(2);

  await page.getByLabel(/Type DELETE to confirm/).fill("DELETE");
  await page.getByRole("button", { name: "Delete my account" }).click();

  // Signed out, with a confirmation
  await expect(page).toHaveURL(/\/account\/deleted$/);
  await expect(page.getByRole("heading", { name: "Your account has been deleted" })).toBeVisible();
  await expect(page.getByRole("status")).toContainText("all your photos have been removed");
  await expect(page.getByRole("banner").getByRole("link", { name: "Log in" })).toBeVisible();
  await page.goto("/account");
  await expect(page).toHaveURL(/\/login/);

  // Everything is gone
  expect(await filesOf(request, userId)).toEqual([]);
  expect(await filesOf(request, `${userId}/processed`)).toEqual([]);
  const subs = await request.get(`${SUPABASE_URL}/rest/v1/submissions?user_id=eq.${userId}`, {
    headers: adminHeaders(),
  });
  expect(await subs.json()).toEqual([]);
  const authUser = await request.get(`${SUPABASE_URL}/auth/v1/admin/users/${userId}`, {
    headers: adminHeaders(),
  });
  expect(authUser.status()).toBe(404);
});

test("the delete page requires login", async ({ page }) => {
  await page.goto("/account/delete");
  await expect(page).toHaveURL(/\/login\?next=%2Faccount%2Fdelete/);
});
