import type { Metadata } from "next";
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
