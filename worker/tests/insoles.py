"""Parametric insole outlines whose measurements are known by construction.

## The insole frame and the measurement definitions

These definitions are what `expected.json` means. The pipeline (#23) must report the
same quantities.

- **Frame:** x runs along the insole's long axis, from the heel point (x = 0) to the toe
  tip (x = length). y runs across. Both the heel point and the toe tip lie on y = 0.
- **Width at x:** the extent of the outline across the axis (perpendicular to it) at x.
- `length_mm`: the distance from the heel point to the toe tip, which is also the outline's
  extent along the axis.
- `heel_width_mm`: the largest width in the rear 25 % of the length.
- `arch_width_mm` (midfoot): the smallest width between 30 % and 60 % of the length.
- `ball_width_mm`: the largest width in the front half.
- `toe_width_mm`: the width at 85 %, 90 % and 95 % of the length. These describe the
  toe-box shape: a square toe box stays wide almost to the tip, a pointed one narrows early.
- `toe_box_shape`: `pointed`, `round` or `square`, the label the generator drew. #24 will
  derive it from the toe widths; its thresholds belong in the pipeline config.

## How the outline is built

Each side of the outline (medial = big-toe side, lateral = little-toe side) is a smooth
curve through four control points: heel (16 % of the length), arch (42 %), ball (72 %)
and toe tip.

- **Heel:** an elliptical cap, rounded like a real heel.
- **Heel to arch to ball:** smoothstep transitions (cubic, zero slope at both ends).
  The width changes monotonically between control points, so the max and min widths that
  the definitions ask for fall exactly on the parameters. The lateral side runs straight
  to the arch, and only the medial side cuts in, like a real arch.
- **Toe:** a superellipse cap, (1 - t^n)^(1/n). The exponent n sets the toe-box shape.

All shapes are waisted (arch < heel < ball), which is what makes "smallest width in the
midfoot" well defined. A shape that breaks that is refused.
"""

from dataclasses import dataclass
from typing import Literal

import numpy as np

from app.pipeline.template import FloatArray

ToeBox = Literal["pointed", "round", "square"]
Side = Literal["left", "right"]

TOE_BOX_EXPONENT: dict[ToeBox, float] = {"pointed": 1.4, "round": 2.0, "square": 3.5}

# Control-point positions as fractions of the length.
HEEL_AT, ARCH_AT, BALL_AT = 0.16, 0.42, 0.72
# Share of the ball width on the medial side (the big-toe joint bulges a little).
BALL_MEDIAL_SHARE = 0.52

# Measurement regions (fractions of length), see the module docstring.
HEEL_REGION = (0.0, 0.25)
ARCH_REGION = (0.30, 0.60)
BALL_REGION = (0.50, 1.0)
TOE_WIDTH_AT = (0.85, 0.90, 0.95)

_CAP_SAMPLES = 400  # per heel/toe cap, per side
_MID_STEP_MM = 0.25


def _smoothstep(a: float, b: float, s: FloatArray) -> FloatArray:
    return a + (b - a) * (3 * s**2 - 2 * s**3)


