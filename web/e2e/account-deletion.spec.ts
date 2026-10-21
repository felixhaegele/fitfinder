import type { APIRequestContext } from "@playwright/test";
import { expect, test } from "./fixtures";

import {
  adminHeaders,
  adminRest,
  adminUpload,
  logInAsNewUser,
  ONE_PIXEL_PNG,
  SUPABASE_URL,
  uploadViaForm,
} from "./helpers";

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
  // Uploaded through the real form, so the photo is owned by the user (Supabase won't
  // delete a user who still owns storage objects).
  const submissionId = await uploadViaForm(page);
  const [{ user_id: userId }] = (await adminRest(
    request,
    "GET",
    `submissions?id=eq.${submissionId}&select=user_id`,
  )) as { user_id: string }[];

  // Plays the worker: a processed copy in a subfolder, written with the secret key
  const processedPath = `${userId}/processed/${submissionId}.jpg`;
  await adminUpload(request, processedPath, ONE_PIXEL_PNG);
  await adminRest(request, "PATCH", `submissions?id=eq.${submissionId}`, {
    processed_image_path: processedPath,
  });
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
  expect(await adminRest(request, "GET", `submissions?user_id=eq.${userId}`)).toEqual([]);
  const authUser = await request.get(`${SUPABASE_URL}/auth/v1/admin/users/${userId}`, {
    headers: adminHeaders(),
  });
  expect(authUser.status()).toBe(404);
});

test("the delete page requires login", async ({ page }) => {
  await page.goto("/account/delete");
  await expect(page).toHaveURL(/\/login\?next=%2Faccount%2Fdelete/);
});
