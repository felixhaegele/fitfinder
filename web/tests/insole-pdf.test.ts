import { PDFDocument, PrintScaling, StandardFonts } from "pdf-lib";
import { describe, expect, it } from "vitest";

import {
  A4,
  fitOutline,
  insolePdf,
  InsoleTooLargeError,
  outlineFits,
  parseOutline,
  placeOutline,
  PT_PER_MM,
  wrap,
  type Point,
  type PrintableInsole,
} from "@/lib/insole-pdf";

/**
 * An insole-like outline in the insole frame (ADR 0009): 256 points from the heel point,
 * heel → medial (-x) → toe → lateral (+x). Widest at 70% of the length, like the ball of
 * the foot, and 55% of the width on the medial side: the worst case for the top-left text.
 */
function insoleOutline(lengthMm: number, ballWidthMm: number): Point[] {
  const half = 128;
  const width = (t: number) => ballWidthMm * Math.sin(Math.PI * t ** 1.94) ** 0.5;
  const medial = Array.from({ length: half }, (_, i): Point => {
    const t = i / half;
    return [-0.55 * width(t), t * lengthMm];
  });
  const lateral = Array.from({ length: half }, (_, i): Point => {
    const t = 1 - i / half;
    return [0.45 * width(t), t * lengthMm];
  });
  return [...medial, ...lateral];
}

const insole: PrintableInsole = {
  brand: "Shimano",
  model: "RC7",
  year: 2023,
  size: 43,
  size_system: "eu",
  insole_condition: "new",
  side: "left",
  length_mm: 272.46,
  ball_width_mm: 98.2,
  heel_width_mm: 62.1,
  arch_width_mm: 74,
  width_class: "wide",
  arch_class: "medium",
  toe_box_shape: "round",
  toe_shape: "egyptian",
  outline_mm: insoleOutline(272.46, 98.2),
};

const distance = ([ax, ay]: Point, [bx, by]: Point) => Math.hypot(ax - bx, ay - by);

describe("placeOutline", () => {
  const heelToe: Point[] = [
    [0, 0],
    [0, 280],
    [-40, 200],
  ];

  it("keeps the insole at 1:1", () => {
    const [heel, toe, medial] = placeOutline(heelToe, 280, "right");
    expect(distance(heel, toe)).toBeCloseTo(280, 6);
    expect(distance(heel, medial)).toBeCloseTo(Math.hypot(40, 200), 6);
  });

  it("centres the heel-to-toe line on the page, toes towards the top-right", () => {
    const [heel, toe] = placeOutline(heelToe, 280, "right");
    expect((heel[0] + toe[0]) / 2).toBeCloseTo(A4.width / 2, 6);
    expect((heel[1] + toe[1]) / 2).toBeCloseTo(A4.height / 2, 6);
    expect(toe[0]).toBeGreaterThan(heel[0]);
    expect(toe[1]).toBeGreaterThan(heel[1]);
    // along the page diagonal
    expect((toe[1] - heel[1]) / (toe[0] - heel[0])).toBeCloseTo(A4.height / A4.width, 6);
  });

  it("puts the big toe on the left of a right foot and on the right of a left foot", () => {
    // Seen from above with the toes pointing away: the medial point is left of the
    // heel-to-toe line for the right foot (positive cross product), right of it for the left.
    const side = (foot: "left" | "right") => {
      const [heel, toe, medial] = placeOutline(heelToe, 280, foot);
      return (toe[0] - heel[0]) * (medial[1] - heel[1]) - (toe[1] - heel[1]) * (medial[0] - heel[0]);
    };
    expect(side("right")).toBeGreaterThan(0);
    expect(side("left")).toBeLessThan(0);
  });

  it("draws the left foot as the mirror image of the right", () => {
    const right = placeOutline(heelToe, 280, "right");
    const left = placeOutline(heelToe, 280, "left");
    expect(distance(left[0], left[2])).toBeCloseTo(distance(right[0], right[2]), 6);
    expect(left[0]).toEqual(right[0]);
    expect(left[1]).toEqual(right[1]);
    expect(left[2]).not.toEqual(right[2]);
  });
});

