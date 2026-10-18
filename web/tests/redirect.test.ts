import { describe, expect, it } from "vitest";

import { safeNextPath } from "@/lib/redirect";

describe("safeNextPath", () => {
  it.each(["/account", "/shoes?brand=shimano", "/a/b#c"])("keeps same-site path %s", (path) => {
    expect(safeNextPath(path)).toBe(path);
  });

  it.each([
    ["another site", "https://evil.example"],
    ["protocol-relative URL", "//evil.example"],
    ["backslash trick", "/\\evil.example"],
    ["relative path", "account"],
    ["empty string", ""],
    ["missing value", null],
    ["non-string form value", 42],
  ])("falls back for %s", (_label, value) => {
    expect(safeNextPath(value)).toBe("/account");
  });

  it("uses a custom fallback", () => {
    expect(safeNextPath(undefined, "/")).toBe("/");
  });
});
