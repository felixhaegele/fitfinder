"""`python -m app.cli measure` (#26), run against the synthetic regression fixtures."""

import io
import re
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.cli import EXIT_ERROR, EXIT_MEASURED, EXIT_REJECTED, main, read_photo
from app.jobs.config import MAX_UPLOAD_BYTES
from app.jobs.validate import MESSAGES as IMAGE_MESSAGES
from app.jobs.validate import ImageRejectionCode
from app.overlay import draw_overlay
from app.pipeline.markers import detect_markers
from app.pipeline.rejections import MESSAGES, RejectionCode
from app.pipeline.warp import warp_to_page
from tests.regression import TOLERANCE_MM, RenderedFixture
from tests.test_process import jpeg

WORKER_DIR = Path(__file__).parent.parent
LABELS = {
    "length_mm": "length",
    "heel_width_mm": "heel width",
    "arch_width_mm": "arch width",
    "ball_width_mm": "ball width",
    "toe_width_85_mm": "toe at 85 %",
    "toe_width_90_mm": "toe at 90 %",
    "toe_width_95_mm": "toe at 95 %",
}
CLASS_LABELS = {
    "width_class": "width",
    "arch_class": "arch",
    "toe_box_shape": "toe box",
    "toe_shape": "toe shape",
}


def run(*args: str | Path, root: Path = Path("/")) -> tuple[int, str]:
    # pytest's tmp_path isn't under the home folder (the CLI's default --root), so these
    # tests widen the root. The root check itself is tested below.
    out = io.StringIO()
    code = main([*(str(a) for a in args), "--root", str(root)], out=out)
    return code, out.getvalue()


def photo_file(tmp_path: Path, rendered: RenderedFixture) -> Path:
    path = tmp_path / f"{rendered.fixture.name}.jpg"
    path.write_bytes(jpeg(rendered.photo.image))
    return path


def printed_mm(output: str, label: str) -> float:
    match = re.search(rf"^  {re.escape(label)} +([\d.]+) mm$", output, re.MULTILINE)
    assert match, f"{label!r} not in output:\n{output}"
    return float(match.group(1))


def printed_class(output: str, label: str) -> str:
    match = re.search(rf"^  {re.escape(label)} +(\w+)$", output, re.MULTILINE)
    assert match, f"{label!r} not in output:\n{output}"
    return match.group(1)


def test_measure_prints_measurements_and_classes(
    tmp_path: Path, measurable: RenderedFixture
) -> None:
    code, output = run("measure", photo_file(tmp_path, measurable))

    assert code == EXIT_MEASURED
    expected = measurable.fixture.expected
    assert f"Measured: {measurable.fixture.shape.side} insole" in output
    for key, label in LABELS.items():
        # Printed to 0.1 mm, so allow for the rounding on top of the tolerance.
        assert abs(printed_mm(output, label) - expected.measurements[key]) <= (
            TOLERANCE_MM[key] + 0.05
        ), key
    for key, label in CLASS_LABELS.items():
        assert printed_class(output, label) == expected.classes[key], key


def test_measure_writes_a_debug_overlay(tmp_path: Path, measurable: RenderedFixture) -> None:
    overlay_path = tmp_path / "overlay.png"
    photo_path = photo_file(tmp_path, measurable)

    code, output = run("measure", photo_path, "--debug", overlay_path)

    assert code == EXIT_MEASURED
    assert f"Debug overlay: {overlay_path}" in output
    overlay = cv2.imread(str(overlay_path))
    photo = cv2.imread(str(photo_path))
    assert overlay is not None
    assert photo is not None
    assert overlay.shape == photo.shape
    # Drawn on the photo: the lines change some pixels, but most stay as they were.
    changed = np.any(np.abs(overlay.astype(np.int16) - photo.astype(np.int16)) > 40, axis=2)
    assert 0.001 < changed.mean() < 0.2


def test_measure_reports_rejections_with_the_users_reason(
    tmp_path: Path, rejected: RenderedFixture
) -> None:
    overlay_path = tmp_path / "overlay.png"

    code, output = run("measure", photo_file(tmp_path, rejected), "--debug", overlay_path)

    assert code == EXIT_REJECTED
    assert rejected.fixture.expected.rejection is not None
    reason = RejectionCode(rejected.fixture.expected.rejection)
    assert output.startswith(f"Rejected ({reason}): {MESSAGES[reason]}")
    assert overlay_path.exists()  # shows how far the pipeline got, e.g. which markers


