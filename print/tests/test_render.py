from pathlib import Path

import cv2
import numpy as np
import pypdfium2 as pdfium
import pytest

from fitfinder_template.__main__ import main
from fitfinder_template.geometry import GEOMETRY_DIR, Rect, TemplateGeometry, load
from fitfinder_template.render import ZONE_CLEARANCE_MM, render

DPI = 300
PX_PER_MM = DPI / 25.4
# Detected corners vs. JSON. Covers rasterisation and sub-pixel refinement error.
TOLERANCE_MM = 0.3


@pytest.fixture(scope="module")
def geometry() -> TemplateGeometry:
    return load()


@pytest.fixture(scope="module")
def rendered(geometry: TemplateGeometry, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return main(
        [
            str(GEOMETRY_DIR / f"{geometry.id}.json"),
            "-o",
            str(tmp_path_factory.mktemp("pdf") / "t.pdf"),
        ]
    )


def test_page_is_the_template_size(geometry: TemplateGeometry, rendered: Path) -> None:
    w_pt, h_pt = pdfium.PdfDocument(rendered)[0].get_size()
    assert w_pt * 25.4 / 72 == pytest.approx(geometry.page_width_mm, abs=0.01)
    assert h_pt * 25.4 / 72 == pytest.approx(geometry.page_height_mm, abs=0.01)


def test_output_is_reproducible(geometry: TemplateGeometry, tmp_path: Path) -> None:
    render(geometry, tmp_path / "a.pdf")
    render(geometry, tmp_path / "b.pdf")
    assert (tmp_path / "a.pdf").read_bytes() == (tmp_path / "b.pdf").read_bytes()


def test_nothing_is_printed_in_the_zone_or_near_markers(
    geometry: TemplateGeometry, tmp_path: Path
) -> None:
    printed = render(geometry, tmp_path / "t.pdf")
    assert printed
    cell = geometry.markers[0].size_mm / 6
    page = Rect(0, 0, geometry.page_width_mm, geometry.page_height_mm)
    for kind, box in printed:
        grown = box.grow(ZONE_CLEARANCE_MM - 0.5)
        assert not geometry.measuring_zone.intersects_rect(grown), f"{kind} {box} too close"
        for m in geometry.markers:
            assert not m.rect.grow(cell).intersects(box), (
                f"{kind} {box} in marker {m.id} quiet zone"
            )
        assert page.grow(-3).x_mm <= box.x_mm and box.right_mm <= page.grow(-3).right_mm


def test_markers_detected_where_the_geometry_says(
    geometry: TemplateGeometry, rendered: Path
) -> None:
    """Rasterise the PDF and find the markers like the worker will (#19)."""
    image = pdfium.PdfDocument(rendered)[0].render(scale=DPI / 72, grayscale=True).to_numpy()
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    detector = cv2.aruco.ArucoDetector(
        cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, geometry.aruco_dictionary)), params
    )
    corners, ids, _ = detector.detectMarkers(gray)

    assert ids is not None
    found = {
        int(i): c.reshape(4, 2) / PX_PER_MM for i, c in zip(ids.flatten(), corners, strict=True)
    }
    assert sorted(found) == sorted(m.id for m in geometry.markers)
    for m in geometry.markers:
        # Pixel centres sit half a pixel inside the edges they sample.
        expected = np.array(m.corners_mm) - 0.5 / PX_PER_MM
        assert np.abs(found[m.id] - expected).max() < TOLERANCE_MM, f"marker {m.id}"
