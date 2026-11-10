import math

import cv2
import numpy as np
import pytest

from app.pipeline import config
from app.pipeline.rejections import Rejection, RejectionCode
from app.pipeline.segment import (
    Segmentation,
    edge_blur_px,
    edge_profile,
    segment,
    segment_insole,
)
from app.pipeline.template import Template, load_template
from app.pipeline.warp import warp_to_page
from tests.insoles import measure_in_frame
from tests.regression import RenderedFixture, assert_measurements_match

PPM = config.PX_PER_MM


@pytest.fixture(scope="module")
def template() -> Template:
    return load_template()


# --- Regression against the #25 fixtures -------------------------------------------


def test_fixture_outline_matches_the_truth(measurable: RenderedFixture) -> None:
    seg = segment_insole(warp_to_page(measurable.photo.image))

    truth = np.zeros(seg.mask.shape, np.uint8)
    shift = 4
    pts = np.round(measurable.outline_mm * PPM * 2**shift).astype(np.int32)
    cv2.fillPoly(truth, [pts], 255, cv2.LINE_8, shift)
    iou = np.count_nonzero(truth & seg.mask) / np.count_nonzero(truth | seg.mask)
    assert iou > 0.99

    poly = measurable.outline_mm.astype(np.float32).reshape(-1, 1, 2)
    dist = [abs(cv2.pointPolygonTest(poly, (float(x), float(y)), True)) for x, y in seg.contour_mm]
    assert max(dist) < 0.5, f"outline up to {max(dist):.2f} mm off"


def test_fixture_measures_within_tolerance_in_the_true_frame(
    measurable: RenderedFixture,
) -> None:
    """Measure the segmented outline in the *known* insole frame. That isolates
    segmentation errors from axis-finding, which is #23's job."""
    seg = segment_insole(warp_to_page(measurable.photo.image))
    measured = measure_in_frame(measurable.frame.to_frame(seg.contour_mm))
    assert_measurements_match(measured, measurable.fixture.expected)


def test_fixture_passes_the_quality_checks_comfortably(measurable: RenderedFixture) -> None:
    seg = segment_insole(warp_to_page(measurable.photo.image))
    assert seg.edge_blur_mm < config.MAX_EDGE_BLUR_MM / 2
    assert seg.paper_brightness > config.MIN_PAPER_BRIGHTNESS
    assert seg.contrast > 2 * config.MIN_INSOLE_CONTRAST


def test_fixture_is_rejected_for_the_expected_reason(rejected: RenderedFixture) -> None:
    with pytest.raises(Rejection) as err:
        segment_insole(warp_to_page(rejected.photo.image))
    assert err.value.code == rejected.fixture.expected.rejection


# --- Unit tests on hand-made page images ---------------------------------------------


def _page(template: Template, value: int = 230) -> np.ndarray:
    h, w = round(template.page_height_mm * PPM), round(template.page_width_mm * PPM)
    return np.full((h, w), value, np.uint8)


def _valid(page: np.ndarray) -> np.ndarray:
    return np.full(page.shape[:2], 255, np.uint8)


def _centre_px(template: Template) -> tuple[int, int]:
    return round(template.page_width_mm / 2 * PPM), round(template.page_height_mm / 2 * PPM)


def _axis_angle(template: Template) -> float:
    (hx, hy), (tx, ty) = template.heel_mm, template.toe_mm
    return math.degrees(math.atan2(ty - hy, tx - hx))


def _draw_ellipse(
    page: np.ndarray,
    template: Template,
    axes_mm: tuple[float, float] = (120, 45),
    tone: int = 60,
    offset_mm: tuple[float, float] = (0.0, 0.0),
) -> np.ndarray:
    """A 240 x 90 mm 'insole' along the template's diagonal."""
    cx, cy = _centre_px(template)
    centre = (cx + round(offset_mm[0] * PPM), cy + round(offset_mm[1] * PPM))
    axes = (round(axes_mm[0] * PPM), round(axes_mm[1] * PPM))
    cv2.ellipse(page, centre, axes, _axis_angle(template), 0, 360, tone, -1, cv2.LINE_AA)
    return page


def _segment(template: Template, page: np.ndarray, valid: np.ndarray | None = None) -> Segmentation:
    valid = _valid(page) if valid is None else valid
    return segment(page, valid, template.measuring_zone_mm, PPM)


