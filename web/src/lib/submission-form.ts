// Validation for the upload form. Runs on the server (the server action) and is also
// used by the client for early feedback. The database enforces the same rules again.

export const SIZE_SYSTEMS = {
  eu: { label: "EU", min: 30, max: 52 },
  uk: { label: "UK", min: 1, max: 16 },
  us_m: { label: "US men's", min: 2, max: 17 },
  us_w: { label: "US women's", min: 3, max: 18 },
  mondopoint: { label: "Mondopoint (mm)", min: 200, max: 340 },
} as const;

export type SizeSystem = keyof typeof SIZE_SYSTEMS;

/** Worn insoles compress and stretch, so measurements may later be treated differently. */
export const INSOLE_CONDITIONS = {
  new: "New (never worn)",
  used: "Used (has been worn)",
} as const;

export type InsoleCondition = keyof typeof INSOLE_CONDITIONS;

export type SubmissionInput = {
  shoe: { kind: "existing"; id: string } | { kind: "new"; brand: string; model: string; year: number };
  size: number;
  sizeSystem: SizeSystem;
  insoleCondition: InsoleCondition;
  imagePath: string;
};

export type ParseResult = { ok: true; value: SubmissionInput } | { ok: false; error: string };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export const NEW_SHOE = "new";

function text(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === "string" ? value.trim() : "";
}

function isSizeSystem(value: string): value is SizeSystem {
  return Object.hasOwn(SIZE_SYSTEMS, value);
}

/** Checks the upload form. `userId` is the logged-in user: photos must be in their folder. */
export function parseSubmission(form: FormData, userId: string): ParseResult {
  if (form.get("consent") !== "on") {
    return { ok: false, error: "Please agree to the photo being stored and measured." };
  }

  let shoe: SubmissionInput["shoe"];
  const shoeId = text(form, "shoeModelId");
  if (shoeId === NEW_SHOE) {
    const brand = text(form, "brand");
    const model = text(form, "model");
    const year = Number(text(form, "year"));
    const maxYear = new Date().getFullYear() + 1;
    if (!brand || brand.length > 100 || !model || model.length > 200) {
      return { ok: false, error: "Please enter the brand and model of your shoe." };
    }
    if (!Number.isInteger(year) || year < 1990 || year > maxYear) {
      return { ok: false, error: `Please enter a model year between 1990 and ${maxYear}.` };
    }
    shoe = { kind: "new", brand, model, year };
  } else if (UUID.test(shoeId)) {
    shoe = { kind: "existing", id: shoeId };
  } else {
    return { ok: false, error: "Please choose your shoe model." };
  }

  const sizeSystem = text(form, "sizeSystem");
  if (!isSizeSystem(sizeSystem)) {
    return { ok: false, error: "Please choose a size system." };
  }
  // Half sizes are common (EU 42.5, US 9.5); one decimal place is what the DB stores.
  // Checked on the text, not the number: 1.1 * 10 isn't exactly 11 in floating point.
  const rawSize = text(form, "size").replace(",", ".");
  const size = Number(rawSize);
  const range = SIZE_SYSTEMS[sizeSystem];
  if (!/^\d{1,3}(\.\d)?$/.test(rawSize) || size < range.min || size > range.max) {
    return {
      ok: false,
      error: `Please enter a ${range.label} size between ${range.min} and ${range.max}.`,
    };
  }

  const insoleCondition = text(form, "insoleCondition");
  if (!Object.hasOwn(INSOLE_CONDITIONS, insoleCondition)) {
    return { ok: false, error: "Please tell us whether the insole is new or used." };
  }

  const imagePath = text(form, "imagePath");
  if (!imagePath.startsWith(`${userId}/`) || imagePath.includes("..")) {
    return { ok: false, error: "The photo upload didn't finish. Please try again." };
  }

  return {
    ok: true,
    value: {
      shoe,
      size,
      sizeSystem,
      insoleCondition: insoleCondition as InsoleCondition,
      imagePath,
    },
  };
}
