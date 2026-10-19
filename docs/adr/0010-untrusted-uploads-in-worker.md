# 0010. Validate and measure uploads in a time-limited child process, behind one pipeline seam

- **Status:** Accepted
- **Date:** 2026-10-18

## Context

The worker (#29) downloads photos that users put into Storage. The browser re-encodes them first (#28), but anyone can call the Storage API with their own token, so the worker gets **untrusted bytes**. The security requirements agreed in #29 ask for these checks:

- the real file type from the magic bytes,
- a pixel cap before decoding (decompression bombs),
- a time limit per job,
- a server-side re-encode without metadata. The UI shows it next to the original upload; both stay in the private bucket and are only ever served to their owner via short-lived signed URLs (owner decision 2026-10-19, amending requirement 4 on #29).

Two forces shape how to build this:

1. **Time limits in Python are weak.** Decoding (Pillow) and measuring (OpenCV) run inside C code. A timer signal or a watchdog thread can't interrupt a C call, so a file that makes a decoder spin would hang the whole Cloud Run Job run, and every message behind it would wait.
2. **The pipeline is being built in parallel** (#23 measurements, #24 classifier, #52 outline/toe shape). The worker must not depend on their internals, or every pipeline change would touch the worker too.

## Decision

We will run **validation and the pipeline in a fresh child process per job** (`multiprocessing` with `spawn`). The parent waits up to 60 s and kills the child after that. A timeout, a crash or an exception in the child counts as one failed attempt under ADR 0003's retry rules.

The child does, in order (`app/jobs/validate.py`):

1. Check the byte size (≤ 10 MiB) and the magic bytes (JPEG, PNG, WebP).
2. Open the file with Pillow, restricted to the format the magic bytes claim, and read only the header. Over 50 MP is rejected before any pixel is decoded. `OPENCV_IO_MAX_IMAGE_PIXELS` backs this up inside OpenCV.
3. Decode the first frame, apply the EXIF orientation, convert to RGB, and build a **new image from the bare pixels**. That image is saved as JPEG, so no EXIF, GPS, ICC profile or comment can survive. (Re-saving the decoded image directly turned out to carry a JPEG comment along.)
4. Call the pipeline through **one function**: `process(image) -> Result | Rejection` (`app/jobs/process.py`). Measuring and classifying plug in as an `Analyzer`. Until #23/#24 merge, it returns no rows.

Validation failures are **rejections** with a user-facing reason (`unsupported_image`, `image_too_large`, `image_unreadable`, `image_missing`), like pipeline rejections. They're defined in the worker, not in `app/pipeline/rejections.py`, because they're about files, not about measuring.

The parent process does the I/O: it downloads (streamed, cut off at 10 MiB), uploads the clean copy and writes the database.

## Alternatives considered

- **`signal.alarm` / a thread with a timeout:** no extra process, but can't stop a running C call, so it doesn't actually enforce the limit.
- **A long-lived process pool:** saves the ~1 s start-up per job, but a hung task can't be killed on its own, only the whole pool. At our volume (a few jobs per minute at most), 1 s per job doesn't matter.
- **Rely on the browser's re-encode:** it's skipped by anyone calling the API directly, so it's a convenience, not a control.
- **A separate sandbox (gVisor, a second container, seccomp):** a real security boundary against decoder exploits. That's more than v1 needs. Cloud Run already runs containers in gVisor, the container runs as non-root, and Dependabot keeps Pillow and OpenCV current.

## Consequences

- A hostile or broken photo costs at most 60 s and one attempt. It can't block the queue.
- The child is **not a security boundary**: it runs as the same user with the same environment, secrets included. If decoder exploits ever become a real worry, the next step is to drop secrets from the child's environment or move decoding into its own container.
- Each job pays ~1 s to start the child (importing OpenCV). That's fine for a batch job; revisit if volume grows a lot.
- Wiring in #23/#24 means changing `DEFAULT_ANALYZER` in `process.py` and, for new columns (#52), adding fields to the row types and the insert in `store.py`. The worker's flow doesn't change.
- `Analyzer` functions must be module-level functions, because they're sent to the child process by name (pickling).
