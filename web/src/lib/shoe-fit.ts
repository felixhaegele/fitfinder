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
