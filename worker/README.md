# worker

Python 3.12 measurement worker: FastAPI + OpenCV, dependencies managed with [uv](https://docs.astral.sh/uv/), tests with pytest.
It consumes jobs from the Supabase `submissions` queue, measures the insole photo and writes results to Postgres.

## Measurement pipeline (`app/pipeline/`)

Built step by step in Milestone 5 (#20). Each step is a pure function: photo in, result out, no database.

1. **Markers → flat page** (`warp.py`, #21). The pipeline finds the template's ArUco markers and computes a *homography*: the 3×3 matrix that maps points on one flat surface to how a camera sees them. Because the paper is flat and the markers' mm positions are known, it maps photo pixels to page millimetres. Warping with it gives a top-down image of the page at a fixed **10 px/mm**, so later steps measure in plain pixels ÷ 10.
   - Marker positions come from **`print/geometry/a4-v1.json`**, the same file the printable PDF is drawn from (ADR 0004).
   - Pixel `(x, y)` of the page image is centred on `(x/10, y/10)` mm.
   - A photo is rejected with a user-facing message when fewer than 3 markers are found (`markers_not_found`), or when the markers don't fit one flat page, e.g. curled paper (`paper_not_flat`).
2. Segmentation (#22), measurements and outline (#23), classification (#24): coming next.

All tunable numbers live in `app/pipeline/config.py`. Rejection codes and their user-facing messages live in `app/pipeline/rejections.py`.

Tests use **synthetic photos** (`tests/synthetic.py`). They draw the template from the JSON, then view it through a known perspective with tilt, rotation, blur, noise and dim light. The exact answer is known, so every point on the page can be checked. Realistic insole fixtures follow in #25.

## Develop

```sh
cd worker
uv sync                               # creates .venv (downloads Python 3.12 if needed)
uv run fastapi dev app/main.py        # http://127.0.0.1:8000/health, auto-reload
```

## Check (same as CI)

```sh
uv run ruff check .                   # lint
uv run ruff format --check .          # formatting (drop --check to fix)
uv run mypy                           # strict type checking
uv run pytest                         # tests + coverage (coverage.xml)
```

## Container

```sh
docker build --build-context geometry=../print/geometry -t fitfinder-worker .
docker run --rm -p 8080:8080 fitfinder-worker
curl localhost:8080/health
```

**Why `--build-context`?** Docker can only see files inside the build context, which is `worker/`. The template geometry lives in `print/geometry/`. A *named build context* hands Docker that one extra folder under the name `geometry`, and the Dockerfile copies it with `COPY --from=geometry`. The JSON stays a single file, and the rest of the repo (`web/`, …) isn't sent to Docker. If you forget the flag, the build fails with a "pull access denied" error for `geometry`: Docker then treats the name as an image to download. In the container, `TEMPLATE_GEOMETRY_DIR=/app/geometry` tells the code where the file is. Locally, it finds `../print/geometry` by itself.

The Dockerfile is **multi-stage**. The first stage installs dependencies with uv, and the second copies only the resulting virtualenv and the code into a clean slim image. The final image has no uv or build caches, and it runs as an unprivileged `app` user. Cloud Run supplies `$PORT`, which defaults to 8080.
