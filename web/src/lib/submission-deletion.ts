// Deleting one submission and both of its photos (#82). Pure logic with the Supabase calls
// passed in, like account-deletion.ts, so it can be unit-tested without Supabase. The
// server action wires in the user's own client (src/app/submissions/[id]/actions.ts).

import type { BucketClient } from "@/lib/account-deletion";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** The storage paths a submission row points at. */
export type SubmissionFiles = { image_path: string; processed_image_path: string | null };

/** The slice of the submissions table this module uses. Both return null for no row. */
export type SubmissionRows = {
  get(id: string): Promise<SubmissionFiles | null>;
  /** Deletes the row and returns it as it was at that moment. */
  delete(id: string): Promise<SubmissionFiles | null>;
};

/** Where the worker writes the clean copy (convention from the processed_image_path migration). */
export function processedCopyPath(userId: string, submissionId: string): string {
  return `${userId}/processed/${submissionId}.jpg`;
}

/**
 * Every file that belongs to the submission: the original, the processed copy the row
 * points at, and the conventional processed path (in case the worker uploaded the copy
 * but hasn't recorded it in the row yet). Only paths inside the user's own folder.
 */
export function submissionFilePaths(
  row: SubmissionFiles,
  userId: string,
  submissionId: string,
): string[] {
  const paths = [row.image_path, row.processed_image_path, processedCopyPath(userId, submissionId)];
  const unique = [...new Set(paths.filter((p): p is string => Boolean(p)))];
  for (const path of unique) {
    // The database already enforces this; checked again so a bad row can never make us
    // delete someone else's file.
    if (!path.startsWith(`${userId}/`)) {
      throw new Error(`Refusing to delete ${path}: outside the user's folder`);
    }
  }
  return unique;
}

async function removeFiles(bucket: Pick<BucketClient, "remove">, paths: string[]): Promise<void> {
  // Removing a path that doesn't exist isn't an error, which makes retries safe.
  const { error } = await bucket.remove(paths);
  if (error) {
    throw new Error(`Removing files failed: ${error.message}`);
  }
}

/**
 * Deletes one of the user's submissions, in this order (same idea as ADR 0006):
 *
 * 1. Remove its files: the original upload and the processed copy. First, so that if
 *    anything fails, no file is left behind without a row pointing at it.
 * 2. Delete the row. Measurements and classifications cascade.
 * 3. Remove the files again, for a processed copy the worker finished between 1 and 2.
 *    (If the worker finishes after 2, it finds no row and removes its copy itself.)
 *
 * Steps 1 and 2 are idempotent: if one fails, this throws and the user can try again.
 * Step 3 runs after the submission is already gone, so a failure is only logged.
 *
 * Returns false if the user has no submission with this id.
 */
export async function deleteSubmission(
  deps: { bucket: Pick<BucketClient, "remove">; rows: SubmissionRows },
  userId: string,
  submissionId: string,
): Promise<boolean> {
  if (!UUID.test(userId) || !UUID.test(submissionId)) {
    throw new Error("Refusing to delete: invalid id");
  }

  const row = await deps.rows.get(submissionId);
  if (!row) {
    return false;
  }
  const before = submissionFilePaths(row, userId, submissionId);
  await removeFiles(deps.bucket, before);

  const deleted = await deps.rows.delete(submissionId);

  try {
    const after = deleted ? submissionFilePaths(deleted, userId, submissionId) : before;
    await removeFiles(deps.bucket, [...new Set([...before, ...after])]);
  } catch (err) {
    console.error(`Submission ${submissionId} deleted, but the final file cleanup failed:`, err);
  }
  return true;
}
