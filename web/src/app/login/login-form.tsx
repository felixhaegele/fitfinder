"use client";

import { useActionState } from "react";

import { type LoginState, sendMagicLink } from "@/app/auth/actions";

const initialState: LoginState = { status: "idle" };

export function LoginForm({ next, linkError }: { next: string; linkError: boolean }) {
  const [state, formAction, pending] = useActionState(sendMagicLink, initialState);

  if (state.status === "sent") {
    return (
      <div role="status" className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
        <p className="font-medium">Check your inbox</p>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          We sent a login link to <strong>{state.email}</strong>. You can open it on any device,
          e.g. on your phone.
        </p>
      </div>
    );
  }

  return (
    <form action={formAction} className="flex flex-col gap-4">
      {linkError && (
        <p role="alert" className="text-sm text-red-600">
          That login link is invalid or has expired. Request a new one below.
        </p>
      )}
      <input type="hidden" name="next" value={next} />
      <label className="flex flex-col gap-1 text-sm font-medium">
        Email
        <input
          type="email"
          name="email"
          required
          autoComplete="email"
          className="rounded-md border border-zinc-300 px-3 py-2 text-base font-normal dark:border-zinc-700 dark:bg-zinc-900"
        />
      </label>
      {state.status === "error" && (
        <p role="alert" className="text-sm text-red-600">
          {state.message}
        </p>
      )}
      <button
        type="submit"
        disabled={pending}
        className="rounded-md bg-zinc-900 px-4 py-2 font-medium text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
      >
        {pending ? "Sending…" : "Send me a login link"}
      </button>
    </form>
  );
}
