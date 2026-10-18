"""Tests of the fixture generator itself, plus the pipeline steps that exist so far.

If the generator drifts, every later regression test checks against the wrong truth,
so the ground truth is verified here independently of the pipeline.
"""

import numpy as np
import pytest

from app.pipeline.template import load_template
from app.pipeline.warp import warp_to_page
from tests.insoles import InsoleShape, measure_in_frame
from tests.regression import (
    MEASUREMENT_KEYS,
    TOLERANCE_MM,
    Expected,
    Fixture,
    RenderedFixture,
    all_fixtures,
    assert_measurements_match,
    insole_frame,
    measurable_fixtures,
    render_fixture,
)

# Measurable fixtures keep this much white paper between the insole and the dashed
# guides, so a correct segmentation never has a reason to reject them.
MIN_ZONE_CLEARANCE_MM = 3.0


def test_there_are_fixtures_covering_every_toe_box_and_both_sides() -> None:
    fixtures = measurable_fixtures()
    assert len(fixtures) >= 8
    assert {f.shape.toe_box for f in fixtures} == {"pointed", "round", "square"}
    assert {f.shape.side for f in fixtures} == {"left", "right"}


@pytest.mark.parametrize("fixture", measurable_fixtures(), ids=lambda f: f.name)
def test_expected_json_matches_the_drawn_shape(fixture: Fixture) -> None:
    """Measure the dense outline with the written-down definitions, in the exact frame."""
    truth = measure_in_frame(fixture.shape.outline())
    for key in MEASUREMENT_KEYS:
        assert truth[key] == pytest.approx(fixture.expected.measurements[key], abs=0.1), key
    assert fixture.expected.toe_box_shape == fixture.shape.toe_box


@pytest.mark.parametrize("side", ["left", "right"])
def test_outline_is_closed_simple_and_on_the_expected_side(side: str) -> None:
    shape = InsoleShape(260, 64, 55, 98, "round", side)  # type: ignore[arg-type]
    pts = shape.outline()
    # Shoelace: positive area means counter-clockwise in a y-up frame.
    area = 0.5 * float(
        np.sum(pts[:, 0] * np.roll(pts[:, 1], -1) - np.roll(pts[:, 0], -1) * pts[:, 1])
    )
    assert 0.6 * 260 * 98 * 0.75 < abs(area) < 260 * 98
    # Option A: heel point at the origin, toe tip at (0, length).
    assert pts[0] == pytest.approx([0, 0], abs=1e-9)
    assert pts[:, 1].min() == pytest.approx(0, abs=1e-9)
    assert pts[np.argmax(pts[:, 1])] == pytest.approx([0, 260], abs=1e-9)
    # The medial side (ball bulge) is +x for a left insole, -x for a right one.
    ball = pts[np.abs(pts[:, 1] - 0.72 * 260) < 0.5]
    medial = ball[:, 0].max() if side == "left" else -ball[:, 0].min()
    assert medial == pytest.approx(0.52 * 98, abs=0.2)
    # Heel -> medial -> toe -> lateral: the first steps go to the medial side.
    assert np.sign(pts[5, 0]) == (1 if side == "left" else -1)
    # So a right insole runs clockwise in y-up (negative area), a left one anticlockwise.
    assert np.sign(area) == (1 if side == "left" else -1)


def test_non_waisted_shapes_are_refused() -> None:
    with pytest.raises(ValueError, match="waisted"):
        InsoleShape(260, 60, 65, 98, "round")


def test_every_fixture_has_a_valid_expected_block() -> None:
    for f in all_fixtures():
        assert f.description
        assert (f.expected.rejection is None) != (not f.expected.measurements)


