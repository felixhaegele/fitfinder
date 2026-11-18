import { describe, expect, it } from "vitest";

import { DEFAULT_WIGGLE_MM, matchSizes, parseFootQuery } from "@/lib/foot-match";

describe("parseFootQuery", () => {
  it("is no search and no error while the form is empty", () => {
    expect(parseFootQuery({})).toEqual({ values: { length: "", width: "", wiggle: "" }, foot: null, error: null });
  });

  it("reads length, width and wiggle room in mm, with a decimal point or comma", () => {
    expect(parseFootQuery({ length: "265.5", width: "98,5", wiggle: "4" }).foot).toEqual({
      lengthMm: 265.5,
      widthMm: 98.5,
      wiggleMm: 4,
    });
  });

  it("uses the default wiggle room when it is blank or invalid, but keeps 0", () => {
    expect(parseFootQuery({ length: "265", width: "98" }).foot?.wiggleMm).toBe(DEFAULT_WIGGLE_MM);
    expect(parseFootQuery({ length: "265", width: "98", wiggle: "lots" }).foot?.wiggleMm).toBe(DEFAULT_WIGGLE_MM);
    expect(parseFootQuery({ length: "265", width: "98", wiggle: "99" }).foot?.wiggleMm).toBe(DEFAULT_WIGGLE_MM);
    expect(parseFootQuery({ length: "265", width: "98", wiggle: "0" }).foot?.wiggleMm).toBe(0);
  });

  it("rejects a missing or implausible length or width with a message", () => {
    expect(parseFootQuery({ width: "98" })).toMatchObject({ foot: null, error: expect.stringMatching(/foot length/) });
    expect(parseFootQuery({ length: "26", width: "98" }).error).toMatch(/between 150 and 350/);
    expect(parseFootQuery({ length: "265", width: "9.8.1" }).error).toMatch(/foot width/);
    expect(parseFootQuery({ length: "-265", width: "98" }).error).toMatch(/foot length/);
  });

  it("takes the first value of a repeated parameter", () => {
    expect(parseFootQuery({ length: ["265", "300"], width: "98" }).foot?.lengthMm).toBe(265);
  });
});

const row = (shoe: string, length: number | null, width: number | null, size = 43) => ({
  shoe_model_id: shoe,
  size,
  median_length_mm: length,
  median_ball_width_mm: width,
});

describe("matchSizes", () => {
  const foot = { lengthMm: 260, widthMm: 98, wiggleMm: 7 };

  it("picks, per shoe, the shortest size that is foot length + wiggle room or longer", () => {
    const matches = matchSizes(
      [row("a", 265, 100, 42), row("a", 268, 100, 43), row("a", 274, 101, 44)],
      foot,
    );
    expect(matches).toEqual([{ row: row("a", 268, 100, 43), spareLengthMm: 8, spareWidthMm: 2 }]);
  });

  it("leaves out sizes far too long, too narrow, or not measured", () => {
    expect(matchSizes([row("a", 277.5, 100)], foot)).toEqual([]); // 260 + 7 + 10 = 277 at most
    expect(matchSizes([row("a", 270, 97.5)], foot)).toEqual([]);
    expect(matchSizes([row("a", null, 100), row("b", 270, null)], foot)).toEqual([]);
  });

  it("counts an insole exactly at the limits", () => {
    expect(matchSizes([row("a", 267, 98), row("b", 277, 98)], foot)).toHaveLength(2);
  });

  it("lists the closest fit first", () => {
    const matches = matchSizes([row("far", 275, 100), row("close", 268, 100), row("mid", 271, 100)], foot);
    expect(matches.map((m) => m.row.shoe_model_id)).toEqual(["close", "mid", "far"]);
  });
});
