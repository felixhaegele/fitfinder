"use client";

import { useActionState, useState } from "react";

import { type DeleteSubmissionState, deleteMySubmission } from "./actions";

/** Two steps: first reveal the confirmation, then delete. */
export function DeleteSubmissionForm({ submissionId }: { submissionId: string }) {
  const [confirming, setConfirming] = useState(false);
  const [state, formAction, pending] = useActionState<DeleteSubmissionState, FormData>(
    deleteMySubmission,
    null,
  );

  if (!confirming) {
    return (
      <button
        type="button"
        onClick={() => setConfirming(true)}
        className="self-start text-sm font-medium text-red-600 underline"
      >
        Delete this upload…
      </button>
    );
  }

  return (
    <form action={formAction} className="flex flex-col gap-3 rounded-lg border border-red-200 p-4 dark:border-red-900">
      <input type="hidden" name="submissionId" value={submissionId} />
      <p className="text-sm">
        This permanently deletes both photos (your upload and the cleaned copy) and the
        measurements for this upload.
      </p>
      {state?.error && (
        <p role="alert" className="text-sm text-red-600">
          {state.error}
        </p>
      )}
      <div className="flex gap-3">
        <button
          type="submit"
          disabled={pending}
          className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
        >
          {pending ? "Deleting…" : "Delete upload"}
        </button>
        <button
          type="button"
          onClick={() => setConfirming(false)}
          disabled={pending}
          className="px-4 py-2 text-sm font-medium"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
