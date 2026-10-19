"""The worker's default analyzer: measure (#23) + classify (#24) -> database rows (#84).

These run in CI (no database needed). They pin down exactly what the inserts receive,
because the `outline_mm` check constraint rejects anything but 256 numeric [x, y] pairs
starting at [0, 0], and psycopg can't serialise numpy values.
"""

import json
import math
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest
from psycopg.types.json import Jsonb

from app.jobs.process import (
    DEFAULT_ANALYZER,
    Result,
    measure_and_classify,
    measurement_row,
    outline_for_db,
    process,
)
from app.jobs.store import classification_params, measurement_params
from app.pipeline import config as pipeline_config
from app.pipeline.measure import InsoleMeasurements
from tests.regression import TOLERANCE_MM, load_fixture, render_fixture

FIXTURES = Path(__file__).parent / "fixtures"


def _outline(n: int = 256) -> np.ndarray:
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    pts = np.column_stack([40 * np.sin(t), 130 * (1 - np.cos(t))])
    pts[0] = [-0.0, 0.0]  # a mirrored left insole's heel point
    return pts


def _measurements(**overrides: object) -> InsoleMeasurements:
    values: dict[str, object] = {
        "side": "left",
        "length_mm": 260.0,
        "heel_width_mm": 62.0,
        "arch_width_mm": 55.0,
        "ball_width_mm": 96.0,
        "toe_width_85_mm": 85.12,
        "toe_width_90_mm": 74.3,
        "toe_width_95_mm": 55.0,
        "outline_mm": _outline(),
    } | overrides
    return InsoleMeasurements(**values)  # type: ignore[arg-type]


def test_default_analyzer_measures_and_classifies() -> None:
    assert DEFAULT_ANALYZER is measure_and_classify


def test_outline_for_db_is_plain_floats_starting_at_positive_zero() -> None:
    outline = outline_for_db(_outline())

    assert len(outline) == 256
    assert all(type(c) is float for point in outline for c in point)
    assert outline[0] == (0.0, 0.0)
    assert math.copysign(1.0, outline[0][0]) == 1.0  # -0.0 became +0.0
    assert json.dumps(outline[0]) == "[0.0, 0.0]"


@pytest.mark.parametrize(
    ("pts", "message"),
    [
        (_outline(255), "must be"),
        (np.vstack([_outline()[:-1], [[np.nan, 1.0]]]), "non-finite"),
        (_outline() + np.array([1.0, 0.0]), "heel point"),
    ],
)
def test_outline_for_db_rejects_what_the_database_would(pts: np.ndarray, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        outline_for_db(pts)


def test_measurement_row_maps_toe_widths_and_taper() -> None:
    row = measurement_row(_measurements())

    assert row.pipeline_version == pipeline_config.PIPELINE_VERSION
    assert row.side == "left"
    assert row.extra == {
        "toe_width_85_mm": 85.12,
        "toe_width_90_mm": 74.3,
        "toe_width_95_mm": 55.0,
    }
    assert row.toe_taper == round(74.3 / 96.0, 4)  # numeric(6, 4)


def test_measurement_row_refuses_a_zero_ball_width() -> None:
    with pytest.raises(ValueError, match="ball width"):
        measurement_row(_measurements(ball_width_mm=0.0))


def test_insert_params_match_column_order_and_types() -> None:
    sid = uuid4()
    row = measurement_row(_measurements())

    params = measurement_params(sid, row)

    assert params[:3] == (sid, row.pipeline_version, "left")
    assert params[3:7] == (260.0, 96.0, 62.0, 55.0)  # length, ball, heel, arch
    outline, taper, extra = params[7], params[8], params[9]
    assert isinstance(outline, Jsonb) and isinstance(extra, Jsonb)
    assert len(outline.obj) == 256 and outline.obj[0] == [0.0, 0.0]
    assert all(isinstance(p, list) and len(p) == 2 for p in outline.obj)
    json.dumps(outline.obj, allow_nan=False)  # no numpy, no NaN
    assert taper == row.toe_taper


@pytest.mark.parametrize("name", ["left_round_straight", "right_round_gradient"])
def test_photo_to_rows_end_to_end(name: str) -> None:
    fixture = load_fixture(FIXTURES / name)

    result = process(render_fixture(fixture).photo.image)

    assert isinstance(result, Result)
    m, c = result.measurement, result.classification
    assert m is not None and c is not None
    assert m.side == fixture.shape.side
    for key in ("length_mm", "heel_width_mm", "arch_width_mm", "ball_width_mm"):
        assert abs(getattr(m, key) - fixture.expected.measurements[key]) <= TOLERANCE_MM[key]
    assert m.outline_mm[0] == (0.0, 0.0)
    for key, label in fixture.expected.classes.items():
        assert getattr(c, key) == label, key
    params = classification_params(1, c)
    assert params[0] == 1 and params[-1] == c.toe_shape
