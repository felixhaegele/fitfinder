"""Rule-based foot-shape classifier v1 (#24)."""

import re
from dataclasses import asdict
from itertools import product
from typing import get_args

import numpy as np
import pytest

from app.pipeline import classify as cl
from app.pipeline import config
from app.pipeline.classify import (
    CONTRADICTIONS,
    ArchClass,
    ContradictoryClassificationError,
    ToeBoxShape,
    ToeShape,
    WidthClass,
    check_consistent,
    classify,
    toe_slant,
)
from app.pipeline.measure import measure_insole
from app.pipeline.segment import segment_insole
from app.pipeline.template import FloatArray, Template, load_template
from app.pipeline.warp import warp_to_page
from tests.insoles import InsoleShape
from tests.regression import (
    CLASS_KEYS,
    Expected,
    Fixture,
    Look,
    Placement,
    RenderedFixture,
    assert_classes_match,
    insole_frame,
    measurable_fixtures,
)
from tests.synthetic import Shot

# The thresholds each CLASSIFIER_VERSION was released with. Changing a number in
# config.py makes test_thresholds_are_pinned_to_the_version fail until you bump
# CLASSIFIER_VERSION and add its numbers here, so stored classifications always say which
# rules produced them.
THRESHOLDS_BY_VERSION = {
    "1.0.0": {
        "WIDTH_NARROW_BELOW": 0.355,
        "WIDTH_WIDE_ABOVE": 0.390,
        "ARCH_HIGH_BELOW": 0.52,
        "ARCH_LOW_ABOVE": 0.60,
        "TOE_BOX_POINTED_BELOW": 0.67,
        "TOE_BOX_SQUARE_ABOVE": 0.85,
        "TOE_SLANT_AT": (0.15, 0.45),
        "TOE_SLANT_EGYPTIAN_ABOVE": 0.03,
        "TOE_SLANT_GREEK_BELOW": -0.10,
    },
}


@pytest.fixture(scope="module")
def template() -> Template:
    return load_template()


def stored_outline(shape: InsoleShape, template: Template) -> FloatArray:
    fx = Fixture("t", "", Expected(), shape, Look(), Placement(), Shot(page_corners_px=()))
    return measure_insole(insole_frame(fx, template).to_page(shape.outline()), template).outline_mm


# --- Version and thresholds ----------------------------------------------------------


def test_thresholds_are_pinned_to_the_version() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", config.CLASSIFIER_VERSION)
    pinned = THRESHOLDS_BY_VERSION.get(config.CLASSIFIER_VERSION)
    assert pinned is not None, "new CLASSIFIER_VERSION: record its thresholds above"
    current = {name: getattr(config, name) for name in pinned}
    assert current == pinned, "thresholds changed: bump CLASSIFIER_VERSION"


def test_every_result_carries_the_version(template: Template) -> None:
    shape = InsoleShape(260, 64, 55, 98, "round", "left")
    fx = Fixture("t", "", Expected(), shape, Look(), Placement(), Shot(page_corners_px=()))
    m = measure_insole(insole_frame(fx, template).to_page(shape.outline()), template)
    assert classify(m).classifier_version == config.CLASSIFIER_VERSION


def test_labels_are_those_the_database_accepts() -> None:
    assert set(get_args(WidthClass)) == {"narrow", "regular", "wide"}
    assert set(get_args(ArchClass)) == {"low", "medium", "high"}
    assert set(get_args(ToeBoxShape)) == {"round", "square", "pointed"}
    assert set(get_args(ToeShape)) == {"egyptian", "roman", "greek"}


# --- Single rules --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ratio", "label"),
    [(0.33, "narrow"), (0.356, "regular"), (0.37, "regular"), (0.389, "regular"), (0.41, "wide")],
)
def test_width_class(ratio: float, label: str) -> None:
    assert cl.width_class(ratio) == label


@pytest.mark.parametrize(
    ("ratio", "label"), [(0.48, "high"), (0.53, "medium"), (0.57, "medium"), (0.62, "low")]
)
def test_arch_class(ratio: float, label: str) -> None:
    assert cl.arch_class(ratio) == label


@pytest.mark.parametrize(("ratio", "label"), [(0.58, "pointed"), (0.77, "round"), (0.93, "square")])
def test_toe_box_shape(ratio: float, label: str) -> None:
    assert cl.toe_box_shape(ratio) == label


