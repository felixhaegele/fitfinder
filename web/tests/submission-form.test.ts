import { describe, expect, it } from "vitest";

import { parseSubmission } from "@/lib/submission-form";

const USER = "00000000-0000-0000-0000-00000000000a";
const SHOE = "10000000-0000-0000-0000-000000000001";

function form(fields: Record<string, string>) {
  const data = new FormData();
  for (const [key, value] of Object.entries(fields)) data.set(key, value);
  return data;
}

const valid = {
  consent: "on",
  shoeModelId: SHOE,
  size: "42.5",
  sizeSystem: "eu",
  insoleCondition: "used",
  imagePath: `${USER}/photo.jpg`,
};

describe("parseSubmission", () => {
  it("accepts a valid upload of an existing shoe", () => {
    expect(parseSubmission(form(valid), USER)).toEqual({
      ok: true,
      value: {
        shoe: { kind: "existing", id: SHOE },
        size: 42.5,
        sizeSystem: "eu",
        insoleCondition: "used",
        imagePath: `${USER}/photo.jpg`,
      },
    });
  });

  it("accepts a new shoe model, trimmed", () => {
    const result = parseSubmission(
      form({ ...valid, shoeModelId: "new", brand: " Lake ", model: "CX241", year: "2019" }),
      USER,
    );
    expect(result).toMatchObject({
      ok: true,
      value: { shoe: { kind: "new", brand: "Lake", model: "CX241", year: 2019 } },
    });
  });

  it("requires consent", () => {
    const withoutConsent = Object.fromEntries(Object.entries(valid).filter(([k]) => k !== "consent"));
    expect(parseSubmission(form(withoutConsent), USER)).toMatchObject({ ok: false });
  });

  it.each([
    ["missing shoe", { shoeModelId: "" }],
    ["not a uuid", { shoeModelId: "1; drop table" }],
    ["new shoe without brand", { shoeModelId: "new", brand: "", model: "X", year: "2020" }],
    ["new shoe year too old", { shoeModelId: "new", brand: "A", model: "X", year: "1980" }],
    ["new shoe year not a number", { shoeModelId: "new", brand: "A", model: "X", year: "soon" }],
    ["unknown size system", { sizeSystem: "jp" }],
    ["no insole condition", { insoleCondition: "" }],
    ["unknown insole condition", { insoleCondition: "worn out" }],
    ["inherited object key as condition", { insoleCondition: "toString" }],
    ["EU size out of range", { size: "12" }],
    ["two decimals", { size: "42.25" }],
    ["size not a number", { size: "forty" }],
    ["photo in someone else's folder", { imagePath: "00000000-0000-0000-0000-00000000000b/x.jpg" }],
    ["path traversal", { imagePath: `${USER}/../other/x.jpg` }],
  ])("rejects %s", (_label, override) => {
    expect(parseSubmission(form({ ...valid, ...override }), USER)).toMatchObject({ ok: false });
  });

  it.each([
    ["comma as decimal separator", { size: "42,5" }],
    ["US half size", { sizeSystem: "us_m", size: "9.5" }],
    ["UK size with .1 (float edge case)", { sizeSystem: "uk", size: "1.1" }],
    ["Mondopoint", { sizeSystem: "mondopoint", size: "270" }],
    ["a new insole", { insoleCondition: "new" }],
  ])("accepts %s", (_label, override) => {
    expect(parseSubmission(form({ ...valid, ...override }), USER)).toMatchObject({ ok: true });
  });
});
