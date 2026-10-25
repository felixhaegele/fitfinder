import { expect, test } from "./fixtures";

import {
  adminRest,
  adminUpload,
  logInAsNewUser,
  ONE_PIXEL_PNG,
  uploadViaForm,
} from "./helpers";

test("status page updates by itself and shows results and both photos", async ({ page, request }) => {
  await logInAsNewUser(page, request);
  const model = `Status Model ${Date.now()}`;
  const id = await uploadViaForm(page, model);

  await expect(page.getByRole("status")).toContainText("Waiting to be measured");
  await expect(page.getByRole("img", { name: "The photo you uploaded" })).toBeVisible();
  await expect(page.getByText("Created when your photo is measured.")).toBeVisible();

  // The worker's part: cleaned copy, measurement, classification, status
  const [submission] = await adminRest(request, "GET", `submissions?id=eq.${id}&select=user_id`);
  const processedPath = `${submission.user_id}/processed/${id}.jpg`;
  await adminUpload(request, processedPath, ONE_PIXEL_PNG);
  const [measurement] = await adminRest(request, "POST", "measurements", {
    submission_id: id,
    pipeline_version: "e2e",
    length_mm: 272.46,
    ball_width_mm: 98.2,
    heel_width_mm: 62.1,
    arch_width_mm: 74,
    side: "left",
    // 256 points starting at the heel point (0, 0); the shape itself isn't shown yet
    outline_mm: Array.from({ length: 256 }, (_, i) => [0, i]),
  });
  await adminRest(request, "POST", "classifications", {
    measurement_id: measurement.id,
    classifier_version: "e2e",
    width_class: "wide",
    arch_class: "medium",
    toe_box_shape: "round",
    toe_shape: "egyptian",
  });
  await adminRest(request, "PATCH", `submissions?id=eq.${id}`, {
    status: "done",
    processed_image_path: processedPath,
  });

  // No reload: the page polls while the submission is in progress
  await expect(page.getByRole("status")).toContainText("has been measured", { timeout: 15_000 });
  await expect(page.getByText("272.5 mm")).toBeVisible();
  await expect(page.getByText("98.2 mm")).toBeVisible();
  await expect(page.getByText("Wide", { exact: true })).toBeVisible();
  await expect(page.getByText("Egyptian (big toe longest)")).toBeVisible();
  await expect(page.getByText("not your own foot")).toBeVisible();
  await expect(page.getByRole("img", { name: "The photo you uploaded" })).toBeVisible();
  await expect(page.getByRole("img", { name: "re-encoded by FitFinder" })).toBeVisible();

  // And it shows up in the list
  await page.getByRole("link", { name: "← My uploads" }).click();
  await expect(page.getByRole("link", { name: new RegExp(model) })).toContainText("Measured");
});

test("a rejected photo shows the reason and a way to try again", async ({ page, request }) => {
  await logInAsNewUser(page, request);
  const id = await uploadViaForm(page);

  await adminRest(request, "PATCH", `submissions?id=eq.${id}`, {
    status: "rejected",
    rejection_reason: "Markers not found. Make sure all four corners of the template are visible.",
  });

  await expect(page.getByRole("status")).toContainText("Markers not found", { timeout: 15_000 });
  await expect(page.getByRole("link", { name: "Upload a new photo" })).toBeVisible();
});

test("other users' submissions are not found", async ({ browser, page, request }) => {
  await logInAsNewUser(page, request);
  const id = await uploadViaForm(page);

  // A second, separate browser = a different person
  const other = await (await browser.newContext()).newPage();
  await logInAsNewUser(other, request);
  await other.goto(`/submissions/${id}`);
  await expect(other.getByText("This page could not be found")).toBeVisible();

  // Garbage ids too, without a database error
  await other.goto("/submissions/not-a-uuid");
  await expect(other.getByText("This page could not be found")).toBeVisible();
});
