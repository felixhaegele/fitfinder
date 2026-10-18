"""Synthetic template photos with a known ground truth.

`render_page` draws the template (markers + a dark test rectangle) from the geometry
JSON; `photograph` views it through a known perspective with blur, noise and lighting.
Because we know the exact mm -> photo mapping, tests can check the pipeline's result
point by point. Insole-shaped fixtures built on top of this live in `insoles.py` and
`regression.py` (#25).
"""

from dataclasses import dataclass

import cv2
import numpy as np
import numpy.typing as npt

from app.pipeline.template import FloatArray, Template

GrayImage = npt.NDArray[np.uint8]

RENDER_PX_PER_MM = 8
# Test rectangle placed along the insole axis, like a (very boxy) insole.
RECT_LENGTH_MM, RECT_WIDTH_MM = 220.0, 80.0
# The printed zone guides: light grey (0.72 in print/fitfinder_template/render.py),
# 0.3 mm wide, dashed 3 mm on / 2 mm off.
GUIDE_GREY, GUIDE_WIDTH_MM, GUIDE_DASH_MM = 184, 0.3, (3.0, 2.0)


def _mm_to_render(r: float) -> FloatArray:
    # Render pixel i covers [i, i+1) / r mm, so its centre (OpenCV's coordinate for
    # pixel i) is at (i + 0.5) / r mm.
    return np.array([[r, 0, -0.5], [0, r, -0.5], [0, 0, 1]], np.float64)


def rect_corners_mm(template: Template) -> FloatArray:
    (hx, hy), (tx, ty) = template.heel_mm, template.toe_mm
    axis = np.array([tx - hx, ty - hy]) / np.hypot(tx - hx, ty - hy)
    normal = np.array([-axis[1], axis[0]])
    centre = np.array([template.page_width_mm / 2, template.page_height_mm / 2])
    a, b = axis * RECT_LENGTH_MM / 2, normal * RECT_WIDTH_MM / 2
    return np.array([centre - a - b, centre + a - b, centre + a + b, centre - a + b])


def render_page(
    template: Template,
    *,
    covered: tuple[int, ...] = (),
    shifted_mm: dict[int, tuple[int, int]] | None = None,
    rect: bool = True,
    guides: bool = False,
    r: int = RENDER_PX_PER_MM,
) -> GrayImage:
    """The printed page as a grayscale image at r px/mm. `covered` markers are left out;
    `shifted_mm` moves markers by whole mm, as if the paper were folded there. `guides`
    draws the grey dashed lines along the measuring zone, as on the real PDF."""
    shifted_mm = shifted_mm or {}
    page = np.full(
        (round(template.page_height_mm * r), round(template.page_width_mm * r)), 255, np.uint8
    )
    aruco_dict = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, template.aruco_dictionary))
    side = round(template.marker_size_mm * r)
    for marker_id, corners in template.marker_corners_mm.items():
        if marker_id in covered:
            continue
        dx, dy = shifted_mm.get(marker_id, (0, 0))
        x, y = round((corners[0][0] + dx) * r), round((corners[0][1] + dy) * r)
        page[y : y + side, x : x + side] = cv2.aruco.generateImageMarker(
            aruco_dict, marker_id, side, borderBits=1
        )
    if guides:
        _draw_guides(page, template, r)
    if rect:
        pts = cv2.perspectiveTransform(
            rect_corners_mm(template).reshape(-1, 1, 2), _mm_to_render(r)
        ).reshape(-1, 2)
        shift = 4  # sub-pixel precision for fillPoly: coordinates in 1/16 px
        cv2.fillPoly(page, [np.round(pts * 2**shift).astype(np.int32)], 60, cv2.LINE_AA, shift)
    return page


def _draw_guides(page: GrayImage, template: Template, r: int) -> None:
    """Dashed lines along the zone's slanted sides; the PDF leaves out sides that follow
    the paper edge."""
    zone = template.measuring_zone_mm
    on, off = GUIDE_DASH_MM
    thickness = max(1, round(GUIDE_WIDTH_MM * r))
    for a, b in zip(zone, np.roll(zone, -1, axis=0), strict=True):
        if a[0] == b[0] or a[1] == b[1]:
            continue
        length = float(np.hypot(*(b - a)))
        unit = (b - a) / length
        for start in np.arange(0.0, length, on + off):
            p, q = a + unit * start, a + unit * min(start + on, length)
            p_px, q_px = (np.round(p * r - 0.5).astype(int), np.round(q * r - 0.5).astype(int))
            cv2.line(page, tuple(p_px), tuple(q_px), GUIDE_GREY, thickness, cv2.LINE_AA)


