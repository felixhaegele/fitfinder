// How each submission status is shown to the user. Kept apart from the pages so it can be
// unit tested and stays consistent between the list and the detail page.

import type { Database } from "@/lib/database.types";

export type SubmissionStatus = "queued" | "processing" | "done" | "rejected" | "failed";

export const STATUS_COPY: Record<
  SubmissionStatus,
  { label: string; description: string; tone: "neutral" | "busy" | "good" | "bad" }
> = {
  queued: {
    label: "Waiting",
    description: "Waiting to be measured. This usually takes a minute or two.",
    tone: "neutral",
  },
  processing: { label: "Measuring", description: "Measuring your insole…", tone: "busy" },
  done: { label: "Measured", description: "Your insole has been measured.", tone: "good" },
  rejected: {
    label: "Not measurable",
    description: "We couldn't measure this photo.",
    tone: "bad",
  },
  failed: {
    label: "Error",
    description: "Something went wrong on our side. Please upload the photo again.",
    tone: "bad",
  },
};

/** Statuses that still change by themselves; the detail page keeps refreshing for these. */
export function isInProgress(status: string): boolean {
  return status === "queued" || status === "processing";
}

export function statusCopy(status: string) {
  return STATUS_COPY[(Object.hasOwn(STATUS_COPY, status) ? status : "failed") as SubmissionStatus];
}

/** 272.456 → "272.5 mm". Measurements are stored in mm. */
export function formatMm(value: number | null | undefined): string {
  return value == null ? "–" : `${value.toFixed(1)} mm`;
}

type Classification = Database["public"]["Tables"]["classifications"]["Row"];

export const CLASS_LABELS: Record<
  "width_class" | "arch_class" | "toe_box_shape" | "toe_shape",
  { label: string; values: Record<string, string> }
> = {
  width_class: { label: "Width", values: { narrow: "Narrow", regular: "Regular", wide: "Wide" } },
  arch_class: { label: "Arch", values: { low: "Low", medium: "Medium", high: "High" } },
  toe_box_shape: {
    label: "Toe box",
    values: { round: "Round", square: "Square", pointed: "Pointed" },
  },
  toe_shape: {
    label: "Toe shape",
    values: {
      egyptian: "Egyptian (big toe longest)",
      roman: "Roman (first toes even)",
      greek: "Greek (second toe longest)",
    },
  },
};

/**
 * Toe box and toe shape come from the insole, so they describe the shoe's toe box and
 * the foot type it suits, not the user's own foot (owner note on #24).
 */
export const TOE_LABELS_NOTE =
  "Toe box and toe shape describe this shoe's toe box and the foot type it suits, not your own foot.";

export function classificationRows(c: Pick<Classification, keyof typeof CLASS_LABELS>) {
  return (Object.keys(CLASS_LABELS) as (keyof typeof CLASS_LABELS)[]).map((key) => ({
    label: CLASS_LABELS[key].label,
    value: CLASS_LABELS[key].values[c[key]] ?? c[key],
  }));
}