def _code(template: Template, page: np.ndarray, valid: np.ndarray | None = None) -> str:
    with pytest.raises(Rejection) as err:
        _segment(template, page, valid)
    return err.value.code


ELLIPSE_AREA_MM2 = math.pi * 120 * 45


def test_finds_a_clean_ellipse(template: Template) -> None:
    seg = _segment(template, _draw_ellipse(_page(template), template))
    assert seg.area_mm2 == pytest.approx(ELLIPSE_AREA_MM2, rel=0.005)
    assert seg.contour_mm == pytest.approx(seg.contour_px / PPM)
    assert seg.edge_blur_mm < 0.2


def test_accepts_colour_images(template: Template) -> None:
    page = cv2.cvtColor(_draw_ellipse(_page(template), template), cv2.COLOR_GRAY2BGR)
    assert _segment(template, page).area_mm2 == pytest.approx(ELLIPSE_AREA_MM2, rel=0.005)


def test_strong_light_gradient_does_not_move_the_outline(template: Template) -> None:
    """A single global threshold would fail here: the dark corner of the paper is darker
    than a light insole would be. Flattening the lighting fixes that."""
    page = _draw_ellipse(_page(template, 240), template, tone=120).astype(np.float32)
    ramp = np.linspace(1.0, 0.35, page.shape[1], dtype=np.float32)[None, :]
    page = np.clip(page * ramp, 0, 255).astype(np.uint8)
    seg = _segment(template, page)
    assert seg.area_mm2 == pytest.approx(ELLIPSE_AREA_MM2, rel=0.01)


def test_holes_inside_the_insole_are_filled(template: Template) -> None:
    page = _draw_ellipse(_page(template), template)
    cx, cy = _centre_px(template)
    cv2.circle(page, (cx, cy), round(15 * PPM), 230, -1)  # logo as light as the paper
    cv2.putText(page, "FIT", (cx - 300, cy + 400), cv2.FONT_HERSHEY_SIMPLEX, 6, 220, 20)
    seg = _segment(template, page)
    assert seg.area_mm2 == pytest.approx(ELLIPSE_AREA_MM2, rel=0.005)


def test_noise_specks_beside_the_insole_are_ignored(template: Template) -> None:
    page = _draw_ellipse(_page(template), template)
    rng = np.random.default_rng(0)
    for _ in range(40):  # crumbs on the paper, under 1 mm
        x, y = rng.integers(400, 1700), rng.integers(400, 2500)
        cv2.circle(page, (int(x), int(y)), 2, 40, -1)
    seg = _segment(template, page)
    assert seg.area_mm2 == pytest.approx(ELLIPSE_AREA_MM2, rel=0.005)


def test_empty_template_is_insole_not_found(template: Template) -> None:
    assert _code(template, _page(template)) == RejectionCode.INSOLE_NOT_FOUND


def test_small_dark_object_is_insole_not_found(template: Template) -> None:
    page = _draw_ellipse(_page(template), template, axes_mm=(40, 25))
    assert _code(template, page) == RejectionCode.INSOLE_NOT_FOUND


def test_zone_outside_the_photo_is_insole_not_found(template: Template) -> None:
    page = _draw_ellipse(_page(template), template)
    assert _code(template, page, np.zeros_like(page)) == RejectionCode.INSOLE_NOT_FOUND


def test_dark_photo_is_too_dark(template: Template) -> None:
    page = _draw_ellipse(_page(template, 45), template, tone=10)
    assert _code(template, page) == RejectionCode.TOO_DARK


def test_dim_but_usable_photo_is_accepted(template: Template) -> None:
    page = _draw_ellipse(_page(template, 80), template, tone=20)
    assert _segment(template, page).area_mm2 == pytest.approx(ELLIPSE_AREA_MM2, rel=0.005)


def test_blurred_photo_is_too_blurry(template: Template) -> None:
    page = _draw_ellipse(_page(template), template)
    page = cv2.GaussianBlur(page, (0, 0), 0.8 * PPM)
    assert _code(template, page) == RejectionCode.TOO_BLURRY