def test_measure_rejects_a_file_that_isnt_a_photo(tmp_path: Path) -> None:
    path = tmp_path / "photo.jpg"
    path.write_text("<html>not a photo</html>")

    code, output = run("measure", path)

    assert code == EXIT_REJECTED
    code_name = ImageRejectionCode.UNSUPPORTED_IMAGE
    assert output.startswith(f"Rejected ({code_name}): {IMAGE_MESSAGES[code_name]}")


def test_measure_missing_file_is_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, output = run("measure", tmp_path / "missing.jpg")

    assert code == EXIT_ERROR
    assert output == ""
    assert "couldn't read" in capsys.readouterr().err


def test_unwritable_overlay_is_an_error(tmp_path: Path, measurable: RenderedFixture) -> None:
    code, _ = run(
        "measure", photo_file(tmp_path, measurable), "--debug", tmp_path / "no-dir" / "o.png"
    )

    assert code == EXIT_ERROR


def test_photo_outside_root_is_refused(
    tmp_path: Path, measurable: RenderedFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "allowed"
    root.mkdir()

    code, output = run("measure", photo_file(tmp_path, measurable), root=root)

    assert code == EXIT_ERROR
    assert output == ""
    assert "is outside" in capsys.readouterr().err


def test_symlink_escaping_root_is_refused(tmp_path: Path, measurable: RenderedFixture) -> None:
    root = tmp_path / "allowed"
    root.mkdir()
    (root / "link.jpg").symlink_to(photo_file(tmp_path, measurable))

    code, _ = run("measure", root / "link.jpg", root=root)

    assert code == EXIT_ERROR


@pytest.mark.parametrize("name", ["notes.txt", "photo.jpg/"])
def test_non_photo_paths_are_refused(tmp_path: Path, name: str) -> None:
    (tmp_path / "photo.jpg").mkdir()  # a directory with a photo-like name
    (tmp_path / "notes.txt").write_text("hi")

    code, _ = run("measure", tmp_path / name)

    assert code == EXIT_ERROR


def test_overlay_must_be_png_inside_root(tmp_path: Path, measurable: RenderedFixture) -> None:
    photo = photo_file(tmp_path, measurable)

    assert run("measure", photo, "--debug", tmp_path / "o.jpg")[0] == EXIT_ERROR
    root = tmp_path / "allowed"
    root.mkdir()
    (root / "p.jpg").write_bytes(photo.read_bytes())
    assert run("measure", root / "p.jpg", "--debug", tmp_path / "o.png", root=root)[0] == (
        EXIT_ERROR
    )


def test_read_photo_reads_at_most_one_byte_over_the_upload_limit(tmp_path: Path) -> None:
    big = tmp_path / "big.jpg"
    big.write_bytes(b"\0" * (MAX_UPLOAD_BYTES + 1000))

    assert len(read_photo(big, tmp_path)) == MAX_UPLOAD_BYTES + 1


@pytest.mark.parametrize("args", [[], ["measure"], ["measure", "a.jpg", "--nope"]])
def test_bad_arguments_exit_1_not_2(args: list[str]) -> None:
    # 2 means "rejected"; argparse's default 2 for usage errors would be ambiguous.
    with pytest.raises(SystemExit) as excinfo:
        main(args)
    assert excinfo.value.code == EXIT_ERROR


def test_runs_as_a_module() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "measure", "--help"],
        cwd=WORKER_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--debug" in result.stdout


def test_overlay_marks_template_markers_that_werent_found(measurable: RenderedFixture) -> None:
    photo = measurable.photo.image
    warp = warp_to_page(photo)
    gray = np.asarray(cv2.cvtColor(photo, cv2.COLOR_BGR2GRAY), np.uint8)
    found = detect_markers(gray, warp.template)
    assert 0 in found

    def red_pixels(image: np.ndarray) -> int:
        return int(((image[:, :, 2] > 200) & (image[:, :, 1] < 80)).sum())

    with_all = draw_overlay(photo, found, warp)
    without_0 = draw_overlay(photo, {i: c for i, c in found.items() if i != 0}, warp)

    # Marker 0 is outlined in red where the homography expects it, instead of green.
    assert red_pixels(with_all) == 0
    assert red_pixels(without_0) > 100
