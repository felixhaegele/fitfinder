import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from app.pipeline import template as template_module
from app.pipeline.template import geometry_dir, load_template


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    load_template.cache_clear()


def test_reads_the_shared_geometry_from_print() -> None:
    t = load_template()
    assert t.id == "a4-v1"
    assert geometry_dir().parts[-2:] == ("print", "geometry")
    assert sorted(t.marker_corners_mm) == [0, 1, 2, 3]
    # Corners follow OpenCV's order: TL, TR, BR, BL, each marker_size_mm apart.
    c = t.marker_corners_mm[0]
    assert np.allclose(c[1] - c[0], [t.marker_size_mm, 0])
    assert np.allclose(c[3] - c[0], [0, t.marker_size_mm])
    assert t.measuring_zone_mm.shape[1] == 2


def test_env_var_points_at_another_geometry_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = template_module._REPO_GEOMETRY_DIR / "a4-v1.json"
    data = json.loads(source.read_text())
    data["id"] = "a4-v1"
    data["marker_size_mm"] = 25
    (tmp_path / "a4-v1.json").write_text(json.dumps(data))
    monkeypatch.setenv("TEMPLATE_GEOMETRY_DIR", str(tmp_path))

    assert geometry_dir() == tmp_path
    assert load_template().marker_size_mm == 25


def test_missing_template_fails_loudly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shutil.rmtree(tmp_path)
    monkeypatch.setenv("TEMPLATE_GEOMETRY_DIR", str(tmp_path))
    with pytest.raises(FileNotFoundError):
        load_template()
