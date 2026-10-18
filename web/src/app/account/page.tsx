import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { requireUser } from "@/lib/auth";

export const metadata: Metadata = { title: "Account · FitFinder" };

export default function AccountPage() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-6 py-16">
      <h1 className="text-2xl font-semibold tracking-tight">Your account</h1>
      <Suspense fallback={<p className="text-zinc-500">Loading…</p>}>
        <AccountDetails />
      </Suspense>
      <section className="mt-8 flex flex-col gap-2 rounded-lg border border-red-200 p-4 dark:border-red-900">
        <h2 className="font-semibold text-red-700 dark:text-red-400">Delete account</h2>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Permanently delete your account, your submissions and all your photos.
        </p>
        <Link href="/account/delete" className="self-start text-sm font-medium text-red-700 underline dark:text-red-400">
          Delete my account…
        </Link>
      </section>
    </main>
  );
}

async function AccountDetails() {
  const user = await requireUser("/account");
  return (
    <p>
      Logged in as <strong>{user.email}</strong>
    </p>
  );
}
