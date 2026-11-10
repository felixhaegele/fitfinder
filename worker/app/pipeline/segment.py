"""Flattened page -> the insole's outline, or a reason the photo can't be measured.

The approach and its alternatives are in ADR 0005. In short:

1. Search only inside the template's measuring zone (nothing dark is printed there),
   shrunk a little so the grey dashed guides on its border stay out.
2. Too dark? Check the paper's brightness first.
3. Flatten the lighting: estimate how bright the *paper* would be at every point, and
   divide by it. Light gradients and soft shadows vanish, and the paper becomes ~1.0
   everywhere, so a single threshold works across the whole page.
4. Threshold halfway between the paper and insole levels, clean up specks, keep the
   biggest blob, fill its holes (logos, perforations), and take its outline.
5. Shadow? Look for a stretch of outline that is much softer than the rest: the border
   of a cast shadow that merged with the insole.
6. Too blurry? Estimate how wide the insole's edge is smeared, in mm.
7. Touches the edge? Check whether the blob runs into the border of the search region,
   i.e. it was cut off by the guides, the paper edge or the photo's edge.

Everything here is a pure function on arrays: no files, no network, no database.
"""

import math
from dataclasses import dataclass

import cv2
import numpy as np
import numpy.typing as npt

from app.pipeline import config
from app.pipeline.markers import GrayImage
from app.pipeline.rejections import Rejection, RejectionCode
from app.pipeline.template import FloatArray
from app.pipeline.warp import Image, PageWarp

F32Image = npt.NDArray[np.float32]


@dataclass(frozen=True)
class Segmentation:
    # 255 where the insole is (holes filled), same size as the page image.
    mask: GrayImage
    # Outer outline, (n, 2): page-image pixels and page millimetres.
    contour_px: FloatArray
    contour_mm: FloatArray
    area_mm2: float
    # Raw paper brightness (0-255) and insole contrast against the paper (0-1).
    paper_brightness: float
    contrast: float
    # Estimated edge blur, Gaussian sigma in mm.
    edge_blur_mm: float


def _kernel(size_px: int) -> npt.NDArray[np.uint8]:
    size = max(1, size_px) | 1  # odd
    return np.asarray(cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size)), np.uint8)


def to_gray(page: Image) -> GrayImage:
    if page.ndim == 2:
        return page
    return np.asarray(cv2.cvtColor(page, cv2.COLOR_BGR2GRAY), np.uint8)


def search_region(
    valid: GrayImage, zone_mm: FloatArray, px_per_mm: float, margin_mm: float
) -> GrayImage:
    """255 inside the measuring zone, at least `margin_mm` from its border and from any
    part of the page the photo didn't show."""
    region = np.zeros(valid.shape, np.uint8)
    cv2.fillPoly(region, [np.round(zone_mm * px_per_mm).astype(np.int32)], 255)
    region &= valid
    k = _kernel(2 * round(margin_mm * px_per_mm) + 1)
    return np.asarray(cv2.erode(region, k, borderValue=0), np.uint8)


def paper_background(gray: GrayImage, px_per_mm: float, window_mm: float) -> F32Image:
    """How bright the paper is at every pixel, as if the insole weren't there.

    A grey-level *closing* (max filter, then min filter) with a window wider than the
    insole replaces every dark object by the paper around it, while keeping slow changes
    such as a light gradient. Done at 1 px/mm, because it's fast there and lighting
    doesn't change on a finer scale anyway.
    """
    h, w = gray.shape
    small_size = (max(1, round(w / px_per_mm)), max(1, round(h / px_per_mm)))
    small = cv2.resize(gray, small_size, interpolation=cv2.INTER_AREA)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (round(window_mm) | 1,) * 2)
    closed = cv2.morphologyEx(small, cv2.MORPH_CLOSE, k, borderType=cv2.BORDER_REPLICATE)
    smooth = cv2.GaussianBlur(closed.astype(np.float32), (0, 0), window_mm / 8)
    return np.asarray(cv2.resize(smooth, (w, h), interpolation=cv2.INTER_LINEAR), np.float32)


_PRE_SIGMA_PX = 1.0  # light smoothing so pixel noise doesn't fake steep slopes


def _edge_slopes(flat: F32Image, contour_px: FloatArray) -> FloatArray:
    """The steepest brightness change at each outline point, per pixel."""
    smooth = cv2.GaussianBlur(flat, (0, 0), _PRE_SIGMA_PX)
    gx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0, ksize=3, scale=1 / 8)
    gy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3, scale=1 / 8)
    # The outline sits on the edge's middle, give or take a pixel: take the local max.
    slope = cv2.dilate(cv2.magnitude(gx, gy), _kernel(5))
    pts = np.round(contour_px).astype(int)
    return np.asarray(slope[pts[:, 1], pts[:, 0]], np.float64)


