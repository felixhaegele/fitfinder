"""The seam between the queue worker and the measurement pipeline.

`process(image)` is the only function the worker calls on the pipeline. It returns a
`Result` (rows to write) or a `Rejection` (why the photo can't be measured). Everything
before it (files, validation) and after it (database) is the worker's job.

Today it runs markers -> warp -> segment. Measuring (#23) and classifying (#24) plug in
as an `Analyzer`: a function from the warped page + insole outline to the rows to store.
Until they're wired in, `DEFAULT_ANALYZER` returns no rows, and a photo that passes
segmentation becomes `done` without measurements.

The row types mirror the columns of `measurements` and `classifications` on main, so the
worker can insert them as they are. Columns added later (#52: outline, side, toe_shape)
get fields here when their migration lands.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.pipeline.rejections import Rejection
from app.pipeline.segment import Segmentation, segment_insole
from app.pipeline.warp import Image, PageWarp, warp_to_page


@dataclass(frozen=True)
class MeasurementRow:
    """One row of `measurements`. All lengths in millimetres."""

    pipeline_version: str
    length_mm: float
    ball_width_mm: float
    heel_width_mm: float
    arch_width_mm: float
    toe_taper: float | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ClassificationRow:
    """One row of `classifications`. Belongs to the measurement it was computed from."""

    classifier_version: str
    width_class: str
    arch_class: str
    toe_box_shape: str


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
    """Placeholder until #23 (measurements) and #24 (classifier) are merged."""
    return Analysis()


# The one line to change when wiring in #23/#24.
DEFAULT_ANALYZER: Analyzer = no_analysis


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
