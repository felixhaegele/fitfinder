# 0009. Measure insoles in one heel-to-toe frame, found from the outline's shape

- **Status:** Accepted
- **Date:** 2026-10-18

## Context

Segmentation (ADR 0005) gives the insole's outline in page millimetres. The insole lies diagonally (ADR 0004), and real users lay it a bit crooked, off-centre, or even the wrong way round. Length, widths, the classifier (#24) and later crowd averages (v2) and foot-scan matching (v3) all need the outline in a **fixed frame**, so outlines can be compared and overlaid.

The owner fixed that frame on 2026-10-18 ("option A", comments on #23 and #52), and it is used in the tests, the pipeline and the database:

- millimetres, y up, seen from above; the heel point is (0, 0), the toe tip (0, L): the toe points along +y;
- right is the canonical foot: left insoles are mirrored (x → −x), so the medial side is always at −x, and the original side is stored;
- 256 points, evenly resampled, ordered heel → medial → toe → lateral.

The measurement definitions in `worker/tests/insoles.py` use the line from the heel point to the toe tip as the axis. Two things are still open: how to find that line on a real outline, and how to tell left from right, because the upload form doesn't ask which insole it is.

## Decision

We will measure in `worker/app/pipeline/measure.py`, as pure functions. The tunable numbers live in `config.py`.

1. **Smooth.** Resample the pixel contour every 0.1 mm and smooth it along its length (Gaussian, σ = 0.4 mm). This removes the pixel staircase, whose length depends on the edge's direction, so "evenly spaced" is really even. Real edges move by about 0.01 mm.
2. **First guess of the axis.** Use the principal axis of the outline's area (second moments via Green's theorem, so uneven vertex spacing doesn't bias it).
3. **Heel or toe.** The half with more area (by at least 5 %) is the forefoot. This holds however the insole lies, even reversed. Only when the halves are nearly equal does the template's `insole_axis` decide.
4. **Heel point and toe tip.** Take the two extreme points along the axis, aim the axis through them, and repeat until they stop changing. Each round can only lengthen the heel-toe distance, so this settles in a few rounds. It ends exactly where the definition needs it: the heel point and toe tip are the extremes along the line that joins them, so the length is both their distance and the outline's extent.
5. **Side.** Only the medial edge cuts in at the arch. In the frame before mirroring, the narrower half across 30–60 % of the length is medial. A left insole seen from above has its medial side on the right (+x). Callers can pass the side explicitly instead.
6. **Measure** along y with the definitions in `tests/insoles.py` (the module's constants are checked against them), on the full-resolution outline. Then mirror a left insole and resample to 256 points, starting exactly at (0, 0).

## Alternatives considered

- **Principal axis only (no heel-toe re-aiming).** It is the most stable choice, but the toe tip would not be at (0, L), which breaks the owner's frame and the definitions.
- **Template `insole_axis` only.** Simple, but a crooked insole (5° is realistic) skews every width, and a reversed one would be measured back to front.
- **Longest chord (the outline's diameter) as the axis.** On insole shapes it usually gives the same line as step 4 (both are lines whose ends are the extremes along them). But it needs a convex hull and rotating calipers, or an O(n²) search, while step 4 is a few lines of code. It also has no link to the principal axis, so a stray blob at one end would decide it alone.
- **Asking the user for the side.** That is more reliable for odd shapes, but the form doesn't have the field yet. Inference works on every fixture, and `measure_insole(side=…)` is ready if the owner adds the field.

## Consequences

- One frame everywhere. The DB check on `measurements.outline_mm` (#52) enforces 256 points and the heel point at the origin.
- On a **square toe** the "toe tip" is not unique: in a nearly flat toe end, the frontmost point slides to a corner, so the axis tilts by about 2–3° towards it. Lengths and widths stay well within tolerance (fixtures: ≤ 0.6 mm at 95 %, against 2.5 mm allowed). But anything read off the toe end's slant (#24's `toe_shape`) must allow for that tilt, or define the slant relative to something more stable.
- Side detection relies on the arch cut-in. A nearly symmetric insole (some flat aftermarket insoles) could be read as the wrong side. That changes only which way it is mirrored and the `side` label, not the widths.
- Measuring takes about 0.1 s per photo.