def _blur_from_slope(slope: FloatArray, contrast: float) -> FloatArray:
    with np.errstate(divide="ignore"):
        total = contrast / (slope * math.sqrt(2 * math.pi))
    total = np.where(slope > 0, total, math.inf)
    # Blurs add in quadrature; take back out the smoothing we added ourselves.
    return np.asarray(np.sqrt(np.maximum(total**2 - _PRE_SIGMA_PX**2, 0.0)), np.float64)


def edge_blur_px(flat: F32Image, contour_px: FloatArray, contrast: float) -> float:
    """Gaussian sigma (px) of the insole's edge, from its steepest brightness change.

    A sharp step of height C, blurred with a Gaussian of sigma s, has a steepest slope of
    C / (s * sqrt(2 pi)). So s = C / (slope * sqrt(2 pi)). We take the median slope over
    the whole outline: robust to a few noisy or shadowed spots, and independent of how
    bright the photo is (the flattened image has contrast C in its own units).
    """
    median_slope = np.median(_edge_slopes(flat, contour_px))
    return float(_blur_from_slope(np.array([median_slope]), contrast)[0])


@dataclass(frozen=True)
class EdgeProfile:
    # Outline points on a stretch of edge blurred more than the limit.
    soft_px: int
    # Blur (px) that a quarter of the judged outline is sharper than: the insole's own
    # edge, even when a shadow makes up much of the rest.
    sharp_px: float


def edge_profile(
    flat: F32Image,
    contour_px: FloatArray,
    contrast: float,
    ignore: npt.NDArray[np.bool_],
    window_px: int,
    max_blur_px: float,
) -> EdgeProfile:
    """Find stretches of the outline blurred more than `max_blur_px`.

    A cast shadow that merges with the insole puts the outline on the shadow's border,
    which is soft (a penumbra, several mm), while the insole's own edge is sharp. Unlike
    `edge_blur_px`, this looks at the edge point by point: a shadow covers only part of
    the outline, so the median hides it. Each point's blur is the median over a run of
    `window_px` points, so one noisy spot doesn't count. Points where `ignore` is set
    (the search region's rim, where the outline was cut off) are skipped.
    """
    blur = _blur_from_slope(_edge_slopes(flat, contour_px), contrast)
    half = window_px // 2
    if len(blur) <= window_px:
        runs = np.full(len(blur), np.median(blur))
    else:
        wrapped = np.concatenate([blur[-half:], blur, blur[:half]])
        windows = np.lib.stride_tricks.sliding_window_view(wrapped, 2 * half + 1)
        runs = np.median(windows, axis=1)
    pts = np.round(contour_px).astype(int)
    judged = runs[~ignore[pts[:, 1], pts[:, 0]]]
    if len(judged) == 0:
        return EdgeProfile(soft_px=0, sharp_px=math.inf)
    return EdgeProfile(
        soft_px=int(np.count_nonzero(judged > max_blur_px)),
        sharp_px=float(np.percentile(judged, 25)),
    )


