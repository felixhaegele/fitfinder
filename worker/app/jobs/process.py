"""The seam between the queue worker and the measurement pipeline.

`process(image)` is the only function the worker calls on the pipeline. It returns a
`Result` (rows to write) or a `Rejection` (why the photo can't be measured). Everything
before it (files, validation) and after it (database) is the worker's job.

It runs markers -> warp -> segment, then an `Analyzer`: a function from the warped page +
insole outline to the rows to store. `DEFAULT_ANALYZER` measures the outline (#23,
`measure_insole`) and classifies it (#24, `classify`).

The row types mirror the columns of `measurements` and `classifications`, so the worker
can insert them as they are. They hold plain Python values only (no numpy), because they
cross the sandbox's process boundary and end up in JSON.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np

from app.pipeline import config as pipeline_config
from app.pipeline.classify import Classification, classify
from app.pipeline.measure import OUTLINE_POINTS, InsoleMeasurements, measure_insole
from app.pipeline.rejections import Rejection
from app.pipeline.segment import Segmentation, segment_insole
from app.pipeline.template import FloatArray
from app.pipeline.warp import Image, PageWarp, warp_to_page

# 256 [x, y] points in mm: heel point at (0, 0), toe along +y, right-foot frame
# (decision on #23/#52, option A). Stored as `measurements.outline_mm`.
Outline = tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class MeasurementRow:
    """One row of `measurements`. All lengths in millimetres."""

    pipeline_version: str
    side: str
    length_mm: float
    ball_width_mm: float
    heel_width_mm: float
    arch_width_mm: float
    outline_mm: Outline
    toe_taper: float | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ClassificationRow:
    """One row of `classifications`. Belongs to the measurement it was computed from."""

    classifier_version: str
    width_class: str
    arch_class: str
    toe_box_shape: str
    toe_shape: str


@dataclass(frozen=True)
class Analysis:
    measurement: MeasurementRow | None = None
    classification: ClassificationRow | None = None


class Analyzer(Protocol):
    """Measures and classifies a segmented insole. May raise `Rejection`.

    Must be a module-level function: it's sent to the sandbox's child process by name.
    """

    def __call__(self, warp: PageWarp, segmentation: Segmentation, /) -> Analysis: ...


def no_analysis(warp: PageWarp, segmentation: Segmentation, /) -> Analysis:
    """Segmentation only, no rows. For tests that don't need measurements."""
    return Analysis()


def outline_for_db(outline_mm: FloatArray) -> Outline:
    """The canonical outline as plain floats that satisfy the `outline_mm` check constraint.

    Raises ValueError instead of letting the database reject the row: the outline must have
    256 finite points and start exactly at the heel point (0, 0).
    """
    pts = np.asarray(outline_mm, np.float64)
    if pts.shape != (OUTLINE_POINTS, 2):
        raise ValueError(f"outline must be ({OUTLINE_POINTS}, 2), got {pts.shape}")
    if not np.isfinite(pts).all():
        raise ValueError("outline has non-finite coordinates")
    # Mirroring a left insole turns 0.0 into -0.0; adding 0.0 makes it +0.0 again.
    pts = np.round(pts, 2) + 0.0
    if pts[0, 0] != 0.0 or pts[0, 1] != 0.0:
        raise ValueError(f"outline must start at the heel point (0, 0), got {pts[0].tolist()}")
    return tuple((float(x), float(y)) for x, y in pts)


def measurement_row(m: InsoleMeasurements) -> MeasurementRow:
    """Map the pipeline's measurements onto a `measurements` row.

    The toe widths have no columns of their own: they go in `extra`, and `toe_taper`
    (numeric(6, 4)) is the toe width at 90 % of the length over the ball width.
    """
    if not m.ball_width_mm > 0:
        raise ValueError(f"ball width must be positive, got {m.ball_width_mm}")
    return MeasurementRow(
        pipeline_version=pipeline_config.PIPELINE_VERSION,
        side=m.side,
        length_mm=float(m.length_mm),
        ball_width_mm=float(m.ball_width_mm),
        heel_width_mm=float(m.heel_width_mm),
        arch_width_mm=float(m.arch_width_mm),
        outline_mm=outline_for_db(m.outline_mm),
        toe_taper=round(float(m.toe_width_90_mm) / float(m.ball_width_mm), 4),
        extra={
            "toe_width_85_mm": float(m.toe_width_85_mm),
            "toe_width_90_mm": float(m.toe_width_90_mm),
            "toe_width_95_mm": float(m.toe_width_95_mm),
        },
    )


def classification_row(c: Classification) -> ClassificationRow:
    return ClassificationRow(
        classifier_version=c.classifier_version,
        width_class=c.width_class,
        arch_class=c.arch_class,
        toe_box_shape=c.toe_box_shape,
        toe_shape=c.toe_shape,
    )


def measure_and_classify(warp: PageWarp, segmentation: Segmentation, /) -> Analysis:
    """Measure the segmented outline (side inferred from its shape) and classify it."""
    measurements = measure_insole(segmentation.contour_mm, warp.template)
    for name, value in measurements.scalars().items():
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"{name} is not finite: {value}")
    return Analysis(
        measurement=measurement_row(measurements),
        classification=classification_row(classify(measurements)),
    )


DEFAULT_ANALYZER: Analyzer = measure_and_classify


@dataclass(frozen=True)
class Result:
    measurement: MeasurementRow | None
    classification: ClassificationRow | None
    # For logs: how the pipeline saw the photo.
    markers_found: tuple[int, ...]
    insole_area_mm2: float


def process(image: Image, analyze: Analyzer = DEFAULT_ANALYZER) -> Result | Rejection:
    """Measure an insole photo (BGR, upright). Rejections are returned, not raised."""
    try:
        warp = warp_to_page(image)
        segmentation = segment_insole(warp)
        analysis = analyze(warp, segmentation)
    except Rejection as rejection:
        return rejection
    if analysis.classification is not None and analysis.measurement is None:
        raise ValueError("a classification needs the measurement it was computed from")
    return Result(
        measurement=analysis.measurement,
        classification=analysis.classification,
        markers_found=tuple(warp.markers_found),
        insole_area_mm2=segmentation.area_mm2,
    )
