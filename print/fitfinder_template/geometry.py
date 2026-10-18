"""Typed view of a template geometry JSON file (print/geometry/*.json).

The JSON is the single source of truth: this generator draws from it, and the worker
uses the same numbers to turn detected markers into millimetres.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

GEOMETRY_DIR = Path(__file__).resolve().parent.parent / "geometry"
DEFAULT_TEMPLATE = GEOMETRY_DIR / "a4-v1.json"

Point = tuple[float, float]


@dataclass(frozen=True)
class Rect:
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float

    @property
    def right_mm(self) -> float:
        return self.x_mm + self.width_mm

    @property
    def bottom_mm(self) -> float:
        return self.y_mm + self.height_mm

    @property
    def corners(self) -> list[Point]:
        return [
            (self.x_mm, self.y_mm),
            (self.right_mm, self.y_mm),
            (self.right_mm, self.bottom_mm),
            (self.x_mm, self.bottom_mm),
        ]

    def grow(self, by_mm: float) -> "Rect":
        return Rect(
            self.x_mm - by_mm,
            self.y_mm - by_mm,
            self.width_mm + 2 * by_mm,
            self.height_mm + 2 * by_mm,
        )

    def intersects(self, other: "Rect") -> bool:
        return (
            self.x_mm < other.right_mm
            and other.x_mm < self.right_mm
            and self.y_mm < other.bottom_mm
            and other.y_mm < self.bottom_mm
        )


@dataclass(frozen=True)
class Polygon:
    """Convex polygon."""

    points: list[Point]

    def edges(self) -> list[tuple[Point, Point]]:
        n = len(self.points)
        return [(self.points[i], self.points[(i + 1) % n]) for i in range(n)]

    def contains(self, p: Point) -> bool:
        signs = set()
        for (ax, ay), (bx, by) in self.edges():
            cross = (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax)
            if cross != 0:
                signs.add(cross > 0)
        return len(signs) <= 1

    def x_span_at(self, y: float) -> tuple[float, float] | None:
        """Leftmost and rightmost x of the polygon on the horizontal line at y."""
        xs = []
        for (ax, ay), (bx, by) in self.edges():
            if min(ay, by) <= y <= max(ay, by):
                if ay == by:
                    xs += [ax, bx]
                else:
                    xs.append(ax + (y - ay) / (by - ay) * (bx - ax))
        return (min(xs), max(xs)) if xs else None

    def intersects_rect(self, r: Rect) -> bool:
        """Separating axis test: two convex shapes are disjoint iff some edge normal
        separates their projections."""
        rect_pts = r.corners
        axes: list[Point] = [(1, 0), (0, 1)]
        axes += [(ay - by, bx - ax) for (ax, ay), (bx, by) in self.edges()]
        for nx, ny in axes:
            proj_p = [nx * x + ny * y for x, y in self.points]
            proj_r = [nx * x + ny * y for x, y in rect_pts]
            if max(proj_p) <= min(proj_r) or max(proj_r) <= min(proj_p):
                return False
        return True


@dataclass(frozen=True)
class Marker:
    id: int
    x_mm: float
    y_mm: float
    size_mm: float

    @property
    def rect(self) -> Rect:
        return Rect(self.x_mm, self.y_mm, self.size_mm, self.size_mm)

    @property
    def corners_mm(self) -> list[Point]:
        """Corners in OpenCV ArUco order: top-left, top-right, bottom-right, bottom-left."""
        return self.rect.corners

    @property
    def center_mm(self) -> Point:
        return (self.x_mm + self.size_mm / 2, self.y_mm + self.size_mm / 2)


@dataclass(frozen=True)
class Ruler:
    x_mm: float
    y_mm: float
    length_mm: float
    direction: Literal["vertical", "horizontal"]
    tick_side: Literal["up", "down", "left", "right"]


@dataclass(frozen=True)
class TemplateGeometry:
    id: str
    page_width_mm: float
    page_height_mm: float
    aruco_dictionary: str
    aruco_border_bits: int
    markers: list[Marker]
    measuring_zone: Polygon
    heel_mm: Point
    toe_mm: Point
    rulers: list[Ruler]

    @property
    def page(self) -> Rect:
        return Rect(0, 0, self.page_width_mm, self.page_height_mm)


def _point(p: list[float]) -> Point:
    return (p[0], p[1])


def load(path: Path = DEFAULT_TEMPLATE) -> TemplateGeometry:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    size = data["marker_size_mm"]
    return TemplateGeometry(
        id=data["id"],
        page_width_mm=data["page"]["width_mm"],
        page_height_mm=data["page"]["height_mm"],
        aruco_dictionary=data["aruco"]["dictionary"],
        aruco_border_bits=data["aruco"]["border_bits"],
        markers=[Marker(m["id"], m["x_mm"], m["y_mm"], size) for m in data["markers"]],
        measuring_zone=Polygon([_point(p) for p in data["measuring_zone"]["points_mm"]]),
        heel_mm=_point(data["insole_axis"]["heel_mm"]),
        toe_mm=_point(data["insole_axis"]["toe_mm"]),
        rulers=[Ruler(**r) for r in data["rulers"]],
    )
