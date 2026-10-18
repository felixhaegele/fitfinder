# 0004. Place the insole diagonally on an A4 template described by one geometry JSON

- **Status:** Accepted
- **Date:** 2026-10-18

## Context

Users photograph an insole on a printed sheet. The measurement worker finds ArUco markers on the sheet, computes a homography and measures the insole in millimetres. Two forces shape the sheet:

1. **The insole must lie completely on white paper.** Segmentation needs a clean background around the whole outline. An insole that hangs off the paper can't be measured.
2. **Almost everyone has A4, almost nobody has A3.** A4 is 210 × 297 mm. With a small border, laying the insole lengthwise leaves about 290 mm, roughly EU 45. Many cyclists wear EU 45–47.

The printed geometry (where the markers are, where the insole goes) must be known exactly by both the PDF generator and the worker. If the two copies drift apart, every measurement is wrong without any error.

## Decision

We will place the insole **diagonally**, with the heel towards the bottom-left and the toes towards the top-right, and with white paper all around it (it never touches the paper edge). The measuring zone is a 120 mm wide band along the page diagonal.

We will put the 4 markers (DICT_4X4_50, IDs 0–3, 20 mm) and two 100 mm rulers, one horizontal and one vertical, in the two free triangles beside the band. Nothing dark is printed inside the band. Its edges are light-grey dashed guides.

We will describe the template in **one JSON file per template version** (`print/geometry/a4-v1.json`), validated by a JSON Schema. The generator draws only from that file, and the worker will read the same file. Any geometry change gets a new template id (`a4-v2`), so old photos stay interpretable.

## Alternatives considered

- **Lengthwise on A4, markers in the corners.** About 291 mm usable, and only room for one ruler. The diagonal gives a little more length (about 297 mm for a typical insole profile, because the paper corners limit the heel and toe), plus room for both rulers. It also matches how users would naturally fit a long insole on the sheet.
- **A3 template.** Fits every size, but most home printers can't print it. Could be added later as `a3-v1` with different marker IDs, so the worker can tell the templates apart.
- **Two taped A4 sheets.** Error-prone: the tape joint misaligns the markers.
- **Hard-coding geometry in both the generator and the worker.** Drift would go unnoticed. The shared JSON plus a test that detects markers in the rendered PDF prevents this.

## Consequences

- Insoles up to roughly 295–300 mm (about EU 46) fit. Bigger ones must be rejected with a clear message ("insole touches the edge of the paper") until an A3 template exists.
- The worker can't assume the insole is axis-aligned. It must rotate the outline into a heel-to-toe frame (using `insole_axis` from the JSON plus the shape's principal axis) before measuring length and widths. This frame is also what makes stored outlines comparable across submissions.
- Two rulers let users catch printers that scale only one axis.
- The worker's Docker build will need access to `print/geometry/`. Today the build context is `worker/`, so this has to be solved when the worker starts reading the JSON (#21).
