import { afterEach, describe, expect, it, vi } from "vitest";

import {
  type AuthAdminClient,
  type BucketClient,
  deleteAccount,
  isConfirmed,
  listAllFiles,
  purgeUserFiles,
} from "@/lib/account-deletion";

const USER = "00000000-0000-0000-0000-00000000000a";

/** In-memory stand-in for a Storage bucket that lists one folder level at a time. */
function fakeBucket(initial: string[], failOn?: "list" | "remove") {
  const files = new Set(initial);
  const calls: string[] = [];
  const bucket: BucketClient = {
    async list(folder, { limit, offset }) {
      calls.push(`list ${folder} ${offset}`);
      if (failOn === "list") return { data: null, error: { message: "list broke" } };
      const entries = new Map<string, string | null>();
      for (const path of [...files].sort()) {
        if (!path.startsWith(`${folder}/`)) continue;
        const [name, ...rest] = path.slice(folder.length + 1).split("/");
        entries.set(name, rest.length ? null : `id-${path}`);
      }
      const page = [...entries].slice(offset, offset + limit).map(([name, id]) => ({ name, id }));
      return { data: page, error: null };
    },
    async remove(paths) {
      calls.push(`remove ${paths.length}`);
      if (failOn === "remove") return { data: null, error: { message: "remove broke" } };
      for (const p of paths) files.delete(p);
      return { data: [], error: null };
    },
  };
  return { bucket, files, calls };
}

function fakeAuthAdmin(error: { message: string } | null = null, log?: string[]) {
  const authAdmin: AuthAdminClient = {
    deleteUser: vi.fn(async (id: string) => {
      log?.push(`deleteUser ${id}`);
      return { error };
    }),
  };
  return authAdmin;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("isConfirmed", () => {
  it.each(["DELETE", " DELETE "])("accepts %j", (value) => {
    expect(isConfirmed(value)).toBe(true);
  });

  it.each([["delete"], ["DELET"], [""], [null]])("rejects %j", (value) => {
    expect(isConfirmed(value)).toBe(false);
  });
});

describe("listAllFiles", () => {
  it("finds files in subfolders", async () => {
    const { bucket } = fakeBucket([`${USER}/a.jpg`, `${USER}/processed/s1.jpg`, `other/x.jpg`]);
    expect((await listAllFiles(bucket, USER)).sort()).toEqual([
      `${USER}/a.jpg`,
      `${USER}/processed/s1.jpg`,
    ]);
  });

  it("pages through large folders", async () => {
    const paths = Array.from({ length: 250 }, (_, i) => `${USER}/${String(i).padStart(3, "0")}.jpg`);
    const { bucket, calls } = fakeBucket(paths);
    expect(await listAllFiles(bucket, USER)).toHaveLength(250);
    expect(calls).toEqual([`list ${USER} 0`, `list ${USER} 100`, `list ${USER} 200`]);
  });

  it("throws when listing fails", async () => {
    const { bucket } = fakeBucket([], "list");
    await expect(listAllFiles(bucket, USER)).rejects.toThrow("list broke");
  });
});

describe("purgeUserFiles", () => {
  it("removes only that user's files, in batches", async () => {
    const mine = Array.from({ length: 150 }, (_, i) => `${USER}/${i}.jpg`);
    const { bucket, files, calls } = fakeBucket([...mine, `${USER}/processed/p.jpg`, "other/x.jpg"]);
    expect(await purgeUserFiles(bucket, USER)).toBe(151);
    expect([...files]).toEqual(["other/x.jpg"]);
    expect(calls.filter((c) => c.startsWith("remove"))).toEqual(["remove 100", "remove 51"]);
  });

  it("does nothing when there are no files", async () => {
    const { bucket, calls } = fakeBucket([]);
    expect(await purgeUserFiles(bucket, USER)).toBe(0);
    expect(calls.some((c) => c.startsWith("remove"))).toBe(false);
  });

  it.each(["", "..", "abc", `${USER}/x`])("refuses a malformed user id %j", async (id) => {
    const { bucket, calls } = fakeBucket(["other/x.jpg"]);
    await expect(purgeUserFiles(bucket, id)).rejects.toThrow("invalid user id");
    expect(calls).toEqual([]);
  });

  it("throws when removing fails", async () => {
    const { bucket } = fakeBucket([`${USER}/a.jpg`], "remove");
    await expect(purgeUserFiles(bucket, USER)).rejects.toThrow("remove broke");
  });
});

describe("deleteAccount", () => {
  it("purges files, deletes the user, then purges again", async () => {
    const { bucket, files, calls } = fakeBucket([`${USER}/a.jpg`]);
    const authAdmin = fakeAuthAdmin(null, calls);
    await deleteAccount({ bucket, authAdmin }, USER);
    expect(files.size).toBe(0);
    expect(calls).toEqual([
      `list ${USER} 0`,
      "remove 1",
      `deleteUser ${USER}`,
      `list ${USER} 0`,
    ]);
  });

  it("keeps the user when the file purge fails, so they can retry", async () => {
    const { bucket } = fakeBucket([`${USER}/a.jpg`], "remove");
    const authAdmin = fakeAuthAdmin();
    await expect(deleteAccount({ bucket, authAdmin }, USER)).rejects.toThrow("remove broke");
    expect(authAdmin.deleteUser).not.toHaveBeenCalled();
  });

  it("throws when deleting the user fails", async () => {
    const { bucket } = fakeBucket([]);
    const authAdmin = fakeAuthAdmin({ message: "auth down" });
    await expect(deleteAccount({ bucket, authAdmin }, USER)).rejects.toThrow("auth down");
  });

  it("only logs a failed final purge, because the account is already gone", async () => {
    const { bucket } = fakeBucket([]);
    const authAdmin = fakeAuthAdmin();
    // The first purge succeeds; the second one fails.
    let lists = 0;
    const flaky: BucketClient = {
      ...bucket,
      list: (folder, options) =>
        ++lists === 1
          ? bucket.list(folder, options)
          : Promise.resolve({ data: null, error: { message: "list broke" } }),
    };
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    await expect(deleteAccount({ bucket: flaky, authAdmin }, USER)).resolves.toBeUndefined();
    expect(authAdmin.deleteUser).toHaveBeenCalledWith(USER);
    expect(consoleError).toHaveBeenCalledOnce();
  });
});
