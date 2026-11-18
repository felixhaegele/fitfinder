// The printable insole (#122, ADR 0014): one insole's outline at 1:1 on A4, one page per
// foot, so a user can stand on it with their larger foot and see whether it fits.
//
// Everything is laid out in millimetres with the origin at the page's bottom-left (PDF's
// y-up), and only converted to points when drawing. Pure apart from pdf-lib, so the layout
// can be unit tested.

import { PDFDocument, PrintScaling, rgb, StandardFonts, type PDFFont, type PDFPage } from "pdf-lib";

import { FIT_FILTERS, fitLabel, sizeLabel, type FitColumn } from "@/lib/shoe-fit";
import { CLASS_LABELS, formatMm } from "@/lib/submission-status";

export type Point = readonly [number, number];
export type Foot = "left" | "right";
type Rect = { x: number; y: number; w: number; h: number };

export const A4 = { width: 210, height: 297 } as const;
export const PT_PER_MM = 72 / 25.4;
/** Most home printers print to within 5 mm of the edge; the outline needs all the room it can get. */
const MARGIN = 5;
/** Minimum gap between the outline and the text boxes. Outline points are ~3 mm apart. */
const CLEARANCE = 3;

/** Top-left corner: which foot, the shoe and the insole's numbers. */
export const INFO_BOX: Rect = { x: MARGIN, y: A4.height - MARGIN - 38, w: 74, h: 38 };
/** Bottom-right corner: fit labels, how to print and use the page, the 100 mm check ruler. */
export const HELP_BOX: Rect = { x: A4.width - MARGIN - 100, y: MARGIN, w: 100, h: 42 };

// Heel towards the bottom-left, toes towards the top-right, like the photo template (ADR
// 0004): the diagonal is the longest straight line on the page, and the two free corners
// hold the text.
const DIAGONAL_ANGLE = Math.atan2(A4.width, A4.height);

export class InsoleTooLargeError extends Error {
  constructor() {
    super("This insole is too large to print on A4.");
  }
}

/** How the outline sits on the page: turned from the diagonal (degrees) and shifted (mm). */
export type Placement = { angle: number; dx: number; dy: number };
const CENTRED: Placement = { angle: 0, dx: 0, dy: 0 };

/**
 * Puts an outline in the insole frame (ADR 0009: heel at the origin, toe tip at
 * (0, length), drawn as a right foot with the big toe at -x) on the page, in mm. The left
 * foot is the mirror image. Seen from above, as the user stands on it.
 */
export function placeOutline(
  outline: readonly Point[],
  lengthMm: number,
  foot: Foot,
  placement: Placement = CENTRED,
): Point[] {
  const angle = DIAGONAL_ANGLE + (placement.angle * Math.PI) / 180;
  const [sin, cos] = [Math.sin(angle), Math.cos(angle)];
  const mirror = foot === "left" ? -1 : 1;
  return outline.map(([x, y]) => {
    // The middle of the heel-to-toe line goes to the middle of the page (plus the shift).
    const fx = mirror * x;
    const fy = y - lengthMm / 2;
    // Rotation that turns the frame's +y (towards the toes) towards the top-right.
    return [
      A4.width / 2 + placement.dx + fx * cos + fy * sin,
      A4.height / 2 + placement.dy - fx * sin + fy * cos,
    ] as const;
  });
}

// Tried in this order: centred on the diagonal first, then slightly turned and shifted.
// A long insole's heel and toe run into the paper corners, and its wide medial side into
// the text in the top-left (right foot) or bottom-right (left foot), so the best spot
// differs per foot. Insoles up to ~315 mm fit; the photo template can't measure more than
// ~300 mm (ADR 0004).
const PLACEMENTS: Placement[] = (() => {
  const steps = (max: number, step: number) =>
    [0, ...Array.from({ length: max / step }, (_, i) => [(i + 1) * step, -(i + 1) * step]).flat()];
  return steps(6, 1).flatMap((angle) =>
    steps(20, 2).flatMap((dx) => steps(20, 2).map((dy) => ({ angle, dx, dy }))),
  );
})();

/** The first placement where the outline fits the page and clears the text, or null. */
export function fitOutline(outline: readonly Point[], lengthMm: number, foot: Foot): Placement | null {
  return PLACEMENTS.find((p) => outlineFits(placeOutline(outline, lengthMm, foot, p))) ?? null;
}

function inside(rect: Rect, [x, y]: Point, grow = 0): boolean {
  return x >= rect.x - grow && x <= rect.x + rect.w + grow && y >= rect.y - grow && y <= rect.y + rect.h + grow;
}

/** True if the placed outline stays inside the page margins and clear of both text boxes. */
export function outlineFits(points: readonly Point[]): boolean {
  const printable = { x: MARGIN, y: MARGIN, w: A4.width - 2 * MARGIN, h: A4.height - 2 * MARGIN };
  return points.every(
    (p) => inside(printable, p) && !inside(INFO_BOX, p, CLEARANCE) && !inside(HELP_BOX, p, CLEARANCE),
  );
}

