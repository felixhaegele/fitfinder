"""Debug overlay: what the pipeline saw, drawn on the photo (#26).

Draws on the upright photo, not the warped page, so a wrong marker or a skewed warp is
easy to spot:

- detected ArUco markers (green, with their id); template markers that weren't found,
  where the homography expects them (red);
- the measuring zone (grey) and the insole contour (yellow);
- the measurement lines: length (magenta) and the heel, arch, ball and toe widths.

Nothing here measures anything. The lines come from `measure.locate_insole` and
`measure.measurement_lines`, the same functions that produce the numbers.
"""

import cv2
import numpy as np

from app.pipeline.measure import Side, locate_insole, measurement_lines
from app.pipeline.segment import Segmentation
from app.pipeline.template import FloatArray
from app.pipeline.warp import Image, PageWarp

# BGR
GREEN = (60, 200, 60)
RED = (40, 40, 230)
GREY = (160, 160, 160)
YELLOW = (0, 220, 255)
MAGENTA = (220, 60, 220)
WIDTH_COLOURS = {
    "heel_width_mm": (255, 140, 0),
    "arch_width_mm": (0, 160, 255),
    "ball_width_mm": (255, 60, 60),
    "toe_width_85_mm": (180, 120, 255),
    "toe_width_90_mm": (180, 120, 255),
    "toe_width_95_mm": (180, 120, 255),
}
LABELS = {
    "heel_width_mm": "heel",
    "arch_width_mm": "arch",
    "ball_width_mm": "ball",
    "toe_width_85_mm": "toe 85%",
    "toe_width_90_mm": "toe 90%",
    "toe_width_95_mm": "toe 95%",
}


def _px(points: FloatArray) -> np.ndarray:
    return np.round(points).astype(np.int32).reshape(-1, 1, 2)


def draw_overlay(
    photo: Image,
    markers: dict[int, FloatArray],
    warp: PageWarp | None = None,
    segmentation: Segmentation | None = None,
    side: Side | None = None,
) -> Image:
    """A copy of `photo` (BGR) with whatever the pipeline got to before it stopped.

    `markers` are detected corners in photo pixels (`markers.detect_markers`). `warp` and
    `segmentation` are None when the photo was rejected before those steps.
    """
    out = photo.copy()
    scale = max(1.0, min(out.shape[:2]) / 1000)
    thick = max(2, round(2 * scale))
    font = 0.6 * scale

    def text(label: str, at: FloatArray, colour: tuple[int, int, int]) -> None:
        x, y = (int(v) for v in np.round(at))
        cv2.putText(
            out, label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, font, (0, 0, 0), thick + 2, cv2.LINE_AA
        )
        cv2.putText(out, label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, font, colour, thick, cv2.LINE_AA)

    for marker_id, corners in sorted(markers.items()):
        cv2.polylines(out, [_px(corners)], True, GREEN, thick, cv2.LINE_AA)
        text(f"id {marker_id}", corners[0], GREEN)

    if warp is None:
        return out

    for marker_id, corners_mm in sorted(warp.template.marker_corners_mm.items()):
        if marker_id not in markers:
            expected = warp.mm_to_photo(corners_mm)
            cv2.polylines(out, [_px(expected)], True, RED, thick, cv2.LINE_AA)
            text(f"id {marker_id} missing", expected[0], RED)
    zone = warp.mm_to_photo(warp.template.measuring_zone_mm)
    cv2.polylines(out, [_px(zone)], True, GREY, max(1, thick // 2), cv2.LINE_AA)

    if segmentation is None:
        return out
    contour = warp.mm_to_photo(segmentation.contour_mm)
    cv2.polylines(out, [_px(contour)], True, YELLOW, thick, cv2.LINE_AA)

    if len(segmentation.contour_mm) < 3:
        return out
    frame, _heel, placed = locate_insole(segmentation.contour_mm, warp.template, side)
    lines = measurement_lines(frame)

    def segment(ends: FloatArray, colour: tuple[int, int, int]) -> None:
        (x0, y0), (x1, y1) = (map(int, p) for p in np.round(ends))
        cv2.line(out, (x0, y0), (x1, y1), colour, thick, cv2.LINE_AA)

    def to_photo(points_frame: list[tuple[float, float]]) -> FloatArray:
        return warp.mm_to_photo(placed.to_page_mm(np.array(points_frame, np.float64)))

    length = to_photo([(0.0, lines.y0), (0.0, lines.y0 + lines.length)])
    segment(length, MAGENTA)
    text(f"length {lines.length:.1f}", length[1], MAGENTA)
    for name, w in lines.widths.items():
        if not (np.isfinite(w.x_min) and np.isfinite(w.x_max)):
            continue
        ends = to_photo([(w.x_min, w.y), (w.x_max, w.y)])
        colour = WIDTH_COLOURS[name]
        segment(ends, colour)
        text(f"{LABELS[name]} {w.width:.1f}", ends[1], colour)
    return out
