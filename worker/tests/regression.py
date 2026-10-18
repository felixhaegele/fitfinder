"""Regression fixtures: insole photos with known measurements.

Each fixture is a folder `tests/fixtures/<name>/` with an `expected.json`:

- `description`: one sentence on what the fixture exercises.
- `expected`: what the pipeline must output. Either the measurements (definitions in
  `insoles.py`) or `{"rejection": "<code>"}` for a photo that must be refused.
- `synthetic`: how to draw the photo, namely the insole shape, where it lies on the
  template, and how the camera sees the page (perspective, light, blur, noise, seed).

Images are rendered at test time from `synthetic` (deterministic, fast) instead of being
committed. A real photo can be added later as a fixture with a `photo.jpg` and no
`synthetic` block.

To look at the fixtures: `uv run python -m tests.regression /tmp/fixtures` writes one JPEG
per fixture.
"""

import json
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.pipeline.template import FloatArray, Template, load_template
from tests.insoles import InsoleShape
from tests.synthetic import RENDER_PX_PER_MM, GrayImage, Photo, Shot, photograph, render_page

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# How far a measurement may be from the truth before the regression test fails.
# One EU shoe size is 6.67 mm of length, and fit-relevant width differences start at a
# few mm, so 1 mm keeps every result well below what changes a recommendation. Toe
# widths are looser because they sit where the outline narrows fast: a 1 mm error in the
# length moves the 95 % position by 1 mm, which changes a pointed toe's width there by
# up to ~1.6 mm.
TOLERANCE_MM: dict[str, float] = {
    "length_mm": 1.0,
    "heel_width_mm": 1.0,
    "arch_width_mm": 1.0,
    "ball_width_mm": 1.0,
    "toe_width_85_mm": 1.5,
    "toe_width_90_mm": 2.0,
    "toe_width_95_mm": 2.5,
}
MEASUREMENT_KEYS = tuple(TOLERANCE_MM)

PAPER_WHITE = 255


@dataclass(frozen=True)
class Expected:
    rejection: str | None = None
    measurements: dict[str, float] = field(default_factory=dict)
    toe_box_shape: str | None = None


@dataclass(frozen=True)
class Placement:
    """Where the insole's midpoint lies relative to the page centre, along the template's
    insole axis and across it (mm), and how far it's turned off that axis."""

    along_mm: float = 0.0
    across_mm: float = 0.0
    rotation_deg: float = 0.0


@dataclass(frozen=True)
class Look:
    """How the insole looks on paper. Grey levels are 0-255, before lighting."""

    tone: int = 50
    texture: float = 0.0  # std dev of fabric-like grain
    logo: bool = False  # a light print on the heel, which segmentation must fill in
    shadow: bool = False  # soft shadow along one side, as cast by a lamp


@dataclass(frozen=True)
class Fixture:
    name: str
    description: str
    expected: Expected
    shape: InsoleShape
    look: Look
    placement: Placement
    shot: Shot


def _expected(raw: Mapping[str, Any]) -> Expected:
    if "rejection" in raw:
        return Expected(rejection=str(raw["rejection"]))
    return Expected(
        measurements={k: float(raw[k]) for k in MEASUREMENT_KEYS},
        toe_box_shape=str(raw["toe_box_shape"]),
    )


def load_fixture(path: Path) -> Fixture:
    raw = json.loads((path / "expected.json").read_text(encoding="utf-8"))
    syn = raw["synthetic"]
    ins = dict(syn["insole"])
    look = Look(**{k: ins.pop(k) for k in ("tone", "texture", "logo", "shadow") if k in ins})
    shot = dict(syn["shot"])
    shot["page_corners_px"] = tuple(tuple(map(float, c)) for c in shot["page_corners_px"])
    shot["size"] = tuple(shot["size"])
    return Fixture(
        name=path.name,
        description=raw["description"],
        expected=_expected(raw["expected"]),
        shape=InsoleShape(**ins),
        look=look,
        placement=Placement(**syn.get("placement", {})),
        shot=Shot(**shot),
    )


@cache
def all_fixtures() -> tuple[Fixture, ...]:
    return tuple(load_fixture(p) for p in sorted(FIXTURES_DIR.iterdir()) if p.is_dir())


def measurable_fixtures() -> list[Fixture]:
    return [f for f in all_fixtures() if f.expected.rejection is None]


def rejected_fixtures() -> list[Fixture]:
    return [f for f in all_fixtures() if f.expected.rejection is not None]


@dataclass(frozen=True)
class InsoleFrame:
    """Maps between page mm and the insole frame (heel point at the origin, x to the toe)."""

    heel_mm: FloatArray  # (2,)
    axis: FloatArray  # unit vector heel -> toe, (2,)
    normal: FloatArray  # unit vector of the frame's +y, (2,)

    def to_page(self, pts: FloatArray) -> FloatArray:
        return np.asarray(
            self.heel_mm + pts[:, :1] * self.axis + pts[:, 1:2] * self.normal, np.float64
        )

    def to_frame(self, pts_mm: FloatArray) -> FloatArray:
        d = np.asarray(pts_mm, np.float64) - self.heel_mm
        return np.column_stack([d @ self.axis, d @ self.normal])


