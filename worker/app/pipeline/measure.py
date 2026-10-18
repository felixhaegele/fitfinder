"""Insole outline on the page -> measurements in mm and the stored 256-point outline.

Input is `Segmentation.contour_mm` from `segment.py`: the insole's outline in page
millimetres (y down, as printed), lying roughly along the template's diagonal
`insole_axis` (ADR 0004). Output is in the **option-A frame** (owner decision on #23/#52,
2026-10-18), the one frame used by the tests, the pipeline and the database:

- millimetres, y up, seen from above as if standing on the insole;
- the heel point is the origin (0, 0), the toe tip is (0, length): the toe points along +y;
- canonical foot is right: left insoles are mirrored (x -> -x), so the medial (big-toe)
  side is always at -x, and the original side is reported in `side`;
- the outline is resampled to 256 points, evenly spaced along the contour, ordered
  heel point -> medial -> toe tip -> lateral (clockwise in y-up coordinates).

Steps:

1. **Principal axis.** The second moments of the outline's *area* give the direction the
   insole is longest in. That's only a first guess: the measurement definitions
   (`tests/insoles.py`) use the line from the heel point to the toe tip.
2. **Which end is the heel.** The forefoot (ball + toes) holds clearly more area than the
   heel + arch, so the half with more area is the front. This works however the insole
   lies, even reversed on the template. Only when the two halves are nearly equal does
   the template's `insole_axis` (heel bottom-left, toe top-right) decide.
3. **Heel point and toe tip.** Take the outline's two extreme points along the axis, make
   the line through them the new axis, and repeat until they stop changing. The result
   satisfies the definition exactly: the heel point and toe tip are the outline's
   extremes along the line that joins them, so length = their distance = the extent.
4. **Side.** Only the medial edge cuts in at the arch, so in the midfoot (30-60 % of the
   length) the medial half is the narrower one. Left insoles are then mirrored onto right.
5. **Measure** along y with the definitions in `tests/insoles.py`, on the full-resolution
   outline, and **resample** it to 256 points for storage.

Everything here is a pure function on arrays: no images, files or database.
"""

from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np

from app.pipeline import config
from app.pipeline.template import FloatArray, Template

Side = Literal["left", "right"]

# --- Measurement definitions (fractions of the length). They define what the numbers
# mean, so they must equal those in tests/insoles.py (a test checks it).
HEEL_REGION = (0.0, 0.25)
ARCH_REGION = (0.30, 0.60)
BALL_REGION = (0.50, 1.0)
TOE_WIDTH_AT = (0.85, 0.90, 0.95)

# Number of points in the stored outline. The database's check constraint on
# measurements.outline_mm requires exactly this many.
OUTLINE_POINTS = 256

# Widths in a region are sampled on this many evenly spaced lines across the axis.
_REGION_SAMPLES = 601


@dataclass(frozen=True)
class InsoleMeasurements:
    side: Side
    length_mm: float
    heel_width_mm: float
    arch_width_mm: float
    ball_width_mm: float
    toe_width_85_mm: float
    toe_width_90_mm: float
    toe_width_95_mm: float
    # (OUTLINE_POINTS, 2), canonical right-foot frame, rounded to 0.01 mm.
    outline_mm: FloatArray

    def scalars(self) -> dict[str, float | str]:
        """Everything except the outline, e.g. for `assert_measurements_match`."""
        values = asdict(self)
        del values["outline_mm"]
        return values


# --- Geometry helpers ----------------------------------------------------------------


def _unit(v: FloatArray) -> FloatArray:
    return np.asarray(v / np.hypot(v[0], v[1]), np.float64)


def page_to_y_up(points_mm: FloatArray) -> FloatArray:
    """Page mm (y down) -> y-up mm. The picture stays the same, seen from above; only the
    direction of the y axis changes. Rotating y-down points without this would give the
    mirror image, and every right insole would be read as a left one."""
    pts = np.asarray(points_mm, np.float64)
    return np.column_stack([pts[:, 0], -pts[:, 1]])


def signed_area(pts: FloatArray) -> float:
    """Shoelace formula. Positive = anticlockwise in y-up coordinates."""
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def principal_axis(pts: FloatArray) -> tuple[FloatArray, FloatArray]:
    """Centroid and unit direction of the longest principal axis of the polygon's area.

    Uses the polygon's area moments (Green's theorem), not the vertices: vertices are
    spaced unevenly along a pixel contour and would bias the result.
    """
    p = pts - pts.mean(axis=0)  # centred for numerical precision
    x0, y0 = p[:, 0], p[:, 1]
    x1, y1 = np.roll(x0, -1), np.roll(y0, -1)
    cross = x0 * y1 - x1 * y0
    area = cross.sum() / 2
    cx = ((x0 + x1) * cross).sum() / (6 * area)
    cy = ((y0 + y1) * cross).sum() / (6 * area)
    sxx = ((x0**2 + x0 * x1 + x1**2) * cross).sum() / (12 * area) - cx**2
    syy = ((y0**2 + y0 * y1 + y1**2) * cross).sum() / (12 * area) - cy**2
    sxy = ((x0 * y1 + 2 * x0 * y0 + 2 * x1 * y1 + x1 * y0) * cross).sum() / (24 * area) - cx * cy
    _, vectors = np.linalg.eigh(np.array([[sxx, sxy], [sxy, syy]]))
    centroid = pts.mean(axis=0) + np.array([cx, cy])
    return np.asarray(centroid, np.float64), _unit(vectors[:, 1])  # largest eigenvalue


