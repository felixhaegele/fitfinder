// Search filters and labels for the public shoe pages (/shoes, /shoes/[id]). Pure functions,
// so the parsing of untrusted query parameters can be unit tested.

import { CLASS_LABELS } from "@/lib/submission-status";

/** Query parameter → column of the shoe_fit_summaries result it filters on. */
export const FIT_FILTERS = [
  { param: "width", column: "width_class" },
  { param: "arch", column: "arch_class" },
  { param: "toe_box", column: "toe_box_shape" },
  { param: "toe_shape", column: "toe_shape" },
] as const;

export type FitColumn = (typeof FIT_FILTERS)[number]["column"];

export type ShoeFilters = {
  /** Free-text search over brand, model and year; "" for none. */
  q: string;
  /** Only known label values, so they can go straight into an equality filter. */
  classes: Partial<Record<FitColumn, string>>;
};

export const MAX_SEARCH_LENGTH = 100;

type SearchParams = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

/**
 * Turns the URL's query parameters into filters. Anything unknown is dropped instead of
 * causing an error: a hand-edited URL just shows more shoes.
 */
export function parseShoeFilters(params: SearchParams): ShoeFilters {
  const q = (first(params.q) ?? "").trim().replaceAll(/\s+/g, " ").slice(0, MAX_SEARCH_LENGTH).trim();

  const classes: ShoeFilters["classes"] = {};
  for (const { param, column } of FIT_FILTERS) {
    const value = first(params[param]);
    if (value && Object.hasOwn(CLASS_LABELS[column].values, value)) {
      classes[column] = value;
    }
  }
  return { q, classes };
}

export function hasActiveFilters(filters: ShoeFilters): boolean {
  return filters.q !== "" || Object.keys(filters.classes).length > 0;
}

/** "wide" → "Wide". Null (no classified insole yet) → "–". */
export function fitLabel(column: FitColumn, value: string | null | undefined): string {
  if (value == null) {
    return "–";
  }
  const values = CLASS_LABELS[column].values;
  return Object.hasOwn(values, value) ? values[value] : value;
}

/** Label rows for a summary, in the same order as on the status page. */
export function fitLabelRows(summary: Partial<Record<FitColumn, string | null>>) {
  return FIT_FILTERS.map(({ column }) => ({
    label: CLASS_LABELS[column].label,
    value: fitLabel(column, summary[column]),
  }));
}

export function insoleCount(n: number): string {
  return n === 1 ? "1 insole measured" : `${n} insoles measured`;
}

/** The filters as a query string for a link ("" or "?q=…&width=…"), the reverse of parseShoeFilters. */
export function shoeFiltersQuery(filters: ShoeFilters): string {
  const params = new URLSearchParams();
  if (filters.q) {
    params.set("q", filters.q);
  }
  for (const { param, column } of FIT_FILTERS) {
    const value = filters.classes[column];
    if (value) {
      params.set(param, value);
    }
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

/** The columns of a shoe_fit_summaries row the CSV uses. Labels are null until classified. */
export type ShoeSummaryRow = {
  brand: string;
  model: string;
  year: number;
  submission_count: number;
  median_length_mm: number | null;
  median_ball_width_mm: number | null;
  median_heel_width_mm: number | null;
  median_arch_width_mm: number | null;
} & Partial<Record<FitColumn, string | null>>;

type CsvValue = string | number | null | undefined;

const CSV_COLUMNS: { header: string; value: (row: ShoeSummaryRow) => CsvValue }[] = [
  { header: "Brand", value: (row) => row.brand },
  { header: "Model", value: (row) => row.model },
  { header: "Year", value: (row) => row.year },
  { header: "Insoles measured", value: (row) => row.submission_count },
  { header: "Median length (mm)", value: (row) => row.median_length_mm },
  { header: "Median ball width (mm)", value: (row) => row.median_ball_width_mm },
  { header: "Median heel width (mm)", value: (row) => row.median_heel_width_mm },
  { header: "Median arch width (mm)", value: (row) => row.median_arch_width_mm },
  // Readable labels, like on the page; an empty cell (not "–") when not classified yet.
  ...FIT_FILTERS.map(({ column }) => ({
    header: CLASS_LABELS[column].label,
    value: (row: ShoeSummaryRow) => (row[column] == null ? null : fitLabel(column, row[column])),
  })),
];

/**
 * One CSV cell (RFC 4180). Brand and model are typed in by users, so text a spreadsheet
 * would run as a formula (starting with =, +, -, @, tab or CR) gets a leading apostrophe.
 */
function csvCell(value: CsvValue): string {
  if (value == null) {
    return "";
  }
  let text = String(value);
  if (typeof value === "string" && /^[=+\-@\t\r]/.test(text)) {
    text = `'${text}`;
  }
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

/** The shoe list as CSV: a header row, then one row per shoe, CRLF line endings. */
export function shoesToCsv(rows: ShoeSummaryRow[]): string {
  const lines = [CSV_COLUMNS.map((column) => csvCell(column.header))];
  for (const row of rows) {
    lines.push(CSV_COLUMNS.map((column) => csvCell(column.value(row))));
  }
  return lines.map((cells) => cells.join(",")).join("\r\n") + "\r\n";
}