describe("fitOutline", () => {
  it("centres a typical insole on the diagonal", () => {
    for (const foot of ["left", "right"] as const) {
      expect(fitOutline(insoleOutline(250, 90), 250, foot)).toEqual({ angle: 0, dx: 0, dy: 0 });
    }
  });

  it("fits every insole the photo template can measure (~300 mm), clear of the text", () => {
    for (const [length, ball] of [
      [272, 98],
      [300, 110],
      [310, 115],
    ]) {
      for (const foot of ["left", "right"] as const) {
        const outline = insoleOutline(length, ball);
        const placement = fitOutline(outline, length, foot);
        expect(placement, `${length} ${foot}`).not.toBeNull();
        expect(outlineFits(placeOutline(outline, length, foot, placement!))).toBe(true);
      }
    }
  });

  it("turning and shifting keeps the insole at 1:1", () => {
    const outline = insoleOutline(300, 110);
    const [heel, , toe] = placeOutline([outline[0], outline[64], [0, 300]], 300, "right", { angle: 5, dx: -8, dy: 12 });
    expect(distance(heel, toe)).toBeCloseTo(300, 6);
  });

  it("gives up on an insole longer than the page allows", () => {
    expect(fitOutline(insoleOutline(380, 110), 380, "right")).toBeNull();
  });
});

describe("parseOutline", () => {
  it("accepts a list of [x, y] numbers", () => {
    expect(parseOutline(insoleOutline(270, 100))).toHaveLength(256);
  });

  it("rejects anything else", () => {
    for (const bad of [null, "x", [], [[0, 0]], [[0, 0], [1, "2"], [3, 4]], [[0, 0, 0], [1, 1], [2, 2]], [[0, 0], [1, Number.NaN], [2, 2]]]) {
      expect(() => parseOutline(bad)).toThrow("Invalid insole outline");
    }
  });
});

describe("wrap", async () => {
  const doc = await PDFDocument.create();
  const font = await doc.embedFont(StandardFonts.Helvetica);
  const width = (s: string) => font.widthOfTextAtSize(s, 10) / PT_PER_MM;

  it("keeps short text on one line", () => {
    expect(wrap("Shimano RC7 (2023)", font, 10, 74, 2)).toEqual(["Shimano RC7 (2023)"]);
  });

  it("wraps long text and cuts it at the line limit with an ellipsis", () => {
    const lines = wrap("word ".repeat(60), font, 10, 74, 2);
    expect(lines).toHaveLength(2);
    expect(lines[1].endsWith("…")).toBe(true);
    expect(lines.every((l) => width(l) <= 74)).toBe(true);
  });

  it("shortens a single word wider than the line", () => {
    const [only] = wrap("x".repeat(200), font, 10, 74, 2);
    expect(width(only)).toBeLessThanOrEqual(74);
    expect(only.endsWith("…")).toBe(true);
  });
});

describe("insolePdf", () => {
  it("makes two A4 pages, left foot then right foot", async () => {
    const pdf = await PDFDocument.load(await insolePdf(insole));
    expect(pdf.getPageCount()).toBe(2);
    for (const page of pdf.getPages()) {
      expect(page.getWidth()).toBeCloseTo(A4.width * PT_PER_MM, 2);
      expect(page.getHeight()).toBeCloseTo(A4.height * PT_PER_MM, 2);
    }
    expect(pdf.getTitle()).toBe("FitFinder insole: Shimano RC7 (2023), EU 43");
  });

  it("asks the print dialog not to scale", async () => {
    const pdf = await PDFDocument.load(await insolePdf(insole));
    expect(pdf.catalog.getViewerPreferences()?.getPrintScaling()).toBe(PrintScaling.None);
  });

  it("copes with long, non-Latin and unclassified shoes", async () => {
    const odd = {
      ...insole,
      brand: "Fi'zi:k ".repeat(12),
      model: "Vento Ω 碳 " + "Infinito ".repeat(20),
      width_class: null,
      arch_class: null,
      toe_box_shape: null,
      toe_shape: null,
    };
    await expect(insolePdf(odd)).resolves.toBeInstanceOf(Uint8Array);
  });

  it("refuses an insole too large for A4", async () => {
    await expect(insolePdf({ ...insole, length_mm: 380, outline_mm: insoleOutline(380, 110) })).rejects.toThrow(
      InsoleTooLargeError,
    );
  });

  it("refuses an invalid outline", async () => {
    await expect(insolePdf({ ...insole, outline_mm: { not: "points" } })).rejects.toThrow("Invalid insole outline");
  });
});