def insole_frame(fixture: Fixture, template: Template) -> InsoleFrame:
    (hx, hy), (tx, ty) = template.heel_mm, template.toe_mm
    angle = np.arctan2(ty - hy, tx - hx) + np.deg2rad(fixture.placement.rotation_deg)
    axis = np.array([np.cos(angle), np.sin(angle)])
    # +y of the frame is the right-hand side when walking heel -> toe, seen from above
    # (image coordinates, y down). For a left insole that's the medial side.
    normal = np.array([-axis[1], axis[0]])
    template_axis = np.array([tx - hx, ty - hy]) / np.hypot(tx - hx, ty - hy)
    template_normal = np.array([-template_axis[1], template_axis[0]])
    centre = (
        np.array([template.page_width_mm / 2, template.page_height_mm / 2])
        + fixture.placement.along_mm * template_axis
        + fixture.placement.across_mm * template_normal
    )
    heel = centre - axis * fixture.shape.length_mm / 2
    return InsoleFrame(heel_mm=heel, axis=axis, normal=normal)


@dataclass(frozen=True)
class RenderedFixture:
    fixture: Fixture
    photo: Photo
    frame: InsoleFrame
    # Ground-truth outline on the page, mm, (n, 2).
    outline_mm: FloatArray


def _poly_px(pts_mm: FloatArray, r: int) -> list[np.ndarray]:
    shift = 4  # fillPoly sub-pixel precision: coordinates in 1/16 px
    return [np.round((pts_mm * r - 0.5) * 2**shift).astype(np.int32)]


def _draw_insole(
    page: GrayImage, outline_mm: FloatArray, frame: InsoleFrame, fx: Fixture, r: int
) -> None:
    look, rng = fx.look, np.random.default_rng(fx.shot.seed + 1000)
    mask = np.zeros(page.shape, np.uint8)
    cv2.fillPoly(mask, _poly_px(outline_mm, r), 255, cv2.LINE_AA, 4)
    alpha = mask.astype(np.float64) / 255

    img = page.astype(np.float64)
    if look.shadow:
        # Shifted 1.5 mm, blurred over ~1 mm, 20 % darker at most.
        m = np.array([[1, 0, 1.5 * r], [0, 1, 1.5 * r]], np.float64)
        shadow = cv2.warpAffine(alpha, m, (page.shape[1], page.shape[0]))
        shadow = cv2.GaussianBlur(shadow, (0, 0), 1.0 * r)
        img *= 1 - 0.2 * shadow

    insole = np.full(page.shape, look.tone, np.float64)
    if look.texture:
        grain = rng.normal(0, look.texture, page.shape)
        insole += cv2.GaussianBlur(grain, (0, 0), 0.8)
    if look.logo:
        centre_mm = frame.to_page(np.array([[0.22 * fx.shape.length_mm, 0.0]]))[0]
        centre = tuple(int(v) for v in np.round(centre_mm * r - 0.5))
        angle = float(np.degrees(np.arctan2(frame.axis[1], frame.axis[0])))
        cv2.ellipse(insole, centre, (18 * r, 10 * r), angle, 0, 360, min(look.tone + 110, 230), -1)
    img = img * (1 - alpha) + insole * alpha
    page[:] = np.clip(img, 0, 255).astype(np.uint8)


def render_fixture(fixture: Fixture, template: Template | None = None) -> RenderedFixture:
    template = template or load_template()
    r = RENDER_PX_PER_MM
    frame = insole_frame(fixture, template)
    outline_mm = frame.to_page(fixture.shape.outline())
    page = render_page(template, rect=False, guides=True, r=r)
    _draw_insole(page, outline_mm, frame, fixture, r)
    return RenderedFixture(
        fixture=fixture,
        photo=photograph(page, template, fixture.shot, r=r),
        frame=frame,
        outline_mm=outline_mm,
    )


def assert_measurements_match(
    measured: Mapping[str, float | str],
    expected: Expected,
    keys: Iterable[str] = MEASUREMENT_KEYS,
) -> None:
    """Fail with every out-of-tolerance value listed, not only the first."""
    problems = []
    for key in keys:
        want = expected.measurements[key]
        got = measured.get(key)
        if not isinstance(got, float | int):
            problems.append(f"{key}: missing (expected {want:.1f})")
        elif abs(got - want) > TOLERANCE_MM[key]:
            problems.append(
                f"{key}: {got:.2f} mm, expected {want:.1f} ± {TOLERANCE_MM[key]} mm "
                f"(off by {got - want:+.2f})"
            )
    if "toe_box_shape" in measured and measured["toe_box_shape"] != expected.toe_box_shape:
        problems.append(
            f"toe_box_shape: {measured['toe_box_shape']!r}, expected {expected.toe_box_shape!r}"
        )
    if problems:
        raise AssertionError("measurements out of tolerance:\n  " + "\n  ".join(problems))


def main(out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for fx in all_fixtures():
        cv2.imwrite(str(out / f"{fx.name}.jpg"), render_fixture(fx).photo.image)
        print(out / f"{fx.name}.jpg")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "fixture-images")