def _inside_convex(poly: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Signed distance (mm) of each point to the nearest edge; > 0 inside."""
    a, b = poly, np.roll(poly, -1, axis=0)
    edge = b - a
    normal = np.column_stack([-edge[:, 1], edge[:, 0]]) / np.linalg.norm(edge, axis=1)[:, None]
    # Orient normals inwards.
    centre = poly.mean(axis=0)
    flip = np.sign(np.sum((centre - a) * normal, axis=1))
    d = ((pts[:, None, :] - a[None]) * (normal * flip[:, None])[None]).sum(axis=2)
    return np.asarray(d.min(axis=1))


@pytest.mark.parametrize("fixture", measurable_fixtures(), ids=lambda f: f.name)
def test_measurable_fixtures_lie_inside_the_measuring_zone(fixture: Fixture) -> None:
    template = load_template()
    outline_mm = insole_frame(fixture, template).to_page(fixture.shape.outline())
    clearance = _inside_convex(template.measuring_zone_mm, outline_mm).min()
    assert clearance >= MIN_ZONE_CLEARANCE_MM, f"only {clearance:.1f} mm from the guides"


def test_rendering_is_deterministic() -> None:
    fixture = min(measurable_fixtures(), key=lambda f: f.shot.size[0] * f.shot.size[1])
    a, b = render_fixture(fixture), render_fixture(fixture)
    assert np.array_equal(a.photo.image, b.photo.image)


def test_frame_round_trip(measurable: RenderedFixture) -> None:
    frame = measurable.frame
    back = frame.to_frame(measurable.outline_mm)
    assert np.allclose(back, measurable.fixture.shape.outline(), atol=1e-9)


def test_insole_outline_survives_the_warp(measurable: RenderedFixture) -> None:
    """The flattened page shows the insole where the ground truth says, to 0.5 mm.
    Segmentation (#22) and measuring (#23) start from this."""
    result = warp_to_page(measurable.photo.image)
    recovered = result.photo_to_mm(measurable.photo.project(measurable.outline_mm))
    error = np.linalg.norm(recovered - measurable.outline_mm, axis=1)
    assert error.max() < 0.5, f"max error {error.max():.3f} mm"


def test_the_insole_is_visible_in_the_photo(measurable: RenderedFixture) -> None:
    """The photo really shows a dark insole on light paper where the outline says.
    Guards against a renderer bug that would make every later test vacuous."""
    gray = measurable.photo.image[..., 0].astype(float)
    frame = measurable.frame
    length = measurable.fixture.shape.length_mm
    # A point on the axis in the midfoot (inside) and one 15 mm beyond the toe (paper).
    inside, outside = frame.to_page(np.array([[0.0, 0.5 * length], [0.0, length + 15.0]]))
    pi, po = measurable.photo.project(np.array([inside, outside])).round().astype(int)
    assert gray[pi[1], pi[0]] + 25 < gray[po[1], po[0]]


class TestAssertMeasurementsMatch:
    expected = Expected(measurements={k: 100.0 for k in MEASUREMENT_KEYS}, toe_box_shape="round")

    def test_passes_within_tolerance(self) -> None:
        measured = {k: 100.0 + 0.9 * TOLERANCE_MM[k] for k in MEASUREMENT_KEYS}
        assert_measurements_match({**measured, "toe_box_shape": "round"}, self.expected)

    def test_lists_every_failure(self) -> None:
        measured: dict[str, float | str] = {k: 100.0 for k in MEASUREMENT_KEYS}
        measured["length_mm"] = 101.5
        measured["ball_width_mm"] = 98.0
        measured["toe_box_shape"] = "square"
        del measured["arch_width_mm"]
        with pytest.raises(AssertionError) as err:
            assert_measurements_match(measured, self.expected)
        text = str(err.value)
        assert "length_mm: 101.50" in text
        assert "ball_width_mm: 98.00" in text
        assert "arch_width_mm: missing" in text
        assert "toe_box_shape" in text

    def test_checks_only_the_requested_keys(self) -> None:
        assert_measurements_match({"length_mm": 100.5}, self.expected, keys=["length_mm"])
