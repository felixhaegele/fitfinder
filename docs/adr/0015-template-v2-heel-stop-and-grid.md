# 0015. Template v2: keep the diagonal A4, add a fold-line heel stop, rulers along the band and a light grid

- **Status:** Proposed
- **Date:** 2026-11-18

## Context

The owner measured a black foam insole about **5 mm longer** than the pipeline did (277.8 mm, #133). Neither pressing it flat nor the print scale (checked with a ruler on the sheet) explains the difference. The outline sits on the insole's edge to within 0.5 mm.

**The likely cause is the page mapping in the marker-free corners.** The heel and the toe lie in the two corners without markers (bottom-left, top-right). There the single homography fitted to the four markers is extrapolated. The photos came from a document-scanner app, which bends and crops the image on its own and returns only ~6 px/mm. Two checks on these scans show this:
- **Leaving one marker out:** a homography fitted to the other three predicts its corners **0.4–2.1 mm** off. On the synthetic fixtures it's 0.02 mm. So the scanner output isn't a clean perspective view of the page.
- **Near markers 0–1** the printed 100 mm ruler measures 100.2 mm. That checks the scale only there, not in the heel and toe corners.

The insole's height doesn't explain a *shortfall*. A raised heel cup or toe is pushed away from the point below the camera, which makes the outline *longer*. Height and camera position remain a second-order error in the other direction, especially for widths. (The test in #133 that tells the two apart: a flat dark card of known length, photographed with the scanner app and with the Camera app.)

Users also have no way to check a result themselves. And the owner wants the template to stay usable for **foot measuring later** (v3, out of scope: don't build, don't block).

The owner decided on **diagonal A4** for v2, as in v1. A4 is what people have, and the diagonal is what makes room for long insoles.

## Decision

We will add a new template `a4-v2` (`print/geometry/a4-v2.json`) next to `a4-v1`. v1 stays valid: people have it printed, and old photos must stay interpretable. The layout stays diagonal: heel at the bottom-left, toes at the top-right. v2 adds the following.

1. **A heel stop from a fold line.** A printed line across the insole axis, **30 mm along the axis from the bottom-left corner**, running from (0, 260.3) to (52.0, 297) mm. The user folds the corner under along it, or cuts it off. The new straight edge is exactly perpendicular to the axis.
   - The user lays the sheet with this edge against a wall or a book, and pushes the insole's heel against it.
   - That gives a repeatable heel position, consistent placement, and the 0 for the rulers and the grid. It's also the heel reference for foot tracing later (see below).
   - **Open question, not decided here:** using the edge as the heel point, instead of the outline's extreme point. It would make the heel end independent of the camera, but it changes ADR 0009's length definition. That means a major `PIPELINE_VERSION` bump, and v1 and v2 lengths would no longer be comparable. It also gives wrong results when the insole doesn't actually sit against the edge. Decide it once real v2 photos exist.
   - The fold costs almost nothing. With the largest fixture's shape scaled to fit, the longest insole that fits goes from ~297 mm (v1, heel ~28 mm from the corner) to ~295.5 mm. The corner is too narrow for the heel to come closer anyway. At 25 mm the limit drops to ~253 mm, at 40 mm to ~286.5 mm, so 30 mm is the sweet spot.
2. **Length rulers along both long edges of the measuring band, 0 at the heel line**, outside the band and its margin. The bottom-right edge has room from 16 to 244 mm from the heel line, the top-left edge from 60 to 288 mm. Their two jobs:
   - **Users** can read the length on the sheet, looking straight down at the toe.
   - **The worker** reads the ticks in every photo and rejects the photo when they don't fit the homography. That catches curled paper, a scanner app's warping, and lens distortion, which is the likely cause above, so **this is the part of v2 that addresses it**. It does **not** catch a uniformly scaled print, because the printed ruler scales with it. For that we keep step 4.
   - The edge rulers don't reach the heel and toe corners, where the error is largest. The check there has to come from the grid (step 3): its lines and labels reach into both corners.
3. **A light grey grid inside the band, aligned with the insole axis, every 10 mm.** Lines across the axis are labelled with the distance from the heel line (needed at the toe end, where no edge ruler reaches past ~288 mm). Lines along the axis are labelled with the offset from the centre line. Together they make a ruler for length and width everywhere.
   - Lines and labels must stay **lighter than the segmentation threshold** (paper ≈ 1.0, threshold ≈ 0.55–0.6 after flattening; target ≈ 0.85) and **thinner than `CLEANUP_KERNEL_MM`** (0.7 mm), so ADR 0005's segmentation keeps working. This replaces ADR 0004's rule that "nothing is printed inside the band" with "nothing *dark* is printed inside the band".
   - The grid gives mapping points **in the heel and toe corners**, which four markers can't. The worker can check the mapping there, and later correct it locally (a piecewise mapping instead of one homography).
4. **Keep the two 100 mm print-check rulers and the instruction "check both rulers measure exactly 100 mm".** A real ruler is the only way to catch wrong print scaling.
5. **New marker IDs 4–7** (still DICT_4X4_50, 20 mm, same corners as v1). The worker picks the geometry by the IDs it finds, so v1 and v2 sheets both work.
6. **Instructions on the sheet** in the free triangles: fold or cut, against a wall, heel against the edge, Camera app (not a scanner app), phone level and straight above, soft light.

For **feet (v3)**, the same sheet would support the usual home method: *sheet against the wall, heel against the wall, trace the foot with a pen held upright, photograph the tracing.* A drawn outline is flat, so it has no height error and no shadow. v2 only has to avoid blocking that: the heel stop, the 0 line and ~295 mm of room are already there. Tracing support itself is v3:
- closing the line's gap at the wall;
- correcting for the pen's offset (the line runs 2–4 mm outside the foot when the pen leans on it);
- a form field to say whether the photo shows an insole or a tracing.

## Alternatives considered

- **Straight layout with a wall edge.** It gives the simplest wall stop, but leaves only ~285 mm on A4. The owner chose diagonal A4.
- **A3 or two taped A4 sheets.** Most home printers can't print A3, and the joint between two sheets misaligns the markers (ADR 0004).
- **A 1 mm grid.** At 10–13 px/mm in a phone photo it causes moiré, disturbs segmentation and adds no accuracy, because edges are already located to ~0.1 mm. 10 mm is enough to read by eye and for a local correction.
- **A printed 1 cm black line to put the heel against.** A dark insole merges with a black line, so the heel's edge disappears. An overlap onto the line can't be seen, only a gap can. And a printed line isn't a physical stop the way a wall is.
- **More markers instead of a grid.** Markers in the heel and toe corners would fix the mapping there best, but those corners are where the insole lies. A light grid is the only reference that can sit under and around the insole.
- **A black grid, to make shadows visible (#121).** It would survive shadows better, but black lines inside the band disturb segmentation, and they don't help when a shadow is clipped to black. Shadows are handled by capture guidance first (#121, #133).
- **A heel mark without a fold (print only).** Simpler for users, but it isn't a physical stop. It doesn't remove the tilt error at the heel, and it doesn't help feet later.

## Consequences

- Two templates in parallel. The worker chooses the geometry by marker IDs, and both need fixtures. `PIPELINE_VERSION` gets a bump when the worker learns v2.
- Users must fold or cut once and use a wall or book. That's an extra step, which the instructions and the upload page must explain. If the fold is crooked, the worker can see it, because the paper edge doesn't match the printed fold line, and can then fall back to the outline's heel point.
- The grid labels and rulers fill the free triangles more. The PDF generator must lay out markers, rulers, labels and text without overlap, and the marker-detection test (#19) must pass for v2.
- In v2 the heel is *meant* to touch the heel-stop edge, so the `insole_touches_edge` check (ADR 0005) must exempt that edge of the measuring zone and still apply to every other edge.
- New rejection: a ruler check that fails gets its own code (e.g. `page_distorted`) and message.
- What has to be built, in order (#133): generator and `a4-v2.json`; worker geometry by marker IDs and the ruler/grid self-check; optionally the local correction from the grid. Using the heel stop as the heel point stays an open question (Decision 1).
- Still open: the flat-card test in #133 (step 0) should confirm that the mapping in the corners, not the insole's height, causes the shortfall.
