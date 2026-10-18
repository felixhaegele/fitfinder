import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { StatusBadge } from "@/components/status-badge";
import { requireUser } from "@/lib/auth";
import { SIZE_SYSTEMS, type SizeSystem } from "@/lib/submission-form";
import { listMySubmissions } from "@/lib/submissions";

export const metadata: Metadata = { title: "My uploads · FitFinder" };

export default function SubmissionsPage() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-6 py-16">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">My uploads</h1>
        <Link href="/upload" className="text-sm font-medium">
          Upload another
        </Link>
      </div>
      <Suspense fallback={<p className="text-zinc-500">Loading…</p>}>
        <SubmissionList />
      </Suspense>
    </main>
  );
}

async function SubmissionList() {
  await requireUser("/submissions");
  const submissions = await listMySubmissions();

  if (submissions.length === 0) {
    return (
      <p className="text-zinc-600 dark:text-zinc-400">
        Nothing here yet. <Link href="/upload" className="font-medium underline">Upload your first insole</Link>.
      </p>
    );
  }

  return (
    <ul className="divide-y divide-zinc-200 rounded-lg border border-zinc-200 dark:divide-zinc-800 dark:border-zinc-800">
      {submissions.map((s) => (
        <li key={s.id}>
          <Link
            href={`/submissions/${s.id}`}
            className="flex items-center justify-between gap-4 px-4 py-3 hover:bg-zinc-50 dark:hover:bg-zinc-900"
          >
            <span>
              <span className="font-medium">
                {s.shoe_models?.brand} {s.shoe_models?.model} ({s.shoe_models?.year})
              </span>
              <span className="block text-sm text-zinc-500">
                {SIZE_SYSTEMS[s.size_system as SizeSystem]?.label ?? s.size_system} {s.size} ·{" "}
                {new Date(s.created_at).toLocaleDateString("en-GB", { dateStyle: "medium" })}
              </span>
            </span>
            <StatusBadge status={s.status} />
          </Link>
        </li>
      ))}
    </ul>
  );
}
