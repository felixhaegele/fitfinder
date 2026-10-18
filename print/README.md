# print

Generates the printable A4 template that users put their insole on before taking a photo. The measurement worker uses it to find the page and convert pixels to millimetres.

```
 ┌────────────────────────────┐
 │ [0]     [1]   TOE ↗  ╱     │   [n]   ArUco marker (DICT_4X4_50, 20 mm)
 │ ├┼┼┼ 100 mm ┼┼┤     ╱      │   ╱ ╱   measuring zone: 120 mm band along the diagonal
 │ instructions      ╱      ╱ │
 │                 ╱  insole╱  │   Heel towards the bottom-left,
 │               ╱       ╱   ┤ │   toes towards the top-right.
 │             ╱       ╱  100┤ │
 │           ╱       ╱     mm┤ │
 │  ╱      ╱  HEEL ↙   [3]  [2]│
 └────────────────────────────┘
```

Why diagonal, and why the geometry lives in JSON: [ADR 0004](../docs/adr/0004-diagonal-a4-template.md).

## Generate

```sh
cd print
uv sync
uv run python -m fitfinder_template        # → out/fitfinder-template-a4-v1.pdf (gitignored)
```

The output is reproducible: the same geometry always gives a byte-identical PDF.

## How it fits together

- **`geometry/a4-v1.json`** is the single source of truth: page size, marker IDs and positions, measuring-zone polygon, heel-to-toe axis and rulers. All values are in mm, origin top-left, y down (like image pixels). It's validated by `geometry/template.schema.json`. The worker will read the same file to know where the markers *should* be.
- **`fitfinder_template/render.py`** draws the PDF with reportlab. Markers are drawn as vector squares, not embedded images, so their edges are sharp on any printer. OpenCV is used only to look up each marker's bit pattern.
- **Never edit the geometry of a published template.** Add `a4-v2.json` instead. Old photos were taken on the old layout.

## Tests

```sh
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
```

- The geometry matches the schema, marker IDs are unique, and markers have their white quiet zone and don't touch the measuring zone.
- Nothing printed (text, rulers, labels) comes within 3 mm of the measuring zone.
- The PDF is rasterised at 300 dpi and OpenCV must find all 4 markers within 0.3 mm of the JSON positions. This is the same detection the worker will do.

## Printing tips (also on the sheet)

Print at **100 % / "Actual size"**, never "Fit to page". Check both rulers with a real ruler. The PDF asks viewers to default to actual size (`PrintScaling=None`), but not every viewer honours that.