@dataclass(frozen=True)
class Shot:
    """How the page appears in the photo: where its 4 corners land (TL, TR, BR, BL as
    printed), plus image degradations."""

    page_corners_px: tuple[tuple[float, float], ...]
    size: tuple[int, int] = (3000, 4000)  # width, height
    brightness: float = 1.0
    blur_sigma: float = 0.0
    noise_sigma: float = 0.0
    seed: int = 0
    # Uneven light: brightness falls linearly by this fraction across the photo, from
    # the side `light_angle_deg` points away from (0 = light from the left).
    light_gradient: float = 0.0
    light_angle_deg: float = 0.0


@dataclass(frozen=True)
class Photo:
    image: npt.NDArray[np.uint8]  # BGR
    mm_to_photo: FloatArray  # exact ground-truth homography

    def project(self, points_mm: FloatArray) -> FloatArray:
        pts = np.asarray(points_mm, np.float64).reshape(-1, 1, 2)
        return np.asarray(cv2.perspectiveTransform(pts, self.mm_to_photo), np.float64).reshape(
            -1, 2
        )


def photograph(page: GrayImage, template: Template, shot: Shot, r: int = RENDER_PX_PER_MM) -> Photo:
    w, h = template.page_width_mm, template.page_height_mm
    page_mm = np.array([[0, 0], [w, 0], [w, h], [0, h]], np.float64)
    m = _mm_to_render(r)
    page_render = cv2.perspectiveTransform(page_mm.reshape(-1, 1, 2), m).reshape(-1, 2)
    render_to_photo = cv2.getPerspectiveTransform(
        page_render.astype(np.float32), np.array(shot.page_corners_px, np.float32)
    )
    table_grey = 90
    img = np.asarray(
        cv2.warpPerspective(
            page,
            render_to_photo,
            shot.size,
            flags=cv2.INTER_AREA,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=table_grey,
        ),
        np.float32,
    )
    rng = np.random.default_rng(shot.seed)
    img = img * np.float32(shot.brightness)
    if shot.light_gradient:
        img *= _light_falloff(shot)
    if shot.blur_sigma:
        img = np.asarray(cv2.GaussianBlur(img, (0, 0), shot.blur_sigma), np.float32)
    if shot.noise_sigma:
        img += rng.normal(0, shot.noise_sigma, img.shape).astype(np.float32)
    gray = np.clip(img, 0, 255).astype(np.uint8)
    return Photo(
        image=np.asarray(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR), np.uint8),
        mm_to_photo=np.asarray(render_to_photo, np.float64) @ m,
    )


def _light_falloff(shot: Shot) -> npt.NDArray[np.float32]:
    w, h = shot.size
    angle = np.deg2rad(shot.light_angle_deg)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    proj = xs * np.float32(np.cos(angle)) + ys * np.float32(np.sin(angle))
    u = (proj - proj.min()) / (proj.max() - proj.min())
    return np.asarray(1 - np.float32(shot.light_gradient) * u, np.float32)


# Page corners in the photo, in printed order TL, TR, BR, BL.
STRAIGHT = ((300, 303), (2700, 303), (2700, 3697), (300, 3697))
TILTED = ((520, 480), (2520, 430), (2860, 3720), (140, 3640))
ROTATED_180 = (STRAIGHT[2], STRAIGHT[3], STRAIGHT[0], STRAIGHT[1])

SHOTS: dict[str, Shot] = {
    "straight": Shot(STRAIGHT),
    "tilted": Shot(TILTED),
    "rotated_180": Shot(ROTATED_180),
    # Landscape photo, phone turned: page rotated 90 degrees clockwise.
    "rotated_90": Shot(((3697, 300), (3697, 2700), (303, 2700), (303, 300)), size=(4000, 3000)),
    "dim_blurry_noisy": Shot(TILTED, brightness=0.45, blur_sigma=2.0, noise_sigma=8.0, seed=1),
    # Lower-resolution phone (about 5 px/mm on the page).
    "low_res": Shot(((80, 75), (1130, 60), (1180, 1540), (40, 1500)), size=(1200, 1600)),
}
