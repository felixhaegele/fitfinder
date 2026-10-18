"""Photo -> flat, top-down image of the template page at a fixed px/mm.

A homography is the 3x3 matrix that maps points on one plane to another as seen through
a (pinhole) camera. The paper is a plane and we know where its markers are in mm, so
matching detected marker corners to their known positions gives the homography from photo
pixels to page millimetres. Warping with it undoes perspective, tilt and rotation; after
that, distances in the page image are plain px / PX_PER_MM.

Pixel convention of the page image: pixel (x, y) is centred on the point
(x / px_per_mm, y / px_per_mm) mm of the page (origin top-left, y down, like the JSON).
"""

from dataclasses import dataclass

import cv2
import numpy as np
import numpy.typing as npt

from app.pipeline import config
from app.pipeline.markers import GrayImage, detect_markers
from app.pipeline.rejections import Rejection, RejectionCode
from app.pipeline.template import FloatArray, Template, load_template

Image = npt.NDArray[np.uint8]


@dataclass(frozen=True)
class PageWarp:
    template: Template
    px_per_mm: float
    # The page seen from straight above, same channels as the input photo.
    page: Image
    # 255 where the page image shows part of the photo, 0 where the photo didn't reach
    # (e.g. a page corner outside the frame). Segmentation must not trust 0 areas.
    valid: GrayImage
    # Photo pixels -> page-image pixels.
    homography: FloatArray
    markers_found: list[int]
    # Largest distance (mm) between a detected marker corner and the homography's fit.
    marker_fit_error_mm: float

    def photo_to_mm(self, points_px: FloatArray) -> FloatArray:
        """Photo pixel coordinates (n, 2) -> page millimetres (n, 2)."""
        return _apply(self.homography, points_px) / self.px_per_mm

    def mm_to_photo(self, points_mm: FloatArray) -> FloatArray:
        """Page millimetres (n, 2) -> photo pixel coordinates (n, 2). For debug overlays."""
        return _apply(np.linalg.inv(self.homography), points_mm * self.px_per_mm)


def _apply(h: FloatArray, points: FloatArray) -> FloatArray:
    pts = np.asarray(points, np.float64).reshape(-1, 1, 2)
    return np.asarray(cv2.perspectiveTransform(pts, h), np.float64).reshape(-1, 2)


def _to_gray(photo: Image) -> GrayImage:
    if photo.ndim == 2:
        return photo
    return np.asarray(cv2.cvtColor(photo, cv2.COLOR_BGR2GRAY), np.uint8)


def warp_to_page(
    photo: Image,
    template: Template | None = None,
    px_per_mm: float = config.PX_PER_MM,
) -> PageWarp:
    """Find the markers in `photo` (BGR or grayscale) and return the flattened page.

    Raises Rejection(MARKERS_NOT_FOUND) if fewer than MIN_MARKERS markers are found and
    Rejection(PAPER_NOT_FLAT) if the markers don't lie on one plane.
    """
    template = template or load_template()
    found = detect_markers(_to_gray(photo), template)
    if len(found) < config.MIN_MARKERS:
        raise Rejection(
            RejectionCode.MARKERS_NOT_FOUND,
            f"found markers {sorted(found)}, need {config.MIN_MARKERS} of "
            f"{sorted(template.marker_corners_mm)}",
        )

    ids = sorted(found)
    src = np.concatenate([found[i] for i in ids])
    dst = np.concatenate([template.marker_corners_mm[i] for i in ids]) * px_per_mm
    # Plain least squares over all corners: with at most 16 points that all come from
    # verified markers, there are no outliers for RANSAC to remove. A bad corner shows up
    # in the fit error below instead.
    h_raw, _ = cv2.findHomography(src, dst, method=0)
    if h_raw is None:
        raise Rejection(RejectionCode.MARKERS_NOT_FOUND, "degenerate marker positions")
    h: FloatArray = np.asarray(h_raw, np.float64)

    fit_error_mm = float(np.linalg.norm(_apply(h, src) - dst, axis=1).max() / px_per_mm)
    if fit_error_mm > config.MAX_MARKER_FIT_ERROR_MM:
        raise Rejection(
            RejectionCode.PAPER_NOT_FLAT,
            f"marker fit error {fit_error_mm:.2f} mm > {config.MAX_MARKER_FIT_ERROR_MM} mm",
        )

    size = (
        round(template.page_width_mm * px_per_mm),
        round(template.page_height_mm * px_per_mm),
    )
    page = cv2.warpPerspective(
        photo, h, size, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0
    )
    valid = cv2.warpPerspective(
        np.full(photo.shape[:2], 255, np.uint8),
        h,
        size,
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    return PageWarp(
        template=template,
        px_per_mm=px_per_mm,
        page=np.asarray(page, np.uint8),
        valid=np.asarray(valid, np.uint8),
        homography=h,
        markers_found=ids,
        marker_fit_error_mm=fit_error_mm,
    )
