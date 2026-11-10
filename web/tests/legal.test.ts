import { describe, expect, it } from "vitest";

import { reportHref } from "@/lib/legal";

describe("reportHref", () => {
  it("points to the reporting section of the terms while there is no contact email", () => {
    expect(reportHref("Report: shoe", null)).toBe("/terms#reporting");
  });

  it("is an email with the subject filled in once the contact email is set", () => {
    expect(reportHref("Report: Shimano RC9 (2024), /shoes/1", "report@example.org")).toBe(
      "mailto:report@example.org?subject=Report%3A%20Shimano%20RC9%20(2024)%2C%20%2Fshoes%2F1",
    );
  });
});
