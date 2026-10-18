"""Draws the printable template PDF from a TemplateGeometry.

Everything is drawn as vectors (no embedded bitmaps), so marker edges stay sharp at
any printer resolution. Geometry uses the template convention (mm, origin top-left,
y down); reportlab uses points with the origin bottom-left, so `_pt` converts.

Every element records its bounding box in `printed`, so tests can prove that nothing
is printed inside the measuring zone or in a marker's quiet zone.
"""

import math
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt
from reportlab.lib.colors import Color, black, white
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

from fitfinder_template.geometry import Marker, Point, Rect, Ruler, TemplateGeometry

# The zone outline is light grey so segmentation doesn't mistake it for the insole's edge.
GUIDE_GREY = Color(0.72, 0.72, 0.72)
TEXT_GREY = Color(0.2, 0.2, 0.2)
FONT, FONT_BOLD = "Helvetica", "Helvetica-Bold"
PT_TO_MM = 25.4 / 72

# Instructions fill the free triangle at the top-left, starting below the ruler.
INSTRUCTIONS_X_MM, INSTRUCTIONS_Y_MM = 6.0, 46.0
INSTRUCTIONS_SIZE_PT, INSTRUCTIONS_LEADING_MM = 6.5, 3.4
# Minimum clearance between printed elements and the measuring zone.
ZONE_CLEARANCE_MM = 3

INSTRUCTIONS: list[tuple[str, bool]] = [
    ("1. Print on A4 at 100 % (“Actual size”). Never use “Fit to page”.", False),
    ("2. Check both rulers: each must measure exactly 100 mm.", False),
    (
        "3. Lay the paper flat. Place the insole diagonally between the grey lines, "
        "heel in the bottom-left corner, toes towards the top-right.",
        False,
    ),
    (
        "4. Photograph from straight above in even light. All 4 black squares must be "
        "visible. No shadows, no flash.",
        False,
    ),
    ("Keep the black squares clean, flat and uncovered.", True),
]


def marker_bits(dictionary: str, marker_id: int, border_bits: int) -> npt.NDArray[np.bool_]:
    """Cell grid of one ArUco marker, True = black, including the black border."""
    aruco_dict = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dictionary))
    cells = aruco_dict.markerSize + 2 * border_bits
    img = cv2.aruco.generateImageMarker(aruco_dict, marker_id, cells, borderBits=border_bits)
    return np.asarray(img < 128)


def _text_box(x: float, y: float, s: str, font: str, size: float, align: str = "left") -> Rect:
    """Box around text drawn with its baseline at y."""
    w = stringWidth(s, font, size) * PT_TO_MM
    left = {"left": x, "right": x - w, "centre": x - w / 2}[align]
    return Rect(left, y - 0.75 * size * PT_TO_MM, w, 0.97 * size * PT_TO_MM)


