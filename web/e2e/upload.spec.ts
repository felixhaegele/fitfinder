import { expect, test } from "./fixtures";

import { adminHeaders, logInAsNewUser, SUPABASE_URL } from "./helpers";

const ONE_PIXEL_PNG =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";

// Stands in for GPS position, camera serial etc.: any EXIF text must not survive upload.
const METADATA_MARKER = "FITFINDER-PRIVATE-METADATA";

/**
 * Adds an EXIF block to a JPEG: an ImageDescription with METADATA_MARKER, and
 * Orientation = 6 ("rotate 90° clockwise to display"), as phones write it.
 */
function withExif(jpeg: Buffer): Buffer {
  const text = Buffer.from(`${METADATA_MARKER}\0`, "ascii");
  const tiff = Buffer.alloc(38); // header (8) + IFD: count (2) + 2 entries (24) + next (4)
  tiff.write("II", 0, "ascii"); // little endian
  tiff.writeUInt16LE(42, 2);
  tiff.writeUInt32LE(8, 4); // IFD0 starts right after the header
  tiff.writeUInt16LE(2, 8);
  // 0x010E ImageDescription, ASCII, points at the text after the IFD
  tiff.writeUInt16LE(0x010e, 10);
  tiff.writeUInt16LE(2, 12);
  tiff.writeUInt32LE(text.length, 14);
  tiff.writeUInt32LE(38, 18);
  // 0x0112 Orientation, SHORT, value 6 stored inline
  tiff.writeUInt16LE(0x0112, 22);
  tiff.writeUInt16LE(3, 24);
  tiff.writeUInt32LE(1, 26);
  tiff.writeUInt16LE(6, 30);
  tiff.writeUInt32LE(0, 34); // no next IFD

  const payload = Buffer.concat([Buffer.from("Exif\0\0", "ascii"), tiff, text]);
  const app1 = Buffer.from([0xff, 0xe1, 0, 0]);
  app1.writeUInt16BE(payload.length + 2, 2);
  // APP1 goes right after the start-of-image marker (FF D8)
  return Buffer.concat([jpeg.subarray(0, 2), app1, payload, jpeg.subarray(2)]);
}

/** Width and height from a JPEG's start-of-frame header. */
function jpegSize(jpeg: Buffer): { width: number; height: number } {
  for (let i = 2; i < jpeg.length; ) {
    const marker = jpeg[i + 1];
    if (marker === 0xc0 || marker === 0xc2) {
      return { height: jpeg.readUInt16BE(i + 5), width: jpeg.readUInt16BE(i + 7) };
    }
    i += 2 + jpeg.readUInt16BE(i + 2);
  }
  throw new Error("no SOF marker");
}

