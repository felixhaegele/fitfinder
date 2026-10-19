"use client";

import { useActionState } from "react";

import { CONFIRMATION_WORD } from "@/lib/account-deletion";

import { type DeleteAccountState, deleteMyAccount } from "./actions";

export function DeleteAccountForm() {
  const [state, formAction, pending] = useActionState<DeleteAccountState, FormData>(
    deleteMyAccount,
    null,
  );

  return (
    <form action={formAction} className="flex flex-col gap-4">
      <label className="flex flex-col gap-1 text-sm font-medium">
        <span>
          Type <strong className="font-mono">{CONFIRMATION_WORD}</strong> to confirm
        </span>
        <input
          type="text"
          name="confirm"
          required
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
          className="rounded-md border border-zinc-300 px-3 py-2 font-mono text-base font-normal dark:border-zinc-700 dark:bg-zinc-900"
        />
      </label>
      {state?.error && (
        <p role="alert" className="text-sm text-red-600">
          {state.error}
        </p>
      )}
      <button
        type="submit"
        disabled={pending}
        className="rounded-md bg-red-600 px-4 py-2 font-medium text-white hover:bg-red-700 disabled:opacity-50"
      >
        {pending ? "Deleting…" : "Delete my account"}
      </button>
    </form>
  );
}
