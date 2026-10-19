import { expect, test } from "@playwright/test";

import { logInAsNewUser } from "./helpers";

const PDF = "/fitfinder-template-a4-v1.pdf";

test("template page explains printing and links the PDF", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Get the printable template" }).click();

  await expect(page).toHaveURL(/\/template$/);
  await expect(page.getByRole("heading", { level: 1, name: "Printable template" })).toBeVisible();
  await expect(page.getByText(/100 % \/ .Actual size./)).toBeVisible();
  await expect(page.getByText("grey dashed zone")).toBeVisible();
  await expect(page.getByRole("link", { name: /Download the template/ })).toHaveAttribute(
    "href",
    PDF,
  );
});

test("template PDF downloads", async ({ page, request }) => {
  await page.goto("/template");
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: /Download the template/ }).click(),
  ]);
  expect(download.suggestedFilename()).toBe("fitfinder-template-a4-v1.pdf");

  const res = await request.get(PDF);
  expect(res.status()).toBe(200);
  expect(res.headers()["content-type"]).toBe("application/pdf");
  expect((await res.body()).subarray(0, 5).toString()).toBe("%PDF-");
});

test("upload page links the template", async ({ page, request }) => {
  await logInAsNewUser(page, request, "/upload");
  await expect(page).toHaveURL(/\/upload$/);

  await page.getByRole("link", { name: "Download and print it" }).click();
  await expect(page).toHaveURL(/\/template$/);
});
