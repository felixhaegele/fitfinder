// Matching a foot to shoe sizes for "find by size" (/shoes/for-my-feet, ADR 0015). Pure
// functions, so the parsing of untrusted query parameters and the matching rule can be
// unit tested. All thresholds live here.

/** Added to the foot length: the insole has to be at least this much longer than the foot. */
export const DEFAULT_WIGGLE_MM = 7;

/**
 * How much longer than foot + wiggle room an insole may be and still count as a match.
 * About one and a half EU sizes (one EU size is 6.67 mm): enough to always catch the next
 * measured size up, not so much that a size far too big is listed.
 */
export const MAX_EXTRA_LENGTH_MM = 10;

/**
 * How much narrower than the foot the insole may be at the ball. 0: at least as wide as the
 * foot. Feet often spread a little over the insole's edge, so this may need loosening.
 */
export const WIDTH_TOLERANCE_MM = 0;

export const FOOT_LIMITS = {
  length: { min: 150, max: 350 },
  width: { min: 50, max: 150 },
  wiggle: { min: 0, max: 30 },
} as const;

export type Foot = { lengthMm: number; widthMm: number; wiggleMm: number };

export type FootQuery = {
  /** The raw values, to fill the form in again. */
  values: { length: string; width: string; wiggle: string };
  /** Null until both length and width are given and valid. */
  foot: Foot | null;
  error: string | null;
};

type SearchParams = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined): string {
  return ((Array.isArray(value) ? value[0] : value) ?? "").trim().slice(0, 10);
}

/** "254", "254.5" or "254,5" → 254.5. Anything else → null. */
function parseMm(raw: string): number | null {
  if (!/^\d{1,3}([.,]\d)?$/.test(raw)) {
    return null;
  }
  return Number(raw.replace(",", "."));
}

function inRange(value: number | null, { min, max }: { min: number; max: number }): value is number {
  return value !== null && value >= min && value <= max;
}

/**
 * Turns the URL's query parameters into a foot. An empty form is no error, just no search
 * yet; a blank or invalid wiggle room falls back to the default.
 */
export function parseFootQuery(params: SearchParams): FootQuery {
  const values = { length: first(params.length), width: first(params.width), wiggle: first(params.wiggle) };
  if (values.length === "" && values.width === "") {
    return { values, foot: null, error: null };
  }

  const length = parseMm(values.length);
  const width = parseMm(values.width);
  const wiggle = parseMm(values.wiggle);
  const { length: l, width: w } = FOOT_LIMITS;
  if (!inRange(length, l)) {
    return { values, foot: null, error: `Please enter your foot length in mm, between ${l.min} and ${l.max}.` };
  }
  if (!inRange(width, w)) {
    return { values, foot: null, error: `Please enter your foot width in mm, between ${w.min} and ${w.max}.` };
  }
  const wiggleMm = inRange(wiggle, FOOT_LIMITS.wiggle) ? wiggle : DEFAULT_WIGGLE_MM;
  return { values, foot: { lengthMm: length, widthMm: width, wiggleMm }, error: null };
}

/** The columns of a shoe_fit_sizes row that matching needs. */
export type SizeRow = {
  shoe_model_id: string;
  median_length_mm: number | null;
  median_ball_width_mm: number | null;
};

export type SizeMatch<R extends SizeRow> = {
  row: R;
  /** Insole length minus foot length: includes the wiggle room. */
  spareLengthMm: number;
  /** Insole ball width minus foot width; negative within WIDTH_TOLERANCE_MM. */
  spareWidthMm: number;
};

/**
 * Per shoe, the shortest measured size whose insole is at least foot length + wiggle room
 * (but at most MAX_EXTRA_LENGTH_MM more) and wide enough at the ball. Ordered by length,
 * never by size number: one shoe can have sizes in several size systems. Closest fits
 * first.
 */
export function matchSizes<R extends SizeRow>(rows: readonly R[], foot: Foot): SizeMatch<R>[] {
  const needed = foot.lengthMm + foot.wiggleMm;
  const best = new Map<string, R>();
  for (const row of rows) {
    const length = row.median_length_mm;
    const width = row.median_ball_width_mm;
    if (length == null || width == null) {
      continue;
    }
    if (length < needed || length > needed + MAX_EXTRA_LENGTH_MM || width < foot.widthMm - WIDTH_TOLERANCE_MM) {
      continue;
    }
    const current = best.get(row.shoe_model_id);
    if (!current || length < current.median_length_mm!) {
      best.set(row.shoe_model_id, row);
    }
  }

  return [...best.values()]
    .map((row) => ({
      row,
      spareLengthMm: row.median_length_mm! - foot.lengthMm,
      spareWidthMm: row.median_ball_width_mm! - foot.widthMm,
    }))
    .sort((a, b) => a.spareLengthMm - b.spareLengthMm);
}
