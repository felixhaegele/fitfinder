import { type APIRequestContext, expect, test } from "@playwright/test";

import {
  adminHeaders,
  adminRest,
  adminUpload,
  logInAsNewUser,
  ONE_PIXEL_PNG,
  SUPABASE_URL,
  uploadViaForm,
} from "./helpers";

/** Full paths of the files directly in `folder` (sub-folders are left out). */
async function filesIn(request: APIRequestContext, folder: string): Promise<string[]> {
  const res = await request.post(`${SUPABASE_URL}/storage/v1/object/list/insoles`, {
    headers: adminHeaders(),
    data: { prefix: folder, limit: 100 },
  });
  expect(res.ok(), await res.text()).toBe(true);
  return ((await res.json()) as { name: string; id: string | null }[])
    .filter((f) => f.id !== null)
    .map((f) => `${folder}/${f.name}`);
}

test("deleting an upload removes the original, the processed copy and the row", async ({
  page,
  request,
}) => {
  await logInAsNewUser(page, request, "/upload");
  const keptId = await uploadViaForm(page, `E2E Kept ${Date.now()}`);
  const submissionId = await uploadViaForm(page);
  const [row] = (await adminRest(
    request,
    "GET",
    `submissions?id=eq.${submissionId}&select=user_id,image_path`,
  )) as { user_id: string; image_path: string }[];
  const userId = row.user_id;

  // Plays the worker: a processed copy written with the secret key, recorded in the row
  const processedPath = `${userId}/processed/${submissionId}.jpg`;
  await adminUpload(request, processedPath, ONE_PIXEL_PNG);
  await adminRest(request, "PATCH", `submissions?id=eq.${submissionId}`, {
    processed_image_path: processedPath,
  });
  expect(await filesIn(request, userId)).toContain(row.image_path);
  expect(await filesIn(request, `${userId}/processed`)).toEqual([processedPath]);

  // Cancel changes nothing
  await page.goto(`/submissions/${submissionId}`);
  await page.getByRole("button", { name: "Delete this upload…" }).click();
  await page.getByRole("button", { name: "Cancel" }).click();
  await page.getByRole("button", { name: "Delete this upload…" }).click();
  await page.getByRole("button", { name: "Delete upload", exact: true }).click();

  await expect(page).toHaveURL(/\/submissions$/);
  await page.goto(`/submissions/${submissionId}`);
  await expect(page.getByText("This page could not be found")).toBeVisible();

  // Both photos and the row are gone. Checked with the secret key, because a storage
  // delete that RLS refuses reports success without removing anything.
  expect(await filesIn(request, userId)).not.toContain(row.image_path);
  expect(await filesIn(request, `${userId}/processed`)).toEqual([]);
  expect(await adminRest(request, "GET", `submissions?id=eq.${submissionId}`)).toEqual([]);

  // The other upload is untouched
  const [kept] = (await adminRest(
    request,
    "GET",
    `submissions?id=eq.${keptId}&select=image_path`,
  )) as { image_path: string }[];
  expect(await filesIn(request, userId)).toEqual([kept.image_path]);
});
