"""Generate the printable template PDF.

uv run python -m fitfinder_template                    # a4-v1 -> out/fitfinder-template-a4-v1.pdf
uv run python -m fitfinder_template geometry/x.json -o some/where.pdf
"""

import argparse
from pathlib import Path

from fitfinder_template import geometry
from fitfinder_template.render import render

OUT_DIR = Path(__file__).resolve().parent.parent / "out"


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("geometry", nargs="?", type=Path, default=geometry.DEFAULT_TEMPLATE)
    parser.add_argument("-o", "--out", type=Path)
    args = parser.parse_args(argv)

    g = geometry.load(args.geometry)
    out: Path = args.out or OUT_DIR / f"fitfinder-template-{g.id}.pdf"
    render(g, out)
    print(f"wrote {out}")
    return out


if __name__ == "__main__":
    main()
