/**
 * Owner details shown on the privacy notice (/privacy) and the terms (/terms).
 *
 * These are owner decisions, not code: until a value is set, the pages show
 * PENDING instead, so nothing made-up is ever published. Fill them in (and
 * have both pages reviewed) before real users sign up.
 */

/** Who runs FitFinder: the "controller" under GDPR / Swiss FADP and the other party to the terms. */
export const OPERATOR_NAME: string | null = null;

/** Postal address of the operator. Required for the privacy notice (GDPR Art. 13(1)(a)). */
export const OPERATOR_ADDRESS: string | null = null;

/** Where people send privacy requests and questions (#94). Not the owner's personal address. */
export const CONTACT_EMAIL: string | null = null;

/**
 * Law and courts for the terms, e.g. "Swiss law; courts at <city>". Depends on where the
 * operator lives. Consumers keep the mandatory protection of their own country either way.
 */
export const GOVERNING_LAW: string | null = null;

/** Minimum age to create an account. 16 is the GDPR default age of consent (Art. 8). */
export const MINIMUM_AGE = 16;

export const PENDING = "[to be added before launch]";

/** Anchor of the "Reporting content" section on /terms. */
export const REPORTING_ANCHOR = "reporting";

/**
 * Where a "report" link points: an email to CONTACT_EMAIL with the subject filled in, or,
 * until that is set, the reporting section of the terms.
 */
export function reportHref(subject: string, contactEmail: string | null = CONTACT_EMAIL): string {
  return contactEmail
    ? `mailto:${contactEmail}?subject=${encodeURIComponent(subject)}`
    : `/terms#${REPORTING_ANCHOR}`;
}
