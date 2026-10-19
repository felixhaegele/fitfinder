"""Measuring (#23): page outline -> option-A frame -> measurements and the 256-point outline."""

import cv2
import numpy as np
import pytest

from app.pipeline import measure
from app.pipeline.measure import (
    OUTLINE_POINTS,
    InsoleMeasurements,
    measure_insole,
    principal_axis,
    resample_closed,
    signed_area,
    toe_direction,
)
from app.pipeline.segment import segment_insole
from app.pipeline.template import FloatArray, Template, load_template
from app.pipeline.warp import warp_to_page
from tests import insoles
from tests.insoles import InsoleShape, measure_in_frame
from tests.regression import (
    MEASUREMENT_KEYS,
    Expected,
    Fixture,
    Look,
    Placement,
    RenderedFixture,
    assert_measurements_match,
    insole_frame,
    measurable_fixtures,
)
from tests.synthetic import Shot


@pytest.fixture(scope="module")
def template() -> Template:
    return load_template()


def canonical_truth(shape: InsoleShape) -> FloatArray:
    """The generator's outline mirrored onto a right foot, as the pipeline stores it."""
    pts = shape.outline()
    return pts * [-1.0, 1.0] if shape.side == "left" else pts


def on_page(shape: InsoleShape, template: Template, *, turn_deg: float = 0.0) -> FloatArray:
    """The dense generator outline laid on the page along the template's insole axis,
    turned `turn_deg` about its middle (positive = anticlockwise as seen on the page)."""
    fx = Fixture("t", "", Expected(), shape, Look(), Placement(), Shot(page_corners_px=()))
    page = insole_frame(fx, template).to_page(shape.outline())
    centre = page.mean(axis=0)
    a = np.deg2rad(-turn_deg)  # page y is down, so anticlockwise on screen is negative
    rot = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    return np.asarray((page - centre) @ rot.T + centre, np.float64)


def assert_valid_outline(m: InsoleMeasurements) -> None:
    out = m.outline_mm
    assert out.shape == (OUTLINE_POINTS, 2)
    assert out[0].tolist() == [0.0, 0.0]  # exactly: the database checks it
    assert out[1, 0] < 0, "after the heel point the outline must go to the medial side (-x)"
    assert signed_area(out) < 0, "heel -> medial -> toe -> lateral is clockwise in y-up"
    assert out[:, 1].min() > -0.05
    assert out[:, 1].max() == pytest.approx(m.length_mm, abs=0.5)
    # Evenly resampled
    step = np.hypot(*np.diff(np.vstack([out, out[:1]]), axis=0).T)
    assert step.max() - step.min() < 0.1


def test_definitions_match_the_test_fixtures() -> None:
    """The pipeline and the ground truth must mean the same thing by each number."""
    assert measure.HEEL_REGION == insoles.HEEL_REGION
    assert measure.ARCH_REGION == insoles.ARCH_REGION
    assert measure.BALL_REGION == insoles.BALL_REGION
    assert measure.TOE_WIDTH_AT == insoles.TOE_WIDTH_AT


# --- Pure functions on exact outlines -------------------------------------------------


@pytest.mark.parametrize("fixture", measurable_fixtures(), ids=lambda f: f.name)
def test_exact_outline_on_the_page_measures_as_expected(
    fixture: Fixture, template: Template
) -> None:
    page = insole_frame(fixture, template).to_page(fixture.shape.outline())
    m = measure_insole(page, template)
    assert m.side == fixture.shape.side
    assert_measurements_match(m.scalars(), fixture.expected)
    assert_valid_outline(m)


@pytest.mark.parametrize("toe_box", ["pointed", "round"])
def test_round_and_pointed_toes_recover_the_exact_frame(toe_box: str, template: Template) -> None:
    """With a single toe tip on the axis, the frame is exactly the generator's: the
    stored outline lies on the true one. (0.1 mm: the light smoothing rounds a pointed
    tip off by ~0.05 mm.)"""
    shape = InsoleShape(262, 63, 54, 97, toe_box, "left")  # type: ignore[arg-type]
    m = measure_insole(on_page(shape, template, turn_deg=3), template)
    truth = measure_in_frame(shape.outline())
    for key in MEASUREMENT_KEYS:
        assert getattr(m, key) == pytest.approx(truth[key], abs=0.1), key
    canon = canonical_truth(shape).astype(np.float32).reshape(-1, 1, 2)
    dist = [abs(cv2.pointPolygonTest(canon, (float(x), float(y)), True)) for x, y in m.outline_mm]
    assert max(dist) < 0.1


