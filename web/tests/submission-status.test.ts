import { describe, expect, it } from "vitest";

import { classificationRows, formatMm, isInProgress, statusCopy, TOE_LABELS_NOTE } from "@/lib/submission-status";

describe("statusCopy", () => {
  it.each([
    ["queued", "Waiting"],
    ["processing", "Measuring"],
    ["done", "Measured"],
    ["rejected", "Not measurable"],
    ["failed", "Error"],
  ])("labels %s as %s", (status, label) => {
    expect(statusCopy(status).label).toBe(label);
  });

  it("treats an unknown status as an error instead of crashing", () => {
    expect(statusCopy("exploded").label).toBe("Error");
    expect(statusCopy("toString").label).toBe("Error");
  });
});

describe("isInProgress", () => {
  it("is true only while the worker may still change the status", () => {
    expect(["queued", "processing", "done", "rejected", "failed"].map(isInProgress)).toEqual([
      true,
      true,
      false,
      false,
      false,
    ]);
  });
});

describe("formatMm", () => {
  it("rounds to one decimal and adds the unit", () => {
    expect(formatMm(272.456)).toBe("272.5 mm");
    expect(formatMm(98)).toBe("98.0 mm");
  });

  it("shows a dash for missing values", () => {
    expect(formatMm(null)).toBe("–");
    expect(formatMm(undefined)).toBe("–");
  });
});

describe("classificationRows", () => {
  it("turns classifier labels into readable rows, in a fixed order", () => {
    expect(
      classificationRows({
        width_class: "wide",
        arch_class: "low",
        toe_box_shape: "square",
        toe_shape: "roman",
      }),
    ).toEqual([
      { label: "Width", value: "Wide" },
      { label: "Arch", value: "Low" },
      { label: "Toe box", value: "Square" },
      { label: "Toe shape", value: "Roman (first toes even)" },
    ]);
  });

  it("labels all three toe shapes", () => {
    const base = { width_class: "regular", arch_class: "medium", toe_box_shape: "round" };
    expect(
      ["egyptian", "roman", "greek"].map(
        (toe_shape) => classificationRows({ ...base, toe_shape })[3].value,
      ),
    ).toEqual([
      "Egyptian (big toe longest)",
      "Roman (first toes even)",
      "Greek (second toe longest)",
    ]);
  });

  it("says the toe labels describe the shoe, not the user's foot", () => {
    expect(TOE_LABELS_NOTE).toMatch(/shoe's toe box/);
    expect(TOE_LABELS_NOTE).toMatch(/not your own foot/);
  });

  it("shows unknown labels as they are (a newer classifier may add some)", () => {
    expect(
      classificationRows({
        width_class: "extra_wide",
        arch_class: "low",
        toe_box_shape: "round",
        toe_shape: "greek",
      })[0],
    ).toEqual({ label: "Width", value: "extra_wide" });
  });
});