/** Reads outline_mm (jsonb) into points, or throws if it isn't a list of [x, y] numbers. */
export function parseOutline(value: unknown): Point[] {
  if (
    !Array.isArray(value) ||
    value.length < 3 ||
    !value.every(
      (p) => Array.isArray(p) && p.length === 2 && p.every((n) => typeof n === "number" && Number.isFinite(n)),
    )
  ) {
    throw new Error("Invalid insole outline");
  }
  return value as Point[];
}

/** What the PDF shows: a row of shoe_insole. Labels are null until classified. */
export type PrintableInsole = {
  brand: string;
  model: string;
  year: number;
  size: number;
  size_system: string;
  insole_condition: string;
  side: string;
  length_mm: number;
  ball_width_mm: number;
  heel_width_mm: number;
  arch_width_mm: number;
  outline_mm: unknown;
} & Partial<Record<FitColumn, string | null>>;

/** The PDF: page 1 left foot, page 2 right foot. Throws InsoleTooLargeError if it can't fit. */
export async function insolePdf(insole: PrintableInsole): Promise<Uint8Array> {
  const outline = parseOutline(insole.outline_mm);
  const pages = (["left", "right"] as const).map((foot) => {
    const placement = fitOutline(outline, insole.length_mm, foot);
    if (!placement) {
      throw new InsoleTooLargeError();
    }
    return { foot, placement };
  });

  const doc = await PDFDocument.create();
  doc.setTitle(
    `FitFinder insole: ${insole.brand} ${insole.model} (${insole.year}), ${sizeLabel(insole.size, insole.size_system)}`,
  );
  doc.setCreator("FitFinder");
  doc.setProducer("FitFinder");
  // Asks the print dialog for "actual size" instead of "fit to page"; viewers may ignore it,
  // which is why the page also has a ruler.
  doc.catalog.getOrCreateViewerPreferences().setPrintScaling(PrintScaling.None);

  const fonts: Fonts = {
    regular: await doc.embedFont(StandardFonts.Helvetica),
    bold: await doc.embedFont(StandardFonts.HelveticaBold),
  };
  for (const { foot, placement } of pages) {
    const page = doc.addPage([A4.width * PT_PER_MM, A4.height * PT_PER_MM]);
    drawOutline(page, outline, fonts.bold, insole.length_mm, foot, placement);
    drawInfo(page, fonts, insole, foot);
    drawHelp(page, fonts, insole);
  }
  return doc.save();
}

// ---------------------------------------------------------------------------
// Drawing
// ---------------------------------------------------------------------------

type Fonts = { regular: PDFFont; bold: PDFFont };
type Line = { text: string; font: PDFFont; size: number; gap?: number };

const BLACK = rgb(0, 0, 0);
const GREY = rgb(0.35, 0.35, 0.35);

function drawOutline(
  page: PDFPage,
  outline: Point[],
  bold: PDFFont,
  lengthMm: number,
  foot: Foot,
  placement: Placement,
) {
  // drawSvgPath puts the SVG origin at (x, y) with SVG's y pointing down, hence -y.
  const path =
    placeOutline(outline, lengthMm, foot, placement)
      .map(([x, y], i) => `${i === 0 ? "M" : "L"} ${x * PT_PER_MM} ${-y * PT_PER_MM}`)
      .join(" ") + " Z";
  page.drawSvgPath(path, { x: 0, y: 0, borderColor: BLACK, borderWidth: 1.2 });

  // Where heel and toes go, inside the outline on its heel-to-toe line.
  const [[hx, hy], [tx, ty]] = placeOutline(
    [
      [0, lengthMm * 0.12],
      [0, lengthMm * 0.82],
    ],
    lengthMm,
    foot,
    placement,
  );
  centredText(page, "HEEL", hx, hy, bold, 10, GREY);
  centredText(page, "TOES", tx, ty, bold, 10, GREY);
}

/** Writes lines top-down into a box; throws if they don't fit (a layout bug, caught by tests). */
function drawLines(page: PDFPage, box: Rect, lines: Line[]): number {
  let top = box.y + box.h;
  for (const line of lines) {
    top -= (line.size * 1.25) / PT_PER_MM;
    text(page, line.text, box.x, top, line.font, line.size);
    top -= line.gap ?? 0;
  }
  if (top < box.y) {
    throw new Error("Insole PDF text overflows its box");
  }
  return top;
}

