import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { requireUser } from "@/lib/auth";

import { DeleteAccountForm } from "./delete-account-form";

export const metadata: Metadata = { title: "Delete account · FitFinder" };

export default function DeleteAccountPage() {
  return (
    <main className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-6 px-6 py-16">
      <h1 className="text-2xl font-semibold tracking-tight">Delete your account</h1>
      <Suspense fallback={<p className="text-zinc-500">Loading…</p>}>
        <DeleteAccount />
      </Suspense>
    </main>
  );
}

async function DeleteAccount() {
  const user = await requireUser("/account/delete");
  return (
    <>
      <div className="flex flex-col gap-2 text-sm">
        <p>
          This permanently deletes the account <strong>{user.email}</strong> right away:
        </p>
        <ul className="list-disc pl-5">
          <li>all insole photos you uploaded, including processed copies,</li>
          <li>your submissions with their measurements and fit results,</li>
          <li>your login.</li>
        </ul>
        <p>
          Shoe models you added to the catalogue stay, but are no longer linked to you. This
          can&apos;t be undone.
        </p>
      </div>
      <DeleteAccountForm />
      <Link href="/account" className="text-sm text-zinc-600 underline dark:text-zinc-400">
        Cancel, keep my account
      </Link>
    </>
  );
}
