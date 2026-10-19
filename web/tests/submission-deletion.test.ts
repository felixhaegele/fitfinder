import { afterEach, describe, expect, it, vi } from "vitest";

import {
  deleteSubmission,
  processedCopyPath,
  type SubmissionFiles,
  type SubmissionRows,
  submissionFilePaths,
} from "@/lib/submission-deletion";

const USER = "00000000-0000-0000-0000-00000000000a";
const OTHER = "00000000-0000-0000-0000-00000000000b";
const SUB = "11111111-1111-1111-1111-111111111111";
const ORIGINAL = `${USER}/${SUB}.jpg`;
const PROCESSED = `${USER}/processed/${SUB}.jpg`;

/** A tiny in-memory world: storage files, one submission row, and a log of every call. */
function fakeWorld(opts: {
  files: string[];
  row: SubmissionFiles | null;
  failRemove?: "first" | "second";
  failDelete?: boolean;
  /** Plays the worker: runs between the first file removal and the row delete. */
  beforeRowDelete?: (world: { files: Set<string>; row: SubmissionFiles | null }) => void;
}) {
  const world = { files: new Set(opts.files), row: opts.row };
  const log: string[] = [];
  let removeCalls = 0;

  const bucket = {
    async remove(paths: string[]) {
      removeCalls += 1;
      log.push(`remove ${paths.join(",")}`);
      const fail =
        (opts.failRemove === "first" && removeCalls === 1) ||
        (opts.failRemove === "second" && removeCalls === 2);
      if (fail) return { data: null, error: { message: "remove broke" } };
      // Like Supabase: paths that don't exist are silently skipped.
      for (const p of paths) world.files.delete(p);
      return { data: [], error: null };
    },
  };
  const rows: SubmissionRows = {
    async get(id) {
      log.push(`get ${id}`);
      return world.row;
    },
    async delete(id) {
      opts.beforeRowDelete?.(world);
      log.push(`delete ${id}`);
      if (opts.failDelete) throw new Error("delete broke");
      const row = world.row;
      world.row = null;
      return row;
    },
  };
  return { world, log, deps: { bucket, rows } };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("submissionFilePaths", () => {
  it("lists the original, the recorded processed copy and the conventional path, once each", () => {
    expect(
      submissionFilePaths({ image_path: ORIGINAL, processed_image_path: PROCESSED }, USER, SUB),
    ).toEqual([ORIGINAL, PROCESSED]);
  });

  it("includes the conventional processed path even before the worker recorded it", () => {
    expect(
      submissionFilePaths({ image_path: ORIGINAL, processed_image_path: null }, USER, SUB),
    ).toEqual([ORIGINAL, processedCopyPath(USER, SUB)]);
  });

  it("refuses paths outside the user's folder", () => {
    expect(() =>
      submissionFilePaths({ image_path: `${OTHER}/x.jpg`, processed_image_path: null }, USER, SUB),
    ).toThrow(/outside the user's folder/);
  });
});

describe("deleteSubmission", () => {
  it("removes both photos, then the row", async () => {
    const { world, log, deps } = fakeWorld({
      files: [ORIGINAL, PROCESSED, `${USER}/other.jpg`],
      row: { image_path: ORIGINAL, processed_image_path: PROCESSED },
    });

    await expect(deleteSubmission(deps, USER, SUB)).resolves.toBe(true);

    expect([...world.files]).toEqual([`${USER}/other.jpg`]);
    expect(world.row).toBeNull();
    // Files first, then the row, then the final cleanup.
    expect(log).toEqual([
      `get ${SUB}`,
      `remove ${ORIGINAL},${PROCESSED}`,
      `delete ${SUB}`,
      `remove ${ORIGINAL},${PROCESSED}`,
    ]);
  });

  it("returns false and touches nothing when there is no such submission", async () => {
    const { log, deps } = fakeWorld({ files: [ORIGINAL], row: null });

    await expect(deleteSubmission(deps, USER, SUB)).resolves.toBe(false);
    expect(log).toEqual([`get ${SUB}`]);
  });

  it("keeps the row when removing the files fails, so the user can retry", async () => {
    const { world, deps } = fakeWorld({
      files: [ORIGINAL, PROCESSED],
      row: { image_path: ORIGINAL, processed_image_path: PROCESSED },
      failRemove: "first",
    });

    await expect(deleteSubmission(deps, USER, SUB)).rejects.toThrow("remove broke");
    expect(world.row).not.toBeNull();
    expect(world.files.size).toBe(2);
  });

  it("can be retried after the row delete failed", async () => {
    const row = { image_path: ORIGINAL, processed_image_path: PROCESSED };
    const first = fakeWorld({ files: [ORIGINAL, PROCESSED], row, failDelete: true });
    await expect(deleteSubmission(first.deps, USER, SUB)).rejects.toThrow("delete broke");
    expect(first.world.files.size).toBe(0);
    expect(first.world.row).not.toBeNull();

    // Second attempt: the files are already gone, which is fine.
    const retry = fakeWorld({ files: [], row: first.world.row });
    await expect(deleteSubmission(retry.deps, USER, SUB)).resolves.toBe(true);
    expect(retry.world.row).toBeNull();
  });

  it("removes a processed copy the worker finished while we were deleting", async () => {
    const elsewhere = `${USER}/processed/late.jpg`;
    const { world, deps } = fakeWorld({
      files: [ORIGINAL],
      row: { image_path: ORIGINAL, processed_image_path: null },
      beforeRowDelete: (w) => {
        w.files.add(elsewhere);
        w.row = { image_path: ORIGINAL, processed_image_path: elsewhere };
      },
    });

    await expect(deleteSubmission(deps, USER, SUB)).resolves.toBe(true);
    expect([...world.files]).toEqual([]);
  });

  it("only logs when the final cleanup fails: the submission is already gone", async () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    const { world, deps } = fakeWorld({
      files: [ORIGINAL, PROCESSED],
      row: { image_path: ORIGINAL, processed_image_path: PROCESSED },
      failRemove: "second",
    });

    await expect(deleteSubmission(deps, USER, SUB)).resolves.toBe(true);
    expect(world.row).toBeNull();
    expect(error).toHaveBeenCalledWith(
      expect.stringContaining("final file cleanup failed"),
      expect.any(Error),
    );
  });

  it.each([
    ["user", "not-a-uuid", SUB],
    ["submission", USER, ""],
  ])("rejects an invalid %s id before touching anything", async (_what, userId, subId) => {
    const { log, deps } = fakeWorld({ files: [ORIGINAL], row: null });
    await expect(deleteSubmission(deps, userId, subId)).rejects.toThrow("invalid id");
    expect(log).toEqual([]);
  });
});