@dataclass(frozen=True)
class InsoleShape:
    length_mm: float
    heel_width_mm: float
    arch_width_mm: float
    ball_width_mm: float
    toe_box: ToeBox
    side: Side = "left"

    def __post_init__(self) -> None:
        if not self.arch_width_mm < self.heel_width_mm < self.ball_width_mm:
            raise ValueError("insole shapes must be waisted: arch < heel < ball width")

    # Half-widths (always >= 0) of each side at the control points.
    @property
    def _heel_half(self) -> tuple[float, float]:
        return self.heel_width_mm / 2, self.heel_width_mm / 2

    @property
    def _arch_half(self) -> tuple[float, float]:
        lateral = self.heel_width_mm / 2  # lateral edge runs straight
        return self.arch_width_mm - lateral, lateral

    @property
    def _ball_half(self) -> tuple[float, float]:
        medial = self.ball_width_mm * BALL_MEDIAL_SHARE
        return medial, self.ball_width_mm - medial

    def _side_points(self, k: int) -> FloatArray:
        """(x, half-width) along side k (0 = medial, 1 = lateral), heel point to toe tip."""
        length = self.length_mm
        xh, xa, xb = HEEL_AT * length, ARCH_AT * length, BALL_AT * length
        yh, ya, yb = self._heel_half[k], self._arch_half[k], self._ball_half[k]

        theta = np.linspace(0, np.pi / 2, _CAP_SAMPLES)
        heel = np.column_stack([xh * (1 - np.cos(theta)), yh * np.sin(theta)])

        x1 = np.arange(xh, xa, _MID_STEP_MM)
        x2 = np.arange(xa, xb, _MID_STEP_MM)
        mid = np.concatenate(
            [
                np.column_stack([x1, _smoothstep(yh, ya, (x1 - xh) / (xa - xh))]),
                np.column_stack([x2, _smoothstep(ya, yb, (x2 - xa) / (xb - xa))]),
            ]
        )

        # Superellipse |u|^n + |v|^n = 1, parametrised by angle for even point spacing.
        e = 2 / TOE_BOX_EXPONENT[self.toe_box]
        theta = np.linspace(0, np.pi / 2, _CAP_SAMPLES)
        toe = np.column_stack([xb + (length - xb) * np.sin(theta) ** e, yb * np.cos(theta) ** e])
        return np.concatenate([heel, mid[1:], toe])

    def outline(self) -> FloatArray:
        """Closed outline (n, 2) in the insole frame, mm. Left insoles have the medial side
        at +y, right insoles are their mirror image."""
        medial = self._side_points(0)
        lateral = self._side_points(1)
        sign = 1.0 if self.side == "left" else -1.0
        pts = np.concatenate([medial * [1, sign], (lateral * [1, -sign])[::-1][1:-1]])
        return np.asarray(pts, np.float64)

    def width_at(self, fraction: float) -> float:
        """Exact width at `fraction` of the length (analytic, for the forefoot only)."""
        if fraction < BALL_AT:
            raise ValueError("width_at is only defined in the forefoot")
        t = (fraction - BALL_AT) / (1 - BALL_AT)
        n = TOE_BOX_EXPONENT[self.toe_box]
        return float(self.ball_width_mm * (1 - t**n) ** (1 / n))

    def toe_widths(self) -> dict[float, float]:
        return {f: self.width_at(f) for f in TOE_WIDTH_AT}


def widths_along(outline: FloatArray, xs: FloatArray) -> FloatArray:
    """Width of a closed outline (in its own frame) across the x axis at each of `xs`.

    Intersects each vertical line x = c with every polygon edge. Test-side ground truth;
    the pipeline does its own measuring (#23).
    """
    a = outline
    b = np.roll(outline, -1, axis=0)
    out = np.empty(len(xs))
    for i, c in enumerate(xs):
        lo, hi = np.minimum(a[:, 0], b[:, 0]), np.maximum(a[:, 0], b[:, 0])
        hit = (lo <= c) & (c <= hi) & (hi > lo)
        t = (c - a[hit, 0]) / (b[hit, 0] - a[hit, 0])
        ys = a[hit, 1] + t * (b[hit, 1] - a[hit, 1])
        out[i] = ys.max() - ys.min() if len(ys) else 0.0
    return out


def measure_in_frame(outline: FloatArray) -> dict[str, float]:
    """Apply the module's measurement definitions to an outline given in the insole frame."""
    length = float(outline[:, 0].max() - outline[:, 0].min())
    x0 = float(outline[:, 0].min())

    def region(lo: float, hi: float) -> FloatArray:
        xs = x0 + length * np.linspace(lo, hi, 601)
        return widths_along(outline, xs[1:-1] if lo == 0.0 or hi == 1.0 else xs)

    result = {
        "length_mm": length,
        "heel_width_mm": float(region(*HEEL_REGION).max()),
        "arch_width_mm": float(region(*ARCH_REGION).min()),
        "ball_width_mm": float(region(*BALL_REGION).max()),
    }
    for f in TOE_WIDTH_AT:
        result[f"toe_width_{round(f * 100)}_mm"] = float(
            widths_along(outline, np.array([x0 + f * length]))[0]
        )
    return result