/** Top-left: which foot, the shoe and the insole's numbers. */
function drawInfo(page: PDFPage, fonts: Fonts, insole: PrintableInsole, foot: Foot) {
  const plain = (value: string, gap?: number): Line => ({ text: value, font: fonts.regular, size: 8, gap });
  drawLines(page, INFO_BOX, [
    { text: foot === "left" ? "LEFT FOOT" : "RIGHT FOOT", font: fonts.bold, size: 18, gap: 1.5 },
    ...wrap(`${insole.brand} ${insole.model} (${insole.year})`, fonts.bold, 10, INFO_BOX.w, 2).map(
      (value): Line => ({ text: value, font: fonts.bold, size: 10 }),
    ),
    plain(`Size ${sizeLabel(insole.size, insole.size_system)}`, 1),
    plain(`Length ${formatMm(insole.length_mm)} · ball ${formatMm(insole.ball_width_mm)}`),
    plain(`Heel ${formatMm(insole.heel_width_mm)} · arch ${formatMm(insole.arch_width_mm)}`),
    plain(`${insole.insole_condition === "used" ? "Used" : "New"} insole, ${insole.side} one measured`),
  ]);
}

const HELP_LINES = [
  "1. Print at 100% (“Actual size”), not “Fit to page”.",
  "2. Check: the ruler below must measure exactly 100 mm.",
  "3. Measure both feet. Stand on the page of your larger",
  "    foot, heel on HEEL. Your foot should fit inside the line.",
];

/** Bottom-right: fit labels, how to use the page, and the 100 mm check ruler. */
function drawHelp(page: PDFPage, fonts: Fonts, insole: PrintableInsole) {
  const plain = (value: string, gap?: number): Line => ({ text: value, font: fonts.regular, size: 8, gap });
  const labels = FIT_FILTERS.map(({ column }) => `${CLASS_LABELS[column].label}: ${fitLabel(column, insole[column])}`);
  const bottom = drawLines(page, HELP_BOX, [
    plain(`${labels[0]} · ${labels[1]}`),
    plain(`${labels[2]} · ${labels[3]}`, 2),
    ...HELP_LINES.map((value) => plain(value)),
  ]);

  // 100 mm ruler along the box's bottom edge: mm ticks, longer every 5 and 10 mm.
  const x0 = HELP_BOX.x;
  const y0 = HELP_BOX.y + 4;
  if (bottom < y0 + 6) {
    throw new Error("Insole PDF text overlaps the ruler");
  }
  line(page, [x0, y0], [x0 + 100, y0], 0.6);
  for (let mm = 0; mm <= 100; mm++) {
    const tick = mm % 10 === 0 ? 4 : mm % 5 === 0 ? 2.5 : 1.5;
    line(page, [x0 + mm, y0], [x0 + mm, y0 + tick], 0.4);
  }
  for (const [mm, label] of [
    [0, "0"],
    [50, "50"],
    [100, "100 mm"],
  ] as const) {
    centredText(page, label, x0 + mm, HELP_BOX.y + 1, fonts.regular, 6);
  }
}

// ---------------------------------------------------------------------------
// Helpers (mm in, points out)
// ---------------------------------------------------------------------------

/** Standard fonts only cover Latin-1; anything else (user-entered names) becomes "?". */
function encodable(value: string, font: PDFFont): string {
  const supported = new Set(font.getCharacterSet());
  return [...value].map((c) => (supported.has(c.codePointAt(0) ?? -1) ? c : "?")).join("");
}

/** Word-wraps to a width in mm, at most maxLines lines; a cut line ends in "…". */
export function wrap(value: string, font: PDFFont, size: number, widthMm: number, maxLines: number): string[] {
  const fits = (s: string) => font.widthOfTextAtSize(encodable(s, font), size) / PT_PER_MM <= widthMm;
  const lines: string[] = [];
  let current = "";
  for (const word of value.split(/\s+/).filter(Boolean)) {
    const next = current ? `${current} ${word}` : word;
    if (fits(next) || !current) {
      current = next;
    } else {
      lines.push(current);
      current = word;
    }
  }
  if (current) {
    lines.push(current);
  }
  if (lines.length > maxLines) {
    lines.length = maxLines;
    lines[maxLines - 1] += "…";
  }
  // A word longer than the width (or a line that the "…" pushed over) loses characters.
  return lines.map((l) => {
    let s = l;
    while (!fits(s) && s.length > 1) {
      s = `${s.replace(/…$/, "").slice(0, -1)}…`;
    }
    return s;
  });
}

function text(page: PDFPage, value: string, x: number, y: number, font: PDFFont, size: number, color = BLACK) {
  page.drawText(encodable(value, font), { x: x * PT_PER_MM, y: y * PT_PER_MM, font, size, color });
}

function centredText(page: PDFPage, value: string, x: number, y: number, font: PDFFont, size: number, color = BLACK) {
  const width = font.widthOfTextAtSize(encodable(value, font), size) / PT_PER_MM;
  text(page, value, x - width / 2, y, font, size, color);
}

function line(page: PDFPage, [x1, y1]: Point, [x2, y2]: Point, thickness: number) {
  page.drawLine({
    start: { x: x1 * PT_PER_MM, y: y1 * PT_PER_MM },
    end: { x: x2 * PT_PER_MM, y: y2 * PT_PER_MM },
    thickness,
    color: BLACK,
  });
}