@dataclass
class _Page:
    c: Canvas
    g: TemplateGeometry
    printed: list[tuple[str, Rect]] = field(default_factory=list)

    def _pt(self, x_mm: float, y_mm: float) -> tuple[float, float]:
        return x_mm * mm, (self.g.page_height_mm - y_mm) * mm

    def _line(self, a: Point, b: Point) -> None:
        self.c.line(*self._pt(*a), *self._pt(*b))

    def _rect(self, r: Rect, fill: Color) -> None:
        # reportlab's rect grows upwards from its bottom-left corner.
        self.c.setFillColor(fill)
        self.c.rect(*self._pt(r.x_mm, r.bottom_mm), r.width_mm * mm, r.height_mm * mm, 0, 1)

    def _text(
        self,
        kind: str,
        x: float,
        y: float,
        s: str,
        *,
        size: float,
        bold: bool = False,
        align: str = "left",
    ) -> Rect:
        font = FONT_BOLD if bold else FONT
        self.c.setFont(font, size)
        self.c.setFillColor(TEXT_GREY)
        draw = {
            "left": self.c.drawString,
            "right": self.c.drawRightString,
            "centre": self.c.drawCentredString,
        }[align]
        draw(*self._pt(x, y), s)
        box = _text_box(x, y, s, font, size, align)
        self.printed.append((kind, box))
        return box

    def marker(self, m: Marker) -> None:
        bits = marker_bits(self.g.aruco_dictionary, m.id, self.g.aruco_border_bits)
        cell = m.size_mm / bits.shape[0]
        self._rect(m.rect, black)
        # White cells, merged into horizontal runs to keep the PDF small.
        for row, line in enumerate(bits):
            col = 0
            while col < len(line):
                if line[col]:
                    col += 1
                    continue
                start = col
                while col < len(line) and not line[col]:
                    col += 1
                run = Rect(m.x_mm + start * cell, m.y_mm + row * cell, (col - start) * cell, cell)
                self._rect(run, white)

    def zone_outline(self) -> None:
        """Dashed lines along the zone's long sides. Sides that follow the paper edge are
        left out: they'd fall into the printer's unprintable margin anyway."""
        self.c.setStrokeColor(GUIDE_GREY)
        self.c.setLineWidth(0.3 * mm)
        self.c.setDash(3 * mm, 2 * mm)
        for a, b in self.g.measuring_zone.edges():
            if a[0] != b[0] and a[1] != b[1]:
                self._line(a, b)
        self.c.setDash()

    def ruler(self, r: Ruler) -> None:
        along = (1.0, 0.0) if r.direction == "horizontal" else (0.0, 1.0)
        tick_dir = {"down": (0, 1), "up": (0, -1), "left": (-1, 0), "right": (1, 0)}[r.tick_side]
        start = (r.x_mm, r.y_mm)
        end = (r.x_mm + along[0] * r.length_mm, r.y_mm + along[1] * r.length_mm)

        def offset(p: Point, d: float) -> Point:
            return (p[0] + tick_dir[0] * d, p[1] + tick_dir[1] * d)

        self.c.setStrokeColor(black)
        self.c.setLineWidth(0.15 * mm)
        self._line(start, end)
        for i in range(int(r.length_mm) + 1):
            p = (start[0] + along[0] * i, start[1] + along[1] * i)
            tick = 4.0 if i % 10 == 0 else 2.5 if i % 5 == 0 else 1.5
            self.c.setLineWidth((0.25 if i % 10 == 0 else 0.12) * mm)
            self._line(p, offset(p, tick))
            if i % 10 == 0:
                lx, ly = offset(p, 5.0)
                if tick_dir[1] != 0:  # ticks go up/down: number centred under the tick
                    ly += 2.0 if tick_dir[1] > 0 else 0.0
                    self._text("ruler", lx, ly, str(i), size=5.5, align="centre")
                else:  # ticks go left/right: number beside the tick, vertically centred
                    align = "right" if tick_dir[0] < 0 else "left"
                    self._text("ruler", lx, ly + 0.7, str(i), size=5.5, align=align)
        lo = (min(start[0], offset(start, 4)[0]), min(start[1], offset(start, 4)[1]))
        hi = (max(end[0], offset(end, 4)[0]), max(end[1], offset(end, 4)[1]))
        self.printed.append(("ruler", Rect(lo[0], lo[1], hi[0] - lo[0], hi[1] - lo[1])))

    def arrow(self, tail: Point, direction: Point, length: float = 8, head: float = 2.2) -> None:
        dx, dy = direction
        tip = (tail[0] + dx * length, tail[1] + dy * length)
        base = (tip[0] - dx * head, tip[1] - dy * head)
        nx, ny = -dy, dx
        self.c.setStrokeColor(TEXT_GREY)
        self.c.setFillColor(TEXT_GREY)
        self.c.setLineWidth(0.4 * mm)
        self._line(tail, base)
        path = self.c.beginPath()
        path.moveTo(*self._pt(*tip))
        path.lineTo(*self._pt(base[0] + nx * head * 0.6, base[1] + ny * head * 0.6))
        path.lineTo(*self._pt(base[0] - nx * head * 0.6, base[1] - ny * head * 0.6))
        path.close()
        self.c.drawPath(path, stroke=0, fill=1)
        xs, ys = [tail[0], tip[0]], [tail[1], tip[1]]
        self.printed.append(
            (
                "label",
                Rect(min(xs) - 1.5, min(ys) - 1.5, max(xs) - min(xs) + 3, max(ys) - min(ys) + 3),
            )
        )

    def orientation_labels(self) -> None:
        """'TOE' and 'HEEL' beside the zone, each with an arrow along the insole axis."""
        (hx, hy), (tx, ty) = self.g.heel_mm, self.g.toe_mm
        length = math.hypot(tx - hx, ty - hy)
        to_toe = ((tx - hx) / length, (ty - hy) / length)
        to_heel = (-to_toe[0], -to_toe[1])
        toe = self._text("label", 96, 17, "TOE", size=9, bold=True)
        self.arrow((toe.right_mm + 2, 15.5), to_toe)
        heel = self._text("label", 90, 284, "HEEL", size=9, bold=True)
        self.arrow((heel.right_mm + 2, 282.5), to_heel)

    def _max_right_at(self, top: float, bottom: float) -> float:
        """Rightmost x a line of text spanning [top, bottom] may reach, left of the zone."""
        spans = [self.g.measuring_zone.x_span_at(y) for y in (top, bottom)]
        lefts = [s[0] for s in spans if s is not None]
        return (min(lefts) if lefts else self.g.page_width_mm) - ZONE_CLEARANCE_MM - 1

    def instructions(self) -> None:
        """Wraps each line to the width left free by the diagonal zone at that height."""
        size = INSTRUCTIONS_SIZE_PT
        x, y = INSTRUCTIONS_X_MM, INSTRUCTIONS_Y_MM
        self._text("text", x, y, f"FitFinder insole template · {self.g.id}", size=8, bold=True)
        y += INSTRUCTIONS_LEADING_MM + 1.5
        for paragraph, bold in INSTRUCTIONS:
            font = FONT_BOLD if bold else FONT
            words = paragraph.split()
            while words:
                box = _text_box(x, y, "", font, size)
                max_w = self._max_right_at(box.y_mm, box.bottom_mm) - x
                line = words.pop(0)
                while words and stringWidth(f"{line} {words[0]}", font, size) * PT_TO_MM <= max_w:
                    line = f"{line} {words.pop(0)}"
                self._text("text", x, y, line, size=size, bold=bold)
                y += INSTRUCTIONS_LEADING_MM
            y += 1.2

    def draw(self) -> None:
        for m in self.g.markers:
            self.marker(m)
        self.zone_outline()
        for r in self.g.rulers:
            self.ruler(r)
        self.orientation_labels()
        self.instructions()


def render(geometry: TemplateGeometry, out: Path) -> list[tuple[str, Rect]]:
    """Writes the PDF to `out` and returns the bounding box of every printed element."""
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas = Canvas(
        str(out),
        pagesize=(geometry.page_width_mm * mm, geometry.page_height_mm * mm),
        pageCompression=1,
        invariant=1,  # reproducible output: same input, byte-identical PDF
    )
    canvas.setTitle(f"FitFinder insole template ({geometry.id})")
    canvas.setAuthor("FitFinder")
    canvas.setSubject("Print on A4 at 100 % (actual size)")
    # Asks PDF viewers to preselect "actual size" in the print dialog instead of "fit".
    canvas.setViewerPreference("PrintScaling", "None")
    page = _Page(canvas, geometry)
    page.draw()
    canvas.showPage()
    canvas.save()
    return page.printed
