"""The printed template's geometry, read from print/geometry/<id>.json.

That JSON is the single source of truth (ADR 0004): the PDF is drawn from it, and this
module reads the same file to know where each marker *should* be on the page. Only the
fields the worker needs are loaded; the schema is enforced by print/'s tests.

Where the JSON is found:
- `TEMPLATE_GEOMETRY_DIR` if set (the Docker image sets it to /app/geometry), else
- `print/geometry/` in this repo (local development and tests).
"""

import json
import os
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import numpy as np
import numpy.typing as npt

DEFAULT_TEMPLATE_ID = "a4-v1"
_REPO_GEOMETRY_DIR = Path(__file__).resolve().parents[3] / "print" / "geometry"

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class Template:
    id: str
    page_width_mm: float
    page_height_mm: float
    aruco_dictionary: str
    marker_size_mm: float
    # Marker id -> its 4 corners in mm, in OpenCV ArUco order (TL, TR, BR, BL), shape (4, 2).
    marker_corners_mm: dict[int, FloatArray]
    # Convex polygon the insole must lie inside, shape (n, 2), mm.
    measuring_zone_mm: FloatArray
    heel_mm: tuple[float, float]
    toe_mm: tuple[float, float]


def geometry_dir() -> Path:
    env = os.environ.get("TEMPLATE_GEOMETRY_DIR")
    return Path(env) if env else _REPO_GEOMETRY_DIR


@cache
def load_template(template_id: str = DEFAULT_TEMPLATE_ID) -> Template:
    path = geometry_dir() / f"{template_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    size = float(data["marker_size_mm"])
    corners = {
        int(m["id"]): np.array(
            [
                [m["x_mm"], m["y_mm"]],
                [m["x_mm"] + size, m["y_mm"]],
                [m["x_mm"] + size, m["y_mm"] + size],
                [m["x_mm"], m["y_mm"] + size],
            ],
            dtype=np.float64,
        )
        for m in data["markers"]
    }
    axis = data["insole_axis"]
    return Template(
        id=data["id"],
        page_width_mm=float(data["page"]["width_mm"]),
        page_height_mm=float(data["page"]["height_mm"]),
        aruco_dictionary=data["aruco"]["dictionary"],
        marker_size_mm=size,
        marker_corners_mm=corners,
        measuring_zone_mm=np.array(data["measuring_zone"]["points_mm"], dtype=np.float64),
        heel_mm=(float(axis["heel_mm"][0]), float(axis["heel_mm"][1])),
        toe_mm=(float(axis["toe_mm"][0]), float(axis["toe_mm"][1])),
    )