def to_frame(pts: FloatArray, origin: FloatArray, axis: FloatArray) -> FloatArray:
    """y-up points -> a frame with `origin` at (0, 0) and `axis` along +y. +x is the
    right-hand side when walking along the axis. A pure rotation (no mirroring)."""
    right = np.array([axis[1], -axis[0]])
    d = pts - origin
    return np.column_stack([d @ right, d @ axis])


def x_extent_along(pts: FloatArray, ys: FloatArray) -> tuple[FloatArray, FloatArray]:
    """Smallest and largest x where the closed outline crosses each line y = c.
    NaN where a line misses the outline."""
    a, b = pts, np.roll(pts, -1, axis=0)
    lo, hi = np.minimum(a[:, 1], b[:, 1]), np.maximum(a[:, 1], b[:, 1])
    c = ys[:, None]
    hit = (lo <= c) & (c <= hi) & (hi > lo)
    dy = np.where(hi > lo, b[:, 1] - a[:, 1], 1.0)
    xs = a[:, 0] + (c - a[:, 1]) / dy * (b[:, 0] - a[:, 0])
    with np.errstate(invalid="ignore"):
        xmin = np.where(hit, xs, np.inf).min(axis=1)
        xmax = np.where(hit, xs, -np.inf).max(axis=1)
    missed = ~hit.any(axis=1)
    xmin[missed] = np.nan
    xmax[missed] = np.nan
    return xmin, xmax


def widths_along(pts: FloatArray, ys: FloatArray) -> FloatArray:
    """Width (extent in x) of the closed outline at each y. 0 where a line misses it."""
    xmin, xmax = x_extent_along(pts, ys)
    return np.nan_to_num(xmax - xmin, nan=0.0)


# --- Steps ---------------------------------------------------------------------------


def toe_direction(pts: FloatArray, template_axis: FloatArray) -> FloatArray:
    """Unit vector along the principal axis that points from heel to toe (step 2).

    `pts` and `template_axis` are y-up. The forefoot half has more area. When the halves
    differ by less than `config.FOREFOOT_AREA_RATIO`, fall back to the template axis.
    """
    centroid, axis = principal_axis(pts)
    frame = to_frame(pts, centroid, axis)
    lo, hi = frame[:, 1].min(), frame[:, 1].max()
    mid = (lo + hi) / 2
    ys = np.linspace(lo, hi, _REGION_SAMPLES)[1:-1]
    widths = widths_along(frame, ys)
    front = float(widths[ys > mid].sum())
    back = float(widths[ys <= mid].sum())
    if front >= config.FOREFOOT_AREA_RATIO * back:
        return axis
    if back >= config.FOREFOOT_AREA_RATIO * front:
        return -axis
    return axis if float(axis @ template_axis) >= 0 else -axis


def heel_and_toe(pts: FloatArray, axis: FloatArray) -> tuple[int, int, FloatArray]:
    """Indices of the heel point and the toe tip, and the unit axis heel -> toe (step 3).

    Each round can only lengthen the heel-toe distance, so it settles quickly: usually in
    2-3 rounds, a few more for a square toe whose tip slides to a corner.
    """
    heel = toe = -1
    for _ in range(config.AXIS_MAX_ITERATIONS):
        s = pts @ axis
        new_heel, new_toe = int(np.argmin(s)), int(np.argmax(s))
        if (new_heel, new_toe) == (heel, toe):
            break
        heel, toe = new_heel, new_toe
        axis = _unit(pts[toe] - pts[heel])
    return heel, toe, axis


def detect_side(frame: FloatArray) -> Side:
    """Left or right, from an outline in the frame (toe along +y, before mirroring).

    The medial edge cuts in at the arch, so the medial half is the narrower one in the
    midfoot. A left insole seen from above has its medial side on the right (+x).
    """
    length = float(frame[:, 1].max())
    ys = length * np.linspace(*ARCH_REGION, 61)
    xmin, xmax = x_extent_along(frame, ys)
    right_half, left_half = float(np.nanmean(xmax)), float(np.nanmean(-xmin))
    return "left" if right_half < left_half else "right"