test("upload strips metadata, keeps orientation and creates a queued submission", async ({
  page,
  request,
}) => {
  await logInAsNewUser(page, request, "/upload");
  await expect(page).toHaveURL(/\/upload$/);

  // A 300×200 JPEG made by the browser itself, then EXIF added in Node
  const base64 = await page.evaluate(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 300;
    canvas.height = 200;
    const ctx = canvas.getContext("2d")!;
    ctx.fillStyle = "#c33";
    ctx.fillRect(0, 0, 300, 200);
    return canvas.toDataURL("image/jpeg").split(",")[1];
  });
  const photo = withExif(Buffer.from(base64, "base64"));
  expect(photo.includes(METADATA_MARKER)).toBe(true); // sanity check of the fixture

  // A shoe that doesn't exist yet: also exercises "My shoe isn't listed"
  const model = `E2E Model ${Date.now()}`;
  await page.getByLabel("Shoe model").selectOption({ label: "My shoe isn't listed" });
  await page.getByLabel("Brand", { exact: true }).fill("Testbrand");
  await page.getByLabel("Model", { exact: true }).fill(model);
  await page.getByLabel("Model year").fill("2024");
  await page.getByLabel("Size", { exact: true }).fill("44.5");
  await page.getByLabel("Size system").selectOption("eu");
  await page.getByLabel("Used (has been worn)").check();
  await page.getByLabel("Photo of the insole").setInputFiles({
    name: "insole.jpg",
    mimeType: "image/jpeg",
    buffer: photo,
  });
  await page.getByLabel(/I agree that FitFinder stores this photo/).check();
  await page.getByRole("button", { name: "Upload" }).click();

  // Straight to the new submission's status page
  await expect(page).toHaveURL(/\/submissions\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("status")).toContainText("Waiting to be measured");

  // The submission exists, is queued and has consent recorded
  const res = await request.get(
    `${SUPABASE_URL}/rest/v1/submissions?select=image_path,size,size_system,insole_condition,status,consent_at,shoe_models!inner(model)&shoe_models.model=eq.${encodeURIComponent(model)}`,
    { headers: adminHeaders() },
  );
  expect(res.ok()).toBe(true);
  const rows = (await res.json()) as {
    image_path: string;
    size: number;
    size_system: string;
    insole_condition: string;
    status: string;
    consent_at: string | null;
  }[];
  expect(rows).toHaveLength(1);
  expect(rows[0]).toMatchObject({
    size: 44.5,
    size_system: "eu",
    insole_condition: "used",
    status: "queued",
  });
  expect(rows[0].consent_at).toBeTruthy();

  // The stored file: a JPEG without any EXIF, rotated upright before stripping
  const file = await request.get(`${SUPABASE_URL}/storage/v1/object/insoles/${rows[0].image_path}`, {
    headers: adminHeaders(),
  });
  expect(file.ok()).toBe(true);
  const stored = await file.body();
  expect(stored.subarray(0, 2)).toEqual(Buffer.from([0xff, 0xd8]));
  expect(stored.includes(METADATA_MARKER)).toBe(false);
  expect(stored.includes(Buffer.from("Exif\0\0", "ascii"))).toBe(false);
  expect(jpegSize(stored)).toEqual({ width: 200, height: 300 });
});

test("the form can't be submitted without consent", async ({ page, request }) => {
  await logInAsNewUser(page, request, "/upload");
  await page.getByLabel("Shoe model").selectOption({ label: "My shoe isn't listed" });
  await page.getByLabel("Brand", { exact: true }).fill("Testbrand");
  await page.getByLabel("Model", { exact: true }).fill("No consent");
  await page.getByLabel("Model year").fill("2024");
  await page.getByLabel("Size", { exact: true }).fill("43");
  await page.getByLabel("New (never worn)").check();
  await page.getByLabel("Photo of the insole").setInputFiles({
    name: "insole.png",
    mimeType: "image/png",
    buffer: Buffer.from(ONE_PIXEL_PNG, "base64"),
  });
  await page.getByRole("button", { name: "Upload" }).click();

  // The browser blocks the submit (required checkbox); we stay on the form
  await expect(page).toHaveURL(/\/upload$/);
  await expect(page.getByLabel(/I agree that FitFinder stores this photo/)).toHaveJSProperty(
    "validity.valueMissing",
    true,
  );
});

test("the form can't be submitted without choosing the insole condition", async ({
  page,
  request,
}) => {
  await logInAsNewUser(page, request, "/upload");
  await page.getByLabel("Shoe model").selectOption({ label: "My shoe isn't listed" });
  await page.getByLabel("Brand", { exact: true }).fill("Testbrand");
  await page.getByLabel("Model", { exact: true }).fill("No condition");
  await page.getByLabel("Model year").fill("2024");
  await page.getByLabel("Size", { exact: true }).fill("43");
  await page.getByLabel("Photo of the insole").setInputFiles({
    name: "insole.png",
    mimeType: "image/png",
    buffer: Buffer.from(ONE_PIXEL_PNG, "base64"),
  });
  await page.getByLabel(/I agree that FitFinder stores this photo/).check();
  await page.getByRole("button", { name: "Upload" }).click();

  // Nothing preselected, and the browser blocks the submit until one is chosen
  await expect(page).toHaveURL(/\/upload$/);
  await expect(page.getByLabel("New (never worn)")).not.toBeChecked();
  await expect(page.getByLabel("Used (has been worn)")).toHaveJSProperty("validity.valueMissing", true);
});

test("logged-out visitors are sent to login", async ({ page }) => {
  await page.goto("/upload");
  await expect(page).toHaveURL(/\/login\?next=%2Fupload/);
});
