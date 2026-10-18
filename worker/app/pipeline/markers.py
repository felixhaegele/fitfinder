"""Find the template's ArUco markers in a photo."""

import cv2
import numpy as np
import numpy.typing as npt

from app.pipeline.template import FloatArray, Template

GrayImage = npt.NDArray[np.uint8]


def _detector(dictionary: str) -> cv2.aruco.ArucoDetector:
    params = cv2.aruco.DetectorParameters()
    # Sub-pixel corners: the homography is only as accurate as these points.
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    aruco_dict = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dictionary))
    return cv2.aruco.ArucoDetector(aruco_dict, params)


def detect_markers(gray: GrayImage, template: Template) -> dict[int, FloatArray]:
    """Marker id -> its 4 corners in photo pixels (TL, TR, BR, BL as printed), shape (4, 2).

    Only ids that belong to the template are returned. An id seen more than once is
    dropped: we can't tell which copy is on the template.
    """
    corners, ids, _rejected = _detector(template.aruco_dictionary).detectMarkers(gray)
    if ids is None:
        return {}
    found: dict[int, list[FloatArray]] = {}
    for raw_id, c in zip(ids.flatten(), corners, strict=True):
        marker_id = int(raw_id)
        if marker_id in template.marker_corners_mm:
            found.setdefault(marker_id, []).append(np.asarray(c, np.float64).reshape(4, 2))
    return {i: cs[0] for i, cs in found.items() if len(cs) == 1}
