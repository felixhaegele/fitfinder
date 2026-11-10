import { describe, expect, it } from "vitest";

import {
  fitLabel,
  fitLabelRows,
  hasActiveFilters,
  insoleCount,
  MAX_SEARCH_LENGTH,
  parseShoeFilters,
  shoeFiltersQuery,
  shoesToCsv,
} from "@/lib/shoe-fit";

describe("parseShoeFilters", () => {
  it("returns no filters for an empty query", () => {
    expect(parseShoeFilters({})).toEqual({ q: "", classes: {} });
  });

  it("maps known label values to their columns", () => {
    expect(
      parseShoeFilters({ width: "wide", arch: "high", toe_box: "square", toe_shape: "greek" }),
    ).toEqual({
      q: "",
      classes: { width_class: "wide", arch_class: "high", toe_box_shape: "square", toe_shape: "greek" },
    });
  });

  it("drops unknown, empty and inherited values instead of failing", () => {
    expect(
      parseShoeFilters({ width: "huge", arch: "", toe_box: "toString", toe_shape: "__proto__" }),
    ).toEqual({ q: "", classes: {} });
  });

  it("does not mix up parameters: a width value is not a valid arch value", () => {
    expect(parseShoeFilters({ arch: "wide" }).classes).toEqual({});
  });

  it("uses the first value when a parameter is repeated", () => {
    expect(parseShoeFilters({ q: ["rc7", "other"], width: ["narrow", "wide"] })).toEqual({
      q: "rc7",
      classes: { width_class: "narrow" },
    });
  });

  it("trims and collapses whitespace in the search", () => {
    expect(parseShoeFilters({ q: "  Shimano \t  RC7 " }).q).toBe("Shimano RC7");
  });

  it("caps the search length", () => {
    const q = parseShoeFilters({ q: "a".repeat(500) }).q;
    expect(q).toHaveLength(MAX_SEARCH_LENGTH);
  });

  it("keeps special characters as plain text; the database treats them literally", () => {
    expect(parseShoeFilters({ q: "50% off, (new)" }).q).toBe("50% off, (new)");
  });
});

describe("hasActiveFilters", () => {
  it("is false only without search and label filters", () => {
    expect(hasActiveFilters({ q: "", classes: {} })).toBe(false);
    expect(hasActiveFilters({ q: "rc7", classes: {} })).toBe(true);
    expect(hasActiveFilters({ q: "", classes: { arch_class: "low" } })).toBe(true);
  });
});

describe("fitLabel", () => {
  it("uses the labels from the status page", () => {
    expect(fitLabel("width_class", "wide")).toBe("Wide");
    expect(fitLabel("toe_shape", "egyptian")).toBe("Egyptian (big toe longest)");
  });

  it("shows a dash when no insole of the shoe is classified yet", () => {
    expect(fitLabel("arch_class", null)).toBe("–");
    expect(fitLabel("arch_class", undefined)).toBe("–");
  });

  it("falls back to the raw value for labels it doesn't know", () => {
    expect(fitLabel("toe_box_shape", "oval")).toBe("oval");
    expect(fitLabel("toe_box_shape", "toString")).toBe("toString");
  });
});

describe("fitLabelRows", () => {
  it("lists width, arch, toe box and toe shape in order", () => {
    expect(
      fitLabelRows({ width_class: "narrow", arch_class: "low", toe_box_shape: "round", toe_shape: null }),
    ).toEqual([
      { label: "Width", value: "Narrow" },
      { label: "Arch", value: "Low" },
      { label: "Toe box", value: "Round" },
      { label: "Toe shape", value: "–" },
    ]);
  });
});

describe("insoleCount", () => {
  it("uses singular and plural", () => {
    expect(insoleCount(1)).toBe("1 insole measured");
    expect(insoleCount(3)).toBe("3 insoles measured");
  });
});

describe("shoeFiltersQuery", () => {
  it("is empty without filters", () => {
    expect(shoeFiltersQuery({ q: "", classes: {} })).toBe("");
  });

  it("round-trips through parseShoeFilters", () => {
    const filters = parseShoeFilters({ q: "shimano rc7 & co", width: "wide", toe_shape: "greek" });
    const query = shoeFiltersQuery(filters);
    expect(query).toBe("?q=shimano+rc7+%26+co&width=wide&toe_shape=greek");
    expect(parseShoeFilters(Object.fromEntries(new URLSearchParams(query)))).toEqual(filters);
  });
});

describe("shoesToCsv", () => {
  const shoe = {
    brand: "Shimano",
    model: "RC7",
    year: 2023,
    submission_count: 2,
    median_length_mm: 272.46,
    median_ball_width_mm: 98.2,
    median_heel_width_mm: 62.1,
    median_arch_width_mm: 74,
    width_class: "wide",
    arch_class: "medium",
    toe_box_shape: "round",
    toe_shape: "egyptian",
  };

  it("writes a header row and one row per shoe with readable labels", () => {
    expect(shoesToCsv([shoe]).split("\r\n")).toEqual([
      "Brand,Model,Year,Insoles measured,Median length (mm),Median ball width (mm)," +
        "Median heel width (mm),Median arch width (mm),Width,Arch,Toe box,Toe shape",
      "Shimano,RC7,2023,2,272.46,98.2,62.1,74,Wide,Medium,Round,Egyptian (big toe longest)",
      "",
    ]);
  });

  it("writes only the header for no shoes", () => {
    expect(shoesToCsv([]).split("\r\n")).toHaveLength(2);
  });

  it("leaves cells empty for a shoe that isn't classified yet", () => {
    const row = shoesToCsv([{ ...shoe, width_class: null, arch_class: null, toe_box_shape: null, toe_shape: null }]);
    expect(row.split("\r\n")[1]).toBe("Shimano,RC7,2023,2,272.46,98.2,62.1,74,,,,");
  });

  it("quotes commas, quotes and line breaks", () => {
    const row = shoesToCsv([{ ...shoe, brand: 'Giro "Pro", Inc.', model: "Line\nbreak" }]).split("\r\n").slice(1).join("\r\n");
    expect(row.startsWith('"Giro ""Pro"", Inc.","Line\nbreak",2023')).toBe(true);
  });

  it("defuses text a spreadsheet would run as a formula", () => {
    for (const evil of ["=HYPERLINK(\"x\")", "+1", "-1", "@SUM(A1)", "\tx"]) {
      const cells = shoesToCsv([{ ...shoe, model: evil }]).split("\r\n")[1];
      expect(cells).not.toMatch(/^Shimano,[=+\-@\t]/);
      expect(cells).toContain(`'${evil.replaceAll('"', '""')}`);
    }
  });
});
