import json
from pathlib import Path

import jsonschema
import pytest

from fitfinder_template.geometry import GEOMETRY_DIR, Polygon, Rect, TemplateGeometry, load
from fitfinder_template.render import marker_bits

TEMPLATES = sorted(p for p in GEOMETRY_DIR.glob("*.json") if p.name != "template.schema.json")


def _quiet_zone_mm(g: TemplateGeometry) -> float:
    """ArUco detection needs at least one cell of white around each marker."""
    cells = marker_bits(g.aruco_dictionary, 0, g.aruco_border_bits).shape[0]
    return float(g.markers[0].size_mm / cells)


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda p: p.stem)
def test_matches_schema(path: Path) -> None:
    schema = json.loads((GEOMETRY_DIR / "template.schema.json").read_text())
    jsonschema.validate(json.loads(path.read_text()), schema)


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda p: p.stem)
def test_file_name_is_template_id(path: Path) -> None:
    assert load(path).id == path.stem


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda p: p.stem)
def test_markers_are_unique_on_page_and_clear_of_the_zone(path: Path) -> None:
    g = load(path)
    quiet = _quiet_zone_mm(g)
    assert len({m.id for m in g.markers}) == len(g.markers)
    for m in g.markers:
        r = m.rect.grow(quiet)
        assert r.x_mm >= 0 and r.y_mm >= 0
        assert r.right_mm <= g.page_width_mm and r.bottom_mm <= g.page_height_mm
        assert not g.measuring_zone.intersects_rect(r), f"marker {m.id} overlaps the zone"
    for a in g.markers:
        for b in g.markers:
            if a.id < b.id:
                assert not a.rect.grow(quiet).intersects(b.rect)


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda p: p.stem)
def test_zone_is_on_the_page(path: Path) -> None:
    g = load(path)
    for x, y in g.measuring_zone.points:
        assert 0 <= x <= g.page_width_mm and 0 <= y <= g.page_height_mm


def test_a4_zone_fits_a_120mm_wide_band_along_the_diagonal() -> None:
    g = load()
    # Midpoint of the heel-toe axis, and points 60 mm either side of it.
    cx, cy = g.page_width_mm / 2, g.page_height_mm / 2
    assert g.measuring_zone.contains((cx, cy))
    assert not g.measuring_zone.contains((10, 10))
    assert not g.measuring_zone.contains((200, 287))


def test_polygon_rect_intersection() -> None:
    triangle = Polygon([(0, 0), (10, 0), (0, 10)])
    assert triangle.intersects_rect(Rect(1, 1, 1, 1))
    assert not triangle.intersects_rect(Rect(8, 8, 2, 2))
    assert triangle.intersects_rect(Rect(-5, -5, 20, 20))
    assert triangle.x_span_at(5) == (0, 5)
    assert triangle.x_span_at(20) is None
