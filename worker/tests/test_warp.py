import cv2
import numpy as np
import pytest

from app.pipeline import config
from app.pipeline.rejections import Rejection, RejectionCode
from app.pipeline.template import Template, load_template
from app.pipeline.warp import warp_to_page
from tests.synthetic import (
    RECT_LENGTH_MM,
    RECT_WIDTH_MM,
    SHOTS,
    STRAIGHT,
    Shot,
    photograph,
    rect_corners_mm,
    render_page,
)

# How far a recovered point may be from the truth. Flat paper, synthetic photo: the
# warp itself should be far better than this; the budget is for the later steps.
POINT_TOLERANCE_MM = 0.5
LENGTH_TOLERANCE_MM = 1.0


@pytest.fixture(scope="module")
def template() -> Template:
    return load_template()


def _page_grid_mm(template: Template, step: float = 15.0) -> np.ndarray:
    xs = np.arange(0, template.page_width_mm + 0.1, step)
    ys = np.arange(0, template.page_height_mm + 0.1, step)
    return np.array([(x, y) for x in xs for y in ys], np.float64)


@pytest.mark.parametrize("shot_name", SHOTS)
def test_every_point_of_the_page_maps_back_to_its_mm(template: Template, shot_name: str) -> None:
    """Including the heel corner, far from any marker: the homography must hold over
    the whole page, not only near the markers that defined it."""
    photo = photograph(render_page(template), template, SHOTS[shot_name])
    result = warp_to_page(photo.image, template)

    truth = _page_grid_mm(template)
    recovered = result.photo_to_mm(photo.project(truth))
    error = np.linalg.norm(recovered - truth, axis=1)
    assert error.max() < POINT_TOLERANCE_MM, f"max error {error.max():.3f} mm"
    assert result.markers_found == sorted(template.marker_corners_mm)
    assert result.marker_fit_error_mm < 0.5


@pytest.mark.parametrize("shot_name", SHOTS)
def test_rectangle_on_the_diagonal_measures_its_true_size(
    template: Template, shot_name: str
) -> None:
    """End to end: segment the dark test rectangle in the flattened page and measure it."""
    photo = photograph(render_page(template), template, SHOTS[shot_name])
    result = warp_to_page(photo.image, template)
    gray = cv2.cvtColor(result.page, cv2.COLOR_BGR2GRAY)

    zone = np.zeros(gray.shape, np.uint8)
    cv2.fillPoly(
        zone, [np.round(template.measuring_zone_mm * result.px_per_mm).astype(np.int32)], 255
    )
    # Otsu picks the dark/light threshold from the zone's own pixels, so dim photos work.
    # (Real segmentation, with its quality checks, is #22.)
    threshold, _ = cv2.threshold(gray[zone > 0], 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    dark = ((gray < threshold) & (zone > 0)).astype(np.uint8)
    contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    (_, _), (w, h), _ = cv2.minAreaRect(max(contours, key=cv2.contourArea))

    length, width = sorted((w / result.px_per_mm, h / result.px_per_mm), reverse=True)
    assert length == pytest.approx(RECT_LENGTH_MM, abs=LENGTH_TOLERANCE_MM)
    assert width == pytest.approx(RECT_WIDTH_MM, abs=LENGTH_TOLERANCE_MM)


def test_page_image_has_the_configured_resolution(template: Template) -> None:
    result = warp_to_page(photograph(render_page(template), template, SHOTS["straight"]).image)
    assert result.page.shape[:2] == (
        round(template.page_height_mm * config.PX_PER_MM),
        round(template.page_width_mm * config.PX_PER_MM),
    )
    # The page sits fully inside this photo, so every page pixel is backed by it.
    assert result.valid.min() == 255


def test_one_covered_marker_is_tolerated(template: Template) -> None:
    photo = photograph(render_page(template, covered=(2,)), template, SHOTS["tilted"])
    result = warp_to_page(photo.image, template)

    assert result.markers_found == [0, 1, 3]
    truth = _page_grid_mm(template)
    error = np.linalg.norm(result.photo_to_mm(photo.project(truth)) - truth, axis=1)
    assert error.max() < POINT_TOLERANCE_MM


def test_two_covered_markers_are_rejected(template: Template) -> None:
    photo = photograph(render_page(template, covered=(0, 2)), template, SHOTS["straight"])
    with pytest.raises(Rejection) as exc:
        warp_to_page(photo.image, template)
    assert exc.value.code is RejectionCode.MARKERS_NOT_FOUND
    assert "black squares" in exc.value.message


def test_photo_without_template_is_rejected(template: Template) -> None:
    blank = np.full((3000, 2000, 3), 128, np.uint8)
    with pytest.raises(Rejection) as exc:
        warp_to_page(blank, template)
    assert exc.value.code is RejectionCode.MARKERS_NOT_FOUND


def test_folded_paper_is_rejected(template: Template) -> None:
    """A marker 6 mm away from where the JSON says can't sit on the same flat page."""
    page = render_page(template, shifted_mm={2: (-6, -6)})
    with pytest.raises(Rejection) as exc:
        warp_to_page(photograph(page, template, SHOTS["straight"]).image, template)
    assert exc.value.code is RejectionCode.PAPER_NOT_FLAT


def test_parts_of_the_page_outside_the_photo_are_marked_invalid(template: Template) -> None:
    # Page shifted left so its left edge (about 2.5 mm, no markers) falls outside the photo.
    shot = Shot(tuple((x - 330, y) for x, y in STRAIGHT))
    result = warp_to_page(photograph(render_page(template), template, shot).image, template)

    px = result.px_per_mm
    assert result.valid[:, : round(1.5 * px)].max() == 0
    assert result.valid[:, round(5 * px) :].min() == 255


def test_photo_and_mm_conversions_are_inverse(template: Template) -> None:
    photo = photograph(render_page(template), template, SHOTS["tilted"])
    result = warp_to_page(photo.image, template)
    mm = np.array([[10.0, 20.0], [105.0, 148.5], [200.0, 290.0]])
    assert np.allclose(result.photo_to_mm(result.mm_to_photo(mm)), mm, atol=1e-6)


def test_grayscale_photos_work(template: Template) -> None:
    photo = photograph(render_page(template), template, SHOTS["straight"])
    gray = np.asarray(cv2.cvtColor(photo.image, cv2.COLOR_BGR2GRAY), np.uint8)
    result = warp_to_page(gray, template)
    assert result.page.ndim == 2


def test_rect_helper_lies_inside_the_measuring_zone(template: Template) -> None:
    zone = template.measuring_zone_mm.astype(np.float32).reshape(-1, 1, 2)
    for x, y in rect_corners_mm(template):
        assert cv2.pointPolygonTest(zone, (float(x), float(y)), False) > 0
