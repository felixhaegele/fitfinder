# 0015. Match a foot to the shortest measured size that is long and wide enough

- **Status:** Proposed
- **Date:** 2026-11-10

## Context

Besides browsing by model and fit labels ("Find by model", `/shoes`), visitors should be able to enter their own foot length and width and get a list of shoes that fit ("Find by size", `/shoes/for-my-feet`). A shoe needs some room in front of the toes, so the owner asked for a "wiggle room" field, 7 mm by default, that is added to the foot length.

Length only means something per size: a shoe's median over all its sizes (`shoe_fit_summaries`) says nothing about any one size. The per-size numbers exist (`shoe_fit_by_size`), but only for one shoe at a time.

ADR 0011 makes every new public function output a privacy decision.

## Decision

We will add `public.shoe_fit_sizes()`. It returns the rows of `shoe_fit_by_size` for every shoe at once, plus the shoe's brand, model and year, and follows the rules of ADR 0011 (security definer, empty `search_path`, execute for `anon` and `authenticated` only, column list pinned by pgTAP). It shows nothing that isn't already public on the `/shoes/[id]` pages, so the privacy boundary doesn't move.

The matching runs in the web app (`web/src/lib/foot-match.ts`), where all thresholds live:

- needed length = foot length + wiggle room (default `DEFAULT_WIGGLE_MM` = 7 mm, 0–30 mm allowed);
- a size matches if its median insole length is at least the needed length and at most `MAX_EXTRA_LENGTH_MM` (10 mm, about one and a half EU sizes) more, and its median ball width is at least the foot width minus `WIDTH_TOLERANCE_MM` (0 mm);
- per shoe, the shortest matching size is shown. Sizes are compared by measured length, never by size number, because one shoe can have sizes in several size systems;
- results are ordered by spare length, closest fit first.

The form is a plain GET form, like `/shoes`, so a search works without JavaScript and has a shareable URL.

## Alternatives considered

- **Match in SQL** (a function that takes the foot). It sends fewer rows, but puts the rule into a migration, so every threshold change needs a new migration and a pgTAP change. At v1 volumes, sending all size rows is cheap. If it gets slow, the rule can move behind the same page.
- **No upper length limit.** A shoe measured only in EU 47 would be listed for a 250 mm foot. Rejected.
- **Strict width only from classification labels** (e.g. "wide feet → wide shoes"). The labels are relative to length; the visitor knows their width in mm. Rejected.

## Consequences

- Only sizes someone has measured can appear; the page says so. A shoe that would fit in an unmeasured size is missing.
- The width rule is an assumption: feet often spread a little over the insole's edge, so a strict "at least as wide as the foot" may leave out shoes that fit. `WIDTH_TOLERANCE_MM` is the knob; the owner should confirm it.
- The page reads every size row of every shoe per search. Revisit with the other aggregates (ADR 0011) when it shows in timings.
