"""Rule-based foot-shape classifier, v1: measurements -> labels.

Every label comes from a ratio, so it doesn't depend on the shoe size. All thresholds
and `CLASSIFIER_VERSION` live in `config.py`; bump the version whenever they change.

- `width_class` (narrow / regular / wide): ball width / length.
- `arch_class` (low / medium / high): arch (midfoot) width / ball width. A high arch
  leaves a narrow midfoot on the insole.
- `toe_box_shape` (pointed / round / square): toe width at 90 % of the length / ball
  width, i.e. how much width the toe box keeps near its end.
- `toe_shape` (egyptian / roman / greek): the toe-end slant of the stored outline, i.e.
  whether the toe end reaches furthest at the big toe, level across the first toes, or
  near the 2nd toe.

These labels describe the **shoe's toe box** (and which foot type it suits), not the
user's foot.

`toe_box_shape` and `toe_shape` describe the same toe end, so some pairs contradict each
other: a square box is level across the toes, so it can't be greek, and a pointed one
can't be level (roman). When the rules produce such a pair, `toe_box_shape` wins: it
rests on three widths, while the slant rests on two points of the toe end, which moves
most with the frame (ADR 0009). `toe_shape` is then set to the nearest consistent label.

Pure functions, no I/O.
"""

from dataclasses import dataclass
from typing import Literal

import numpy as np

from app.pipeline import config
from app.pipeline.measure import InsoleMeasurements, x_extent_along
from app.pipeline.template import FloatArray

WidthClass = Literal["narrow", "regular", "wide"]
ArchClass = Literal["low", "medium", "high"]
ToeBoxShape = Literal["pointed", "round", "square"]
ToeShape = Literal["egyptian", "roman", "greek"]

# Pairs that describe the same toe end in contradicting ways.
CONTRADICTIONS: frozenset[tuple[ToeBoxShape, ToeShape]] = frozenset(
    {("square", "greek"), ("pointed", "roman")}
)


class ContradictoryClassificationError(ValueError):
    """A toe_box_shape / toe_shape pair that can't describe the same toe end."""


@dataclass(frozen=True)
class Classification:
    classifier_version: str
    width_class: WidthClass
    arch_class: ArchClass
    toe_box_shape: ToeBoxShape
    toe_shape: ToeShape


@dataclass(frozen=True)
class Ratios:
    """The numbers the labels are based on. Worth logging, to calibrate thresholds later."""

    width: float  # ball width / length
    arch: float  # arch width / ball width
    toe_box: float  # toe width at 90 % / ball width
    toe_slant: float  # see toe_slant()


def check_consistent(toe_box_shape: ToeBoxShape, toe_shape: ToeShape) -> None:
    if (toe_box_shape, toe_shape) in CONTRADICTIONS:
        raise ContradictoryClassificationError(
            f"toe_box_shape {toe_box_shape!r} contradicts toe_shape {toe_shape!r}"
        )


def toe_slant(outline: FloatArray) -> float:
    """How much further forward the toe end reaches at the big toe than at the 2nd/3rd
    toe, as a fraction of the toe-box width. Positive = longest at the big toe.

    `outline` is the stored outline: option-A frame, canonical right foot (medial at
    -x). The toe box is measured at 85 % of the length. The front edge is sampled at
    `config.TOE_SLANT_AT` of its width from the medial edge.
    """
    length = float(outline[:, 1].max())
    (x_medial,), (x_lateral,) = x_extent_along(outline, np.array([0.85 * length]))
    width = x_lateral - x_medial
    xs = x_medial + width * np.array(config.TOE_SLANT_AT)
    # Front edge = the largest y where a vertical line x = c crosses the outline. Swapping
    # the columns turns "x extent along y" into "y extent along x".
    _, front = x_extent_along(outline[:, ::-1], xs)
    big_toe, second_toe = front
    return float((big_toe - second_toe) / width)


def ratios(m: InsoleMeasurements) -> Ratios:
    return Ratios(
        width=m.ball_width_mm / m.length_mm,
        arch=m.arch_width_mm / m.ball_width_mm,
        toe_box=m.toe_width_90_mm / m.ball_width_mm,
        toe_slant=toe_slant(m.outline_mm),
    )


def width_class(ratio: float) -> WidthClass:
    if ratio < config.WIDTH_NARROW_BELOW:
        return "narrow"
    if ratio > config.WIDTH_WIDE_ABOVE:
        return "wide"
    return "regular"


def arch_class(ratio: float) -> ArchClass:
    if ratio < config.ARCH_HIGH_BELOW:
        return "high"
    if ratio > config.ARCH_LOW_ABOVE:
        return "low"
    return "medium"


def toe_box_shape(ratio: float) -> ToeBoxShape:
    if ratio < config.TOE_BOX_POINTED_BELOW:
        return "pointed"
    if ratio > config.TOE_BOX_SQUARE_ABOVE:
        return "square"
    return "round"


def toe_shape(slant: float, box: ToeBoxShape) -> ToeShape:
    """The slant's label, made consistent with the toe box (see the module docstring)."""
    if slant > config.TOE_SLANT_EGYPTIAN_ABOVE:
        shape: ToeShape = "egyptian"
    elif slant < config.TOE_SLANT_GREEK_BELOW:
        shape = "greek"
    else:
        shape = "roman"
    if (box, shape) == ("square", "greek"):
        return "roman"
    if (box, shape) == ("pointed", "roman"):
        return "egyptian" if slant > 0 else "greek"
    return shape


def classify(m: InsoleMeasurements) -> Classification:
    r = ratios(m)
    box = toe_box_shape(r.toe_box)
    result = Classification(
        classifier_version=config.CLASSIFIER_VERSION,
        width_class=width_class(r.width),
        arch_class=arch_class(r.arch),
        toe_box_shape=box,
        toe_shape=toe_shape(r.toe_slant, box),
    )
    check_consistent(result.toe_box_shape, result.toe_shape)
    return result