def resample_closed(pts: FloatArray, n: int) -> FloatArray:
    """n points evenly spaced along the closed outline, starting at pts[0], in order."""
    closed = np.vstack([pts, pts[:1]])
    seg = np.hypot(*np.diff(closed, axis=0).T)
    keep = np.concatenate([[True], seg > 0])  # drop repeated points
    closed = closed[keep]
    cum = np.concatenate([[0.0], np.cumsum(seg[seg > 0])])
    at = np.arange(n) * cum[-1] / n
    return np.column_stack([np.interp(at, cum, closed[:, 0]), np.interp(at, cum, closed[:, 1])])


def smooth_closed(pts: FloatArray, step_mm: float, sigma_mm: float) -> FloatArray:
    """The closed outline resampled every `step_mm` and smoothed with a Gaussian of
    `sigma_mm` along its length.

    A pixel contour is a staircase: its length along the steps is up to ~8 % longer than
    the real edge, depending on the edge's direction, so "evenly spaced along the contour"
    would not be even at all. Smoothing over a few pixels removes the steps. It barely
    moves the real edge: a curve of radius R shrinks by about sigma^2 / 2R, i.e. 0.01 mm
    at R = 8 mm and sigma = 0.4 mm.
    """
    closed = np.vstack([pts, pts[:1]])
    perimeter = float(np.hypot(*np.diff(closed, axis=0).T).sum())
    n = max(8, round(perimeter / step_mm))
    even = resample_closed(pts, n)
    sigma = sigma_mm / (perimeter / n)
    radius = int(np.ceil(4 * sigma))
    if radius == 0:
        return even
    kernel = np.exp(-0.5 * (np.arange(-radius, radius + 1) / sigma) ** 2)
    kernel /= kernel.sum()
    wrapped = np.vstack([even[-radius:], even, even[:radius]])
    return np.column_stack([np.convolve(wrapped[:, k], kernel, mode="valid") for k in (0, 1)])


def canonical_outline(frame: FloatArray, heel: int, n: int = OUTLINE_POINTS) -> FloatArray:
    """The stored outline: start at the heel point, go heel -> medial -> toe -> lateral,
    n evenly spaced points, rounded to 0.01 mm. `frame` must already be mirrored onto a
    right foot (medial at -x), so that order is clockwise in y-up coordinates."""
    ordered = np.roll(frame, -heel, axis=0)
    if signed_area(ordered) > 0:  # anticlockwise: reverse, keeping the heel point first
        ordered = np.roll(ordered[::-1], 1, axis=0)
    out = np.round(resample_closed(ordered, n), 2) + 0.0  # + 0.0 turns -0.0 into 0.0
    out[0] = (0.0, 0.0)  # the heel point, exactly; the database checks it
    return np.asarray(out, np.float64)


def measure_frame(frame: FloatArray) -> dict[str, float]:
    """The measurement definitions (`tests/insoles.py`) applied along y."""
    y0 = float(frame[:, 1].min())
    length = float(frame[:, 1].max()) - y0

    def region(lo: float, hi: float) -> FloatArray:
        ys = y0 + length * np.linspace(lo, hi, _REGION_SAMPLES)
        # A line exactly through the heel point or toe tip has zero width; skip it.
        return widths_along(frame, ys[1:-1] if lo == 0.0 or hi == 1.0 else ys)

    toe = widths_along(frame, y0 + length * np.array(TOE_WIDTH_AT))
    return {
        "length_mm": length,
        "heel_width_mm": float(region(*HEEL_REGION).max()),
        "arch_width_mm": float(region(*ARCH_REGION).min()),
        "ball_width_mm": float(region(*BALL_REGION).max()),
        **{
            f"toe_width_{round(f * 100)}_mm": float(w)
            for f, w in zip(TOE_WIDTH_AT, toe, strict=True)
        },
    }


def measure_insole(
    contour_mm: FloatArray, template: Template, side: Side | None = None
) -> InsoleMeasurements:
    """Measure an insole outline given in page mm (e.g. `Segmentation.contour_mm`).

    `side` overrides the shape-based left/right detection, for when the user says which
    insole it is.
    """
    pts = smooth_closed(
        page_to_y_up(contour_mm), config.OUTLINE_STEP_MM, config.OUTLINE_SMOOTHING_MM
    )
    (hx, hy), (tx, ty) = template.heel_mm, template.toe_mm
    template_axis = _unit(np.array([tx - hx, hy - ty]))  # y-up: flip the y difference

    heel, _toe, axis = heel_and_toe(pts, toe_direction(pts, template_axis))
    frame = to_frame(pts, pts[heel], axis)
    side = side or detect_side(frame)
    if side == "left":
        frame = frame * [-1.0, 1.0]

    values = measure_frame(frame)
    return InsoleMeasurements(
        side=side,
        length_mm=values["length_mm"],
        heel_width_mm=values["heel_width_mm"],
        arch_width_mm=values["arch_width_mm"],
        ball_width_mm=values["ball_width_mm"],
        toe_width_85_mm=values["toe_width_85_mm"],
        toe_width_90_mm=values["toe_width_90_mm"],
        toe_width_95_mm=values["toe_width_95_mm"],
        outline_mm=canonical_outline(frame, heel),
    )
