import type { Metadata } from "next";
import { Suspense } from "react";

import { requireUser } from "@/lib/auth";

export const metadata: Metadata = { title: "Account · FitFinder" };

export default function AccountPage({ searchParams }: PageProps<"/account">) {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-6 py-16">
      <h1 className="text-2xl font-semibold tracking-tight">Your account</h1>
      <Suspense fallback={<p className="text-zinc-500">Loading…</p>}>
        <AccountDetails searchParams={searchParams} />
      </Suspense>
    </main>
  );
}

async function AccountDetails({
  searchParams,
}: {
  searchParams: PageProps<"/account">["searchParams"];
}) {
  const user = await requireUser("/account");
  const { submitted } = await searchParams;
  return (
    <>
      {/* Until the status page exists (#30), confirm the upload here. */}
      {submitted === "1" && (
        <p role="status" className="rounded-lg border border-green-200 bg-green-50 p-4 text-sm dark:border-green-900 dark:bg-green-950">
          Thanks! Your photo is queued for measuring. That usually takes a minute or two.
        </p>
      )}
      <p>
        Logged in as <strong>{user.email}</strong>
      </p>
    </>
  );
}