def _cast_shadow(page: np.ndarray, template: Template, penumbra_mm: float) -> np.ndarray:
    """A lamp low on one side: the insole's shadow lies 6 mm beside it, as dark as a dark
    insole, with a soft border. Drawn under the insole, then the insole on top."""
    shadow = np.zeros(page.shape, np.float32)
    _draw_ellipse(shadow, template, tone=1, offset_mm=(-4.9, -3.5))  # across the axis
    shadow = np.asarray(cv2.GaussianBlur(shadow, (0, 0), max(penumbra_mm * PPM, 0.1)), np.float32)
    out = (page.astype(np.float32) * (1 - 0.75 * shadow)).astype(np.uint8)
    return _draw_ellipse(out, template, axes_mm=(118, 43))


def test_insole_with_a_soft_cast_shadow_is_shadow(template: Template) -> None:
    page = _cast_shadow(_page(template), template, penumbra_mm=2.5)
    assert _code(template, page) == RejectionCode.SHADOW


def test_blurred_photo_with_a_shadow_is_too_blurry(template: Template) -> None:
    page = _cast_shadow(_page(template), template, penumbra_mm=2.5)
    page = cv2.GaussianBlur(page, (0, 0), 0.8 * PPM)
    assert _code(template, page) == RejectionCode.TOO_BLURRY


def test_shadow_border_as_sharp_as_the_insole_is_not_detected(template: Template) -> None:
    """The known blind spot: with no penumbra (e.g. after a scanner app's contrast boost),
    the shadow is just a bigger, dark insole. Here so a change in behaviour is noticed."""
    seg = _segment(template, _cast_shadow(_page(template), template, penumbra_mm=0.0))
    assert seg.area_mm2 > ELLIPSE_AREA_MM2 * 1.05


def test_edge_profile_skips_the_points_it_is_told_to() -> None:
    img = np.full((200, 400), 1.0, np.float32)
    cv2.circle(img, (200, 100), 70, 0.2, -1)
    img = np.asarray(cv2.GaussianBlur(img, (0, 0), 20.0), np.float32)
    theta = np.linspace(0, 2 * np.pi, 440, endpoint=False)
    contour = np.column_stack([200 + 70 * np.cos(theta), 100 + 70 * np.sin(theta)])
    nothing, everything = np.zeros(img.shape, bool), np.ones(img.shape, bool)
    judged = edge_profile(img, contour, 0.8, nothing, 20, 15.0)
    assert judged.soft_px == len(contour)
    assert judged.sharp_px == pytest.approx(20.0, rel=0.15)
    skipped = edge_profile(img, contour, 0.8, everything, 20, 15.0)
    assert skipped.soft_px == 0
    assert skipped.sharp_px == math.inf


def test_insole_across_the_guide_touches_the_edge(template: Template) -> None:
    # Shifted 30 mm across the band (which is 120 mm wide) towards the top-left.
    page = _draw_ellipse(_page(template), template, offset_mm=(-25, -17))
    assert _code(template, page) == RejectionCode.INSOLE_TOUCHES_EDGE


def test_insole_cut_off_by_the_photo_edge_touches_the_edge(template: Template) -> None:
    page = _draw_ellipse(_page(template), template)
    valid = _valid(page)
    valid[: page.shape[0] // 3] = 0  # the photo didn't show the top third of the page
    assert _code(template, page, valid) == RejectionCode.INSOLE_TOUCHES_EDGE


def test_insole_close_to_but_inside_the_guides_is_accepted(template: Template) -> None:
    # The band is 120 mm wide: a 110 mm wide ellipse leaves 5 mm each side.
    page = _draw_ellipse(_page(template), template, axes_mm=(120, 55))
    _segment(template, page)


@pytest.mark.parametrize("sigma_px", [1.5, 3.0, 5.0, 8.0])
def test_edge_blur_estimate_matches_a_known_gaussian_blur(sigma_px: float) -> None:
    img = np.full((200, 400), 1.0, np.float32)
    cv2.circle(img, (200, 100), 70, 0.2, -1)
    img = np.asarray(cv2.GaussianBlur(img, (0, 0), sigma_px), np.float32)
    theta = np.linspace(0, 2 * np.pi, 360, endpoint=False)
    contour = np.column_stack([200 + 70 * np.cos(theta), 100 + 70 * np.sin(theta)])
    assert edge_blur_px(img, contour, 0.8) == pytest.approx(sigma_px, rel=0.15)


def test_edge_blur_of_a_flat_image_is_infinite() -> None:
    img = np.ones((50, 50), np.float32)
    assert edge_blur_px(img, np.array([[25.0, 25.0]]), 0.8) == math.inf