def segment(
    page: Image,
    valid: GrayImage,
    zone_mm: FloatArray,
    px_per_mm: float = config.PX_PER_MM,
) -> Segmentation:
    """Find the insole in a flattened page image. Raises Rejection when the photo can't
    be measured: TOO_DARK, INSOLE_NOT_FOUND, SHADOW, TOO_BLURRY or INSOLE_TOUCHES_EDGE
    (checked in that order, so the user gets the reason that blocks everything after it)."""
    gray = to_gray(page)
    region = search_region(valid, zone_mm, px_per_mm, config.ZONE_MARGIN_MM)
    inside = region > 0
    if inside.sum() < config.MIN_INSOLE_AREA_MM2 * px_per_mm**2:
        raise Rejection(RejectionCode.INSOLE_NOT_FOUND, "measuring zone not in the photo")

    paper_brightness = float(np.percentile(gray[inside], 90))
    if paper_brightness < config.MIN_PAPER_BRIGHTNESS:
        raise Rejection(
            RejectionCode.TOO_DARK,
            f"paper brightness {paper_brightness:.0f} < {config.MIN_PAPER_BRIGHTNESS:.0f}",
        )

    background = paper_background(gray, px_per_mm, config.BACKGROUND_WINDOW_MM)
    flat: F32Image = np.asarray(gray.astype(np.float32) / np.maximum(background, 1.0), np.float32)

    # Otsu finds the split between the two brightness groups (insole, paper). We then
    # put the threshold exactly halfway between their typical levels: on a blurred edge
    # that's where the true edge is, so blur doesn't grow or shrink the insole.
    values = np.clip(flat[inside] * 200, 0, 255).astype(np.uint8)
    otsu, _ = cv2.threshold(values, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    split = otsu / 200
    flat_inside = flat[inside]
    dark, light = flat_inside[flat_inside < split], flat_inside[flat_inside >= split]
    if len(dark) == 0 or len(light) == 0:
        raise Rejection(RejectionCode.INSOLE_NOT_FOUND, "uniform measuring zone")
    insole_level, paper_level = float(np.median(dark)), float(np.median(light))
    contrast = (paper_level - insole_level) / paper_level
    if contrast < config.MIN_INSOLE_CONTRAST:
        raise Rejection(
            RejectionCode.INSOLE_NOT_FOUND,
            f"contrast {contrast:.2f} < {config.MIN_INSOLE_CONTRAST}",
        )
    threshold = (paper_level + insole_level) / 2

    mask = ((flat < threshold) & inside).astype(np.uint8) * 255
    k = _kernel(round(config.CLEANUP_KERNEL_MM * px_per_mm))
    mask = np.asarray(cv2.morphologyEx(mask, cv2.MORPH_OPEN, k), np.uint8)
    mask = np.asarray(cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k), np.uint8)

    # Only the largest blob's outer outline counts; filling it closes logos and holes.
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    largest = max(contours, key=cv2.contourArea, default=np.zeros((0, 1, 2), np.int32))
    filled = np.zeros(mask.shape, np.uint8)
    if len(largest):
        cv2.drawContours(filled, [largest], -1, 255, thickness=cv2.FILLED)
    area_mm2 = float(np.count_nonzero(filled)) / px_per_mm**2
    if area_mm2 < config.MIN_INSOLE_AREA_MM2:
        raise Rejection(
            RejectionCode.INSOLE_NOT_FOUND,
            f"largest dark region {area_mm2:.0f} mm^2 < {config.MIN_INSOLE_AREA_MM2:.0f}",
        )
    contour_px = largest.reshape(-1, 2).astype(np.float64)

    # A shadow along one side can cover half the outline and push the median blur over
    # the limit, so it's checked first, but only while the rest of the edge is in focus:
    # a photo blurred all over is TOO_BLURRY. It also comes before the edge check: a
    # shadow often reaches the guides too, and then it, not the insole's position, is what
    # the user must fix. The outline near the region's border is left out, because where
    # the region cuts the insole off there is no edge at all.
    near_border = np.asarray(cv2.erode(region, _kernel(7), borderValue=0), np.uint8) == 0
    profile = edge_profile(
        flat,
        contour_px,
        paper_level - insole_level,
        near_border,
        round(config.SHADOW_RUN_MM * px_per_mm),
        config.SHADOW_EDGE_BLUR_MM * px_per_mm,
    )
    soft_mm = profile.soft_px / px_per_mm
    if (
        soft_mm >= config.SHADOW_MIN_LENGTH_MM
        and profile.sharp_px / px_per_mm <= config.MAX_EDGE_BLUR_MM
    ):
        raise Rejection(
            RejectionCode.SHADOW,
            f"{soft_mm:.1f} mm of the outline blurred > {config.SHADOW_EDGE_BLUR_MM} mm",
        )

    blur_mm = edge_blur_px(flat, contour_px, paper_level - insole_level) / px_per_mm
    if blur_mm > config.MAX_EDGE_BLUR_MM:
        raise Rejection(
            RejectionCode.TOO_BLURRY,
            f"edge blur {blur_mm:.2f} mm > {config.MAX_EDGE_BLUR_MM} mm",
        )

    # The region's 1 px rim: insole pixels there mean the insole was cut off.
    rim = region & ~np.asarray(cv2.erode(region, _kernel(3), borderValue=0), np.uint8)
    touching_mm = float(np.count_nonzero(filled & rim)) / px_per_mm
    if touching_mm >= config.EDGE_TOUCH_MIN_MM:
        raise Rejection(
            RejectionCode.INSOLE_TOUCHES_EDGE,
            f"{touching_mm:.1f} mm of the outline on the search region's edge",
        )

    return Segmentation(
        mask=filled,
        contour_px=contour_px,
        contour_mm=contour_px / px_per_mm,
        area_mm2=area_mm2,
        paper_brightness=paper_brightness,
        contrast=contrast,
        edge_blur_mm=blur_mm,
    )


def segment_insole(warp: PageWarp) -> Segmentation:
    """`segment` for the output of `warp_to_page`."""
    return segment(warp.page, warp.valid, warp.template.measuring_zone_mm, warp.px_per_mm)