@pytest.mark.parametrize(
    ("slant", "box", "label"),
    [
        (0.10, "round", "egyptian"),
        (0.0, "round", "roman"),
        (-0.20, "round", "greek"),
        # Contradictions resolve towards the toe box
        (-0.20, "square", "roman"),
        (0.0, "pointed", "greek"),
        (0.02, "pointed", "egyptian"),
        (-0.05, "pointed", "greek"),
    ],
)
def test_toe_shape(slant: float, box: ToeBoxShape, label: str) -> None:
    assert cl.toe_shape(slant, box) == label


# --- Contradictions ------------------------------------------------------------------


@pytest.mark.parametrize(("box", "shape"), sorted(CONTRADICTIONS))
def test_contradictory_combinations_are_rejected(box: ToeBoxShape, shape: ToeShape) -> None:
    with pytest.raises(ContradictoryClassificationError, match=f"{box}.*{shape}"):
        check_consistent(box, shape)


def test_square_greek_is_a_contradiction() -> None:
    """The owner's example on #24."""
    assert ("square", "greek") in CONTRADICTIONS


@pytest.mark.parametrize(
    ("box", "shape"),
    [c for c in product(get_args(ToeBoxShape), get_args(ToeShape)) if c not in CONTRADICTIONS],
)
def test_consistent_combinations_pass(box: ToeBoxShape, shape: ToeShape) -> None:
    check_consistent(box, shape)


@pytest.mark.parametrize("slant", np.linspace(-0.4, 0.4, 41))
@pytest.mark.parametrize("box", get_args(ToeBoxShape))
def test_rules_never_produce_a_contradiction(slant: float, box: ToeBoxShape) -> None:
    check_consistent(box, cl.toe_shape(float(slant), box))


# --- Toe slant on outlines -----------------------------------------------------------


@pytest.mark.parametrize(
    ("toe_box", "share", "label"),
    [
        ("pointed", 0.52, "greek"),
        ("round", 0.52, "greek"),
        ("square", 0.52, "roman"),
        ("round", 0.12, "egyptian"),
        ("pointed", 0.15, "egyptian"),
    ],
)
def test_toe_slant_reads_where_the_toe_end_is_longest(
    toe_box: str, share: float, label: str, template: Template
) -> None:
    for side in ("left", "right"):
        shape = InsoleShape(260, 60, 50, 92, toe_box, side, share)  # type: ignore[arg-type]
        slant = toe_slant(stored_outline(shape, template))
        box = cl.toe_box_shape(shape.width_at(0.90) / shape.ball_width_mm)
        assert cl.toe_shape(slant, box) == label, f"{side}: slant {slant:+.3f}"


def test_toe_slant_sign() -> None:
    """A hand-made toe end that is longest at the medial (-x) edge slants positive."""
    outline = np.array([[0, 0], [-40, 50], [-40, 200], [-30, 250], [40, 200], [40, 50]], float)
    outline -= [outline[3, 0], 0]  # keep the toe tip on x = 0
    assert toe_slant(outline) > 0
    assert toe_slant(outline * [-1, 1]) < 0


# --- Fixtures ------------------------------------------------------------------------


def test_fixtures_cover_every_label() -> None:
    seen = {k: {f.expected.classes[k] for f in measurable_fixtures()} for k in CLASS_KEYS}
    assert seen["width_class"] == set(get_args(WidthClass))
    assert seen["arch_class"] == set(get_args(ArchClass))
    assert seen["toe_box_shape"] == set(get_args(ToeBoxShape))
    assert seen["toe_shape"] == set(get_args(ToeShape))


@pytest.mark.parametrize("fixture", measurable_fixtures(), ids=lambda f: f.name)
def test_drawn_shape_gets_the_expected_labels(fixture: Fixture, template: Template) -> None:
    """On the exact outline, without photo or segmentation errors."""
    page = insole_frame(fixture, template).to_page(fixture.shape.outline())
    assert_classes_match(asdict(classify(measure_insole(page, template))), fixture.expected)


def test_fixture_photo_gets_the_expected_labels(measurable: RenderedFixture) -> None:
    """End to end: photo -> markers -> warp -> segment -> measure -> classify."""
    warp = warp_to_page(measurable.photo.image)
    m = measure_insole(segment_insole(warp).contour_mm, warp.template)
    assert_classes_match(asdict(classify(m)), measurable.fixture.expected)