@pytest.mark.parametrize("turn_deg", [0, 25, 90, 135, 180, 225, 300])
@pytest.mark.parametrize("side", ["left", "right"])
def test_result_does_not_depend_on_how_the_insole_lies(
    turn_deg: float, side: str, template: Template
) -> None:
    """Heel/toe and side come from the shape, so a turned or reversed insole gives the
    same result as one on the guide axis."""
    shape = InsoleShape(255, 61, 52, 94, "round", side)  # type: ignore[arg-type]
    straight = measure_insole(on_page(shape, template), template)
    turned = measure_insole(on_page(shape, template, turn_deg=turn_deg), template)
    assert turned.side == side
    for key in MEASUREMENT_KEYS:
        assert getattr(turned, key) == pytest.approx(getattr(straight, key), abs=0.05), key
    assert np.abs(turned.outline_mm - straight.outline_mm).max() < 0.1


def test_left_and_right_insoles_give_the_same_canonical_outline(template: Template) -> None:
    left = measure_insole(
        on_page(InsoleShape(250, 60, 51, 93, "pointed", "left"), template), template
    )
    right = measure_insole(
        on_page(InsoleShape(250, 60, 51, 93, "pointed", "right"), template), template
    )
    assert (left.side, right.side) == ("left", "right")
    assert np.abs(left.outline_mm - right.outline_mm).max() < 0.1
    assert left.scalars() | {"side": "right"} == pytest.approx(right.scalars())


def test_canonical_outline_has_the_medial_side_at_minus_x(template: Template) -> None:
    shape = InsoleShape(260, 64, 55, 98, "round", "left")
    out = measure_insole(on_page(shape, template), template).outline_mm
    # At the ball the medial side bulges (52 % of the ball width); at the arch it cuts in.
    ball = out[np.abs(out[:, 1] - 0.72 * 260) < 2]
    arch = out[np.abs(out[:, 1] - 0.42 * 260) < 2]
    assert -ball[:, 0].min() > ball[:, 0].max()
    assert -arch[:, 0].min() < arch[:, 0].max()


def test_side_can_be_given(template: Template) -> None:
    shape = InsoleShape(260, 64, 55, 98, "round", "left")
    m = measure_insole(on_page(shape, template), template, side="right")
    assert m.side == "right"
    assert m.outline_mm[1, 0] < 0  # still ordered heel -> -x first


def test_contour_start_and_direction_do_not_matter(template: Template) -> None:
    page = on_page(InsoleShape(250, 60, 51, 93, "square", "right"), template)
    a = measure_insole(page, template)
    b = measure_insole(np.roll(page[::-1], 777, axis=0), template)
    assert np.abs(a.outline_mm - b.outline_mm).max() < 0.05
    assert a.scalars() == pytest.approx(b.scalars(), abs=0.01)


def test_heel_end_comes_from_the_shape_or_else_the_template_axis() -> None:
    """The wider half is the forefoot, whichever way the insole points. An ellipse has
    no wider half; then the template axis (y-up here) decides."""
    template_axis = np.array([0.6, 0.8])
    shape = InsoleShape(260, 64, 55, 98, "round", "right").outline()  # toe along +y
    for flip in (1.0, -1.0):
        toe = toe_direction(shape * flip, template_axis)
        assert toe == pytest.approx([0, flip], abs=0.02)

    t = np.linspace(0, 2 * np.pi, 2000, endpoint=False)
    ellipse = np.column_stack([45 * np.sin(t), 130 * np.cos(t)])  # long axis along y
    assert toe_direction(ellipse, template_axis) == pytest.approx([0, 1], abs=1e-6)
    assert toe_direction(ellipse, -template_axis) == pytest.approx([0, -1], abs=1e-6)


def test_principal_axis_of_a_rectangle() -> None:
    rect = np.array([[0, 0], [100, 0], [100, 20], [0, 20]], np.float64)
    centroid, axis = principal_axis(rect)
    assert centroid == pytest.approx([50, 10])
    assert abs(axis[0]) == pytest.approx(1)
    # Same for the reversed order (negative area) and uneven vertex spacing
    dense = np.vstack([np.column_stack([np.linspace(0, 100, 500), np.zeros(500)]), rect[2:]])
    centroid, axis = principal_axis(dense[::-1])
    assert centroid == pytest.approx([50, 10])
    assert abs(axis[0]) == pytest.approx(1)


def test_resample_closed_spaces_points_evenly_from_the_first() -> None:
    square = np.array([[0, 0], [0, 0], [10, 0], [10, 10], [0, 10]], np.float64)
    out = resample_closed(square, 8)
    assert out.tolist() == [[0, 0], [5, 0], [10, 0], [10, 5], [10, 10], [5, 10], [0, 10], [0, 5]]


# --- End to end: photo -> markers -> warp -> segment -> measure -----------------------


def test_fixture_photo_measures_within_tolerance(measurable: RenderedFixture) -> None:
    warp = warp_to_page(measurable.photo.image)
    m = measure_insole(segment_insole(warp).contour_mm, warp.template)
    assert m.side == measurable.fixture.shape.side
    assert_measurements_match(m.scalars(), measurable.fixture.expected)
    assert_valid_outline(m)
    # The stored 256 points carry the same shape: measured again, they agree.
    assert_measurements_match(measure_in_frame(m.outline_mm), measurable.fixture.expected)
