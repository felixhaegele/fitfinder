# 0005. Segment the insole by thresholding a lighting-flattened page inside the measuring zone

- **Status:** Accepted
- **Date:** 2026-10-18

## Context

After the homography (#21), the worker has a top-down image of the template page at 10 px/mm. It must find the insole's outline in that image, to well under 1 mm, or reject the photo with a reason the user can act on. Every measurement (#23) and the classification (#24) start from this outline.

The forces:

- **Real photos are uneven.** Light falls off across the sheet, lamps cast soft shadows, and phones add noise and blur. Insoles range from black foam to light grey fabric, often with a printed logo or perforations.
- **We control the background.** The insole lies on white paper inside a known band (the measuring zone, ADR 0004), and nothing dark is printed there. Only light grey dashed guides mark the band's border.
- **We must say *why* a photo fails.** The user should hear "too dark" or "the insole goes over the lines", not get a wrong measurement.
- **Boring and testable.** It runs on Cloud Run and must be deterministic for regression tests, with no training data yet.

## Decision

We will segment with classic image processing in `worker/app/pipeline/segment.py`, as a pure function. All thresholds live in `config.py`.

1. **Search region:** the measuring zone, shrunk by 1.5 mm so the dashed guides stay out, and limited to what the photo actually shows.
2. **Too dark:** reject (`too_dark`) when the paper's 90th-percentile brightness is below 60/255.
3. **Flatten the lighting.** We estimate the paper's brightness at every point with a grey-level *closing*: a max filter, then a min filter, over a 121 mm window at 1 px/mm. Because the window is wider than any insole, it replaces the insole with the surrounding paper but keeps slow light gradients. Dividing by this estimate makes the paper ≈ 1.0 everywhere.
4. **Threshold:** Otsu separates insole from paper. The final threshold sits halfway between the two groups' median levels, where a blurred edge's true position is, so blur doesn't grow or shrink the insole. A 0.7 mm opening/closing removes specks. We keep the largest blob and fill its holes (logos, perforations). If no blob is big enough or the contrast is under 15 %, we reject with `insole_not_found`.
5. **Too blurry:** for a Gaussian-blurred step edge, the steepest slope is contrast / (σ·√(2π)). The median slope along the outline therefore gives the blur σ in mm, independent of brightness. We reject (`too_blurry`) above 0.5 mm. The limit is set by the *markers*: in the synthetic tests, blurred marker corners skew the homography by ~0.6 mm at 0.6 mm blur, while segmentation itself stays within ~0.1 mm.
6. **Touches the edge:** if ≥ 1 mm of the blob lies on the search region's border, the insole was cut off by the guides, the paper edge or the photo's edge. We reject with `insole_touches_edge`.

The checks run in that order, so the user hears the reason that blocks the steps after it.

## Alternatives considered

- **One global Otsu threshold on the raw page.** Simplest, and enough for the #21 test rectangle. It fails under a light gradient: the dark end of the paper can be darker than a light insole at the bright end. Flattening first keeps Otsu's simplicity and removes the failure.
- **Adaptive (local) thresholding** (`cv2.adaptiveThreshold`). It handles gradients, but its window is small compared with the insole. Inside a large uniform insole the local mean equals the insole itself, which leaves holes and false edges. A window bigger than the insole is exactly the closing we use, done properly.
- **Edge detection (Canny) and contour following.** Accurate on clean edges, but fabric texture, noise and logos create spurious edges, and gaps break the contour. A region-based method closes the outline by construction.
- **GrabCut / watershed.** More flexible, but slower (seconds at 2100 × 2970 px), and they need seeds and iteration counts to tune. They're harder to explain and to keep deterministic across OpenCV versions. Our controlled white background doesn't need them.
- **Colour-based segmentation** (distance from the paper colour in Lab space). It would catch light but saturated insoles, such as yellow ones, that look pale in grey. Our fixtures are greyscale, and real colour photos aren't available yet. This is the first thing to add if `insole_not_found` shows up for coloured insoles.
- **A learned model** (U-Net, Segment Anything). Robust to almost anything, but it needs labelled training data we don't have yet. It adds a large dependency and image size to the worker, and its behaviour is hard to pin down in regression tests. Reconsider in v2, once crowd data provides real labelled photos.
- **Variance of the Laplacian as the blur measure.** Common and cheap, but its value depends on image content (texture, insole colour, noise), so one threshold doesn't fit all photos. The edge-slope estimate is in millimetres and directly tied to measurement accuracy.

## Consequences

- Segmentation takes about 0.1 s per page. On the synthetic fixtures it is within 0.25 mm of the true outline, with overlap above 99.7 %.
- Insoles must be visibly darker than the paper (≥ 15 % contrast after flattening). Very light or white insoles are rejected with a message that says so. Colour support is the planned remedy.
- The search region is the measuring zone. An insole that lies over the dashed guides is rejected even if it is still on white paper. That is stricter than necessary, but it's simple and explains itself to the user ("place it inside the dashed lines").
- The outline is pixel-accurate (0.1 mm). Sub-pixel refinement can be added later, in #23, if the tolerances need it.
- Blur tolerance is limited by marker detection, not segmentation. Improving marker corner accuracy on blurred photos would let us relax `MAX_EDGE_BLUR_MM`.
