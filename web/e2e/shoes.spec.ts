import type { APIRequestContext } from "@playwright/test";

import { expect, test } from "./fixtures";

import { adminHeaders, adminRest, SUPABASE_URL } from "./helpers";

// This spec is about the public /shoes pages, not about uploading: the uploader, their
// submissions and the worker's results are created directly as admin (bypassing RLS),
// the same way status.spec.ts plays the worker.

/** An uploader created directly in Supabase Auth. */
async function createUser(request: APIRequestContext) {
  const email = `e2e-shoes-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
  const res = await request.post(`${SUPABASE_URL}/auth/v1/admin/users`, {
    headers: { ...adminHeaders(), Authorization: `Bearer ${adminHeaders().apikey}` },
    data: { email, email_confirm: true },
  });
  expect(res.ok(), await res.text()).toBe(true);
  const { id } = (await res.json()) as { id: string };
  return { id, email };
}

/** A submission as the upload form would create it. */
async function createSubmission(request: APIRequestContext, userId: string, shoeModelId: string) {
  const [submission] = await adminRest(request, "POST", "submissions", {
    user_id: userId,
    shoe_model_id: shoeModelId,
    size: 43,
    size_system: "eu",
    image_path: `${userId}/${crypto.randomUUID()}.jpg`,
    consent_at: new Date().toISOString(),
    insole_condition: "new",
  });
  return { id: String(submission.id), imagePath: String(submission.image_path) };
}

/** Plays the worker: a measurement + classification, then the final status. */
async function measure(
  request: APIRequestContext,
  submissionId: string,
  classification: Record<string, string>,
  status: "done" | "rejected" = "done",
) {
  const [measurement] = await adminRest(request, "POST", "measurements", {
    submission_id: submissionId,
    pipeline_version: "e2e",
    length_mm: status === "done" ? 272.46 : 999,
    ball_width_mm: 98.2,
    heel_width_mm: 62.1,
    arch_width_mm: 74,
    side: "left",
    outline_mm: Array.from({ length: 256 }, (_, i) => [0, i]),
  });
  await adminRest(request, "POST", "classifications", {
    measurement_id: measurement.id,
    classifier_version: "e2e",
    ...classification,
  });
  await adminRest(request, "PATCH", `submissions?id=eq.${submissionId}`, {
    status,
    ...(status === "rejected" && { rejection_reason: "Markers not found." }),
  });
}

test("measured shoes are listed, searchable and filterable without logging in", async ({
  page,
  request,
}) => {
  // Someone uploads two insoles of a new shoe: one is measured, one rejected.
  const user = await createUser(request);
  const model = `Fit Model ${Date.now()}`;
  const [shoe] = await adminRest(request, "POST", "shoe_models", {
    brand: "Testbrand",
    model,
    year: 2024,
  });
  const shoeId = String(shoe.id);
  const done = await createSubmission(request, user.id, shoeId);
  await measure(request, done.id, {
    width_class: "wide",
    arch_class: "medium",
    toe_box_shape: "round",
    toe_shape: "egyptian",
  });
  const rejected = await createSubmission(request, user.id, shoeId);
  await measure(
    request,
    rejected.id,
    { width_class: "narrow", arch_class: "low", toe_box_shape: "pointed", toe_shape: "greek" },
    "rejected",
  );

  // A visitor who isn't logged in (this page has no session) finds it from the header.
  await page.goto("/");
  await page.getByRole("link", { name: "Find by model" }).click();
  await expect(page.getByRole("heading", { name: "Shoes by fit" })).toBeVisible();

  await page.getByRole("searchbox", { name: "Brand or model" }).fill(`testbrand ${model}`);
  await page.getByRole("button", { name: "Search" }).click();
  const results = page.getByRole("region", { name: "Shoes" });
  const row = results.getByRole("link", { name: new RegExp(model) });
  await expect(row).toHaveCount(1);
  // Only the done submission counts; the rejected one (narrow, 999 mm) doesn't.
  await expect(row).toContainText("1 insole measured");
  // Insole mm depend on the size, so the list shows none per model.
  await expect(row).not.toContainText(" mm");
  await expect(row).toContainText("Wide");
  await expect(row).toContainText("Egyptian (big toe longest)");
  await expect(row).not.toContainText("Narrow");
  await expect(row).not.toContainText("999");
  await expect(results).toContainText("not your own foot");

  // Filters: matching labels keep it, another width hides it.
  await page.getByLabel("Width").selectOption({ label: "Wide" });
  await page.getByLabel("Toe shape").selectOption({ label: "Egyptian (big toe longest)" });
  await page.getByRole("button", { name: "Search" }).click();
  await expect(page).toHaveURL(/width=wide/);
  await expect(page.getByRole("link", { name: new RegExp(model) })).toHaveCount(1);

  await page.getByLabel("Width").selectOption({ label: "Narrow" });
  await page.getByRole("button", { name: "Search" }).click();
  await expect(page).toHaveURL(/width=narrow/);
  await expect(page.getByText("No measured shoes match your search.")).toBeVisible();
  await expect(page.getByRole("link", { name: new RegExp(model) })).toHaveCount(0);

  // The detail page shows the labels for the model, and measurements only per size.
  await page.goto(`/shoes/${shoeId}`);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(model);
  await expect(page.getByText("1 insole measured, all sizes.")).toBeVisible();
  const sizeRow = page.getByRole("row", { name: /EU 43/ });
  await expect(sizeRow.getByRole("cell", { name: "272.5 mm" })).toBeVisible();
  await expect(sizeRow.getByRole("cell", { name: "98.2 mm" })).toBeVisible();
  // Outside the per-size table, no mm at all.
  const outsideTable = await page.getByRole("main").evaluate((main) => {
    const copy = main.cloneNode(true) as HTMLElement;
    copy.querySelectorAll("table").forEach((table) => table.remove());
    return copy.textContent ?? "";
  });
  expect(outsideTable).not.toMatch(/\d mm/);
  await expect(page.getByText("not your own foot")).toBeVisible();

  // Nothing about the person who uploaded it, on either page.
  for (const url of [`/shoes?q=${encodeURIComponent(model)}`, `/shoes/${shoeId}`]) {
    await page.goto(url);
    await expect(page.getByText(model).first()).toBeVisible();
    const html = await page.content();
    for (const personal of [user.email, user.id, done.imagePath, rejected.imagePath, done.id, rejected.id]) {
      expect(html).not.toContain(personal);
    }
  }
});

test("shoe pages that don't exist are not found", async ({ page }) => {
  await page.goto("/shoes/not-a-uuid");
  await expect(page.getByText("This page could not be found")).toBeVisible();
  await page.goto("/shoes/00000000-0000-0000-0000-000000000000");
  await expect(page.getByText("This page could not be found")).toBeVisible();
});

test("unknown filter values are ignored instead of failing", async ({ page }) => {
  await page.goto("/shoes?width=huge&arch=toString&q=");
  await expect(page.getByRole("heading", { name: "Shoes by fit" })).toBeVisible();
  await expect(page.getByLabel("Width")).toHaveValue("");
});

test("find by size lists shoes whose insole fits a foot plus wiggle room", async ({
  page,
  request,
}) => {
  // One measured EU 43 insole: 272.46 mm long, 98.2 mm at the ball.
  const user = await createUser(request);
  const model = `Foot Model ${Date.now()}`;
  const [shoe] = await adminRest(request, "POST", "shoe_models", {
    brand: "Testbrand",
    model,
    year: 2024,
  });
  const submission = await createSubmission(request, user.id, String(shoe.id));
  await measure(request, submission.id, {
    width_class: "regular",
    arch_class: "medium",
    toe_box_shape: "round",
    toe_shape: "egyptian",
  });

  await page.goto("/");
  await page.getByRole("link", { name: "Find by size" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Shoes for your feet" })).toBeVisible();
  await expect(page.getByLabel("Wiggle room (mm)")).toHaveValue("7");

  // 265 + 7 = 272 mm needed: the 272.46 mm insole fits.
  await page.getByLabel("Foot length (mm)").fill("265");
  await page.getByLabel("Foot width (mm)").fill("98");
  await page.getByRole("button", { name: "Find shoes" }).click();
  await expect(page).toHaveURL(/length=265&width=98&wiggle=7/);
  const match = page
    .getByRole("region", { name: "Matching shoes" })
    .getByRole("link", { name: new RegExp(model) });
  await expect(match).toContainText("Size EU 43");
  await expect(match).toContainText("7.5 mm longer than your foot");

  // 265 + 10 = 275 mm needed: too short now.
  await page.getByLabel("Wiggle room (mm)").fill("10");
  await page.getByRole("button", { name: "Find shoes" }).click();
  await expect(page).toHaveURL(/wiggle=10/);
  await expect(page.getByRole("link", { name: new RegExp(model) })).toHaveCount(0);
});

test("find by size explains an invalid foot size", async ({ page }) => {
  await page.goto("/shoes/for-my-feet?length=26&width=98");
  // Scoped to main: Next.js's route announcer is an alert too.
  await expect(page.getByRole("main").getByRole("alert")).toHaveText(/foot length in mm, between 150 and 350/);
});
