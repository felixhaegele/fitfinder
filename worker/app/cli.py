"""Command line tools for the measurement pipeline (#26).

    uv run python -m app.cli measure photo.jpg [--debug overlay.png]

Measures one photo exactly as the worker would, without Supabase: the same validation
(`clean_image`, so EXIF orientation is applied the same way) and the same seam
(`process()` with `measure_and_classify`). Prints the measurements and classes, or the
reason the photo was rejected. `--debug` also writes the photo with markers, contour and
measurement lines drawn on it (`app/overlay.py`).

Exit codes: 0 measured, 2 rejected (a normal outcome, with a reason), 1 error.

Paths are checked before anything is read or written: they must resolve (after `~` and
symlinks) to a location inside `--root`, your home folder by default. The photo must be a
regular JPEG/PNG/WebP file, and at most `MAX_UPLOAD_BYTES` are read, the same limit as
uploads. The overlay must be a `.png`.
"""

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, TextIO

import cv2
import numpy as np

from app.jobs.config import MAX_UPLOAD_BYTES
from app.jobs.process import Analysis, Result, measure_and_classify, process
from app.jobs.validate import InvalidImage, clean_image
from app.overlay import draw_overlay
from app.pipeline.markers import detect_markers
from app.pipeline.rejections import Rejection
from app.pipeline.segment import Segmentation
from app.pipeline.template import load_template
from app.pipeline.warp import Image, PageWarp

EXIT_MEASURED = 0
EXIT_ERROR = 1
EXIT_REJECTED = 2

MEASUREMENT_LABELS = {
    "length_mm": "length",
    "heel_width_mm": "heel width",
    "arch_width_mm": "arch width",
    "ball_width_mm": "ball width",
}
EXTRA_LABELS = {
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


PHOTO_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp"})


class CliError(Exception):
    pass


def resolve_inside(path: Path, root: Path) -> Path:
    """`path` with `~` and symlinks resolved, refused unless it lies inside `root`."""
    base = root.expanduser().resolve()
    resolved = path.expanduser().resolve()
    if not resolved.is_relative_to(base):
        raise CliError(f"{path} is outside {base}; pass --root to allow another folder")
    return resolved


def read_photo(path: Path, root: Path) -> bytes:
    """The photo's bytes, after the path checks in the module docstring."""
    photo = resolve_inside(path, root)
    if photo.suffix.lower() not in PHOTO_SUFFIXES:
        allowed = ", ".join(sorted(PHOTO_SUFFIXES))
        raise CliError(f"couldn't read {path}: expected a photo ({allowed})")
    if not photo.is_file():
        raise CliError(f"couldn't read {path}: not a file")
    try:
        with photo.open("rb") as f:
            # One byte over the limit is enough for clean_image to reject it as too large.
            return f.read(MAX_UPLOAD_BYTES + 1)
    except OSError as e:
        raise CliError(f"couldn't read {path}: {e.strerror or e}") from e


def overlay_path(path: Path, root: Path) -> Path:
    target = resolve_inside(path, root)
    if target.suffix.lower() != ".png":
        raise CliError(f"the debug overlay must be a .png file, got {path}")
    return target


class _Parser(argparse.ArgumentParser):
    # argparse exits with 2 on bad arguments, which here means "rejected".
    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(EXIT_ERROR, f"{self.prog}: error: {message}\n")


@dataclass
class _Capture:
    """The default analyzer, keeping what it was given for the overlay."""

    warp: PageWarp | None = None
    segmentation: Segmentation | None = None

    def __call__(self, warp: PageWarp, segmentation: Segmentation, /) -> Analysis:
        self.warp, self.segmentation = warp, segmentation
        return measure_and_classify(warp, segmentation)


def _print_result(result: Result, out: TextIO) -> None:
    m, c = result.measurement, result.classification
    if m is None:
        print("Measured, but the analyzer returned no measurement.", file=out)
        return
    print(f"Measured: {m.side} insole (pipeline {m.pipeline_version})", file=out)
    for key, label in MEASUREMENT_LABELS.items():
        print(f"  {label:<14}{getattr(m, key):8.1f} mm", file=out)
    for key, value in m.extra.items():
        print(f"  {EXTRA_LABELS.get(key, key):<14}{value:8.1f} mm", file=out)
    if m.toe_taper is not None:
        print(f"  {'toe taper':<14}{m.toe_taper:8.4f}", file=out)
    if c is not None:
        print(f"Classes (classifier {c.classifier_version}):", file=out)
        for key, label in CLASS_LABELS.items():
            print(f"  {label:<14}{getattr(c, key)}", file=out)
    print(f"Markers found: {', '.join(map(str, result.markers_found))}", file=out)


def _print_rejection(code: str, message: str, detail: str, out: TextIO) -> None:
    print(f"Rejected ({code}): {message}", file=out)
    if detail:
        print(f"  detail: {detail}", file=out)


def _write_overlay(path: Path, photo: Image, capture: _Capture) -> None:
    template = capture.warp.template if capture.warp else load_template()
    gray = np.asarray(cv2.cvtColor(photo, cv2.COLOR_BGR2GRAY), np.uint8)
    overlay = draw_overlay(
        photo, detect_markers(gray, template), capture.warp, capture.segmentation
    )
    if not cv2.imwrite(str(path), overlay):
        raise CliError(f"couldn't write the overlay to {path}")


def measure(photo_path: Path, debug: Path | None, out: TextIO, root: Path | None = None) -> int:
    root = Path.home() if root is None else root
    data = read_photo(photo_path, root)
    debug = None if debug is None else overlay_path(debug, root)
    try:
        clean = clean_image(data)
    except InvalidImage as e:
        _print_rejection(str(e.code), e.message, e.detail, out)
        return EXIT_REJECTED

    photo: Image = np.ascontiguousarray(clean.rgb[:, :, ::-1])  # OpenCV expects BGR
    capture = _Capture()
    outcome = process(photo, capture)

    if isinstance(outcome, Rejection):
        _print_rejection(str(outcome.code), outcome.message, outcome.detail, out)
    else:
        _print_result(outcome, out)
    if debug is not None:
        _write_overlay(debug, photo, capture)
        print(f"Debug overlay: {debug}", file=out)
    return EXIT_REJECTED if isinstance(outcome, Rejection) else EXIT_MEASURED


def main(argv: Sequence[str] | None = None, out: TextIO | None = None) -> int:
    parser = _Parser(prog="python -m app.cli", description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    m = commands.add_parser(
        "measure",
        help="measure an insole photo",
        description="Measure and classify an insole photo taken on the A4 template.",
    )
    m.add_argument("photo", type=Path, help="JPEG, PNG or WebP photo")
    m.add_argument("--debug", type=Path, metavar="OUT.png", help="write a debug overlay image")
    m.add_argument(
        "--root",
        type=Path,
        default=Path.home(),
        help="only read and write files inside this folder (default: your home folder)",
    )
    args = parser.parse_args(argv)

    out = out or sys.stdout
    try:
        return measure(args.photo, args.debug, out, args.root)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
