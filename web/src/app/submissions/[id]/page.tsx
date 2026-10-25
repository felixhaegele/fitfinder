import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { StatusBadge } from "@/components/status-badge";
import { requireUser } from "@/lib/auth";
import { INSOLE_CONDITIONS, type InsoleCondition, SIZE_SYSTEMS, type SizeSystem } from "@/lib/submission-form";
import {
  classificationRows,
  formatMm,
  isInProgress,
  statusCopy,
  TOE_LABELS_NOTE,
} from "@/lib/submission-status";
import { getMySubmission } from "@/lib/submissions";

import { AutoRefresh } from "./auto-refresh";
import { DeleteSubmissionForm } from "./delete-submission-form";

export const metadata: Metadata = { title: "Upload · FitFinder" };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default function SubmissionPage({ params }: PageProps<"/submissions/[id]">) {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-8 px-6 py-16">
      <Link href="/submissions" className="text-sm text-zinc-600 dark:text-zinc-400">
        ← My uploads
      </Link>
      <Suspense fallback={<p className="text-zinc-500">Loading…</p>}>
        <SubmissionDetails params={params} />
      </Suspense>
    </main>
  );
}

async function SubmissionDetails({ params }: { params: PageProps<"/submissions/[id]">["params"] }) {
  const { id } = await params;
  await requireUser(`/submissions/${id}`);
  // Not a uuid → can't exist; skip the query (Postgres would error on the cast).
  const submission = UUID.test(id) ? await getMySubmission(id) : null;
  if (!submission) {
    notFound();
  }

  const copy = statusCopy(submission.status);
  const shoe = submission.shoe_models;
  const sizeLabel = SIZE_SYSTEMS[submission.size_system as SizeSystem]?.label ?? submission.size_system;

  return (
    <>
      {isInProgress(submission.status) && <AutoRefresh />}

      <section className="flex flex-col gap-2">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">
            {shoe?.brand} {shoe?.model} ({shoe?.year})
          </h1>
          <StatusBadge status={submission.status} />
        </div>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          {sizeLabel} {submission.size} ·{" "}
          {INSOLE_CONDITIONS[submission.insole_condition as InsoleCondition] ?? submission.insole_condition} ·
          uploaded {new Date(submission.created_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}
        </p>
      </section>

      <section role="status" aria-live="polite" className="flex flex-col gap-2">
        <p>{copy.description}</p>
        {submission.status === "rejected" && submission.rejection_reason && (
          <p className="font-medium">Reason: {submission.rejection_reason}</p>
        )}
        {(submission.status === "rejected" || submission.status === "failed") && (
          <Link href="/upload" className="font-medium underline">
            Upload a new photo
          </Link>
        )}
      </section>

      {submission.status === "done" && submission.measurement && (
        <section className="grid gap-6 sm:grid-cols-2">
          <div>
            <h2 className="mb-2 font-semibold">Measurements</h2>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
              <dt>Length</dt>
              <dd>{formatMm(submission.measurement.length_mm)}</dd>
              <dt>Ball width</dt>
              <dd>{formatMm(submission.measurement.ball_width_mm)}</dd>
              <dt>Arch width</dt>
              <dd>{formatMm(submission.measurement.arch_width_mm)}</dd>
              <dt>Heel width</dt>
              <dd>{formatMm(submission.measurement.heel_width_mm)}</dd>
            </dl>
          </div>
          {submission.classification && (
            <div>
              <h2 className="mb-2 font-semibold">Foot shape</h2>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                {classificationRows(submission.classification).map((row) => (
                  <div key={row.label} className="contents">
                    <dt>{row.label}</dt>
                    <dd>{row.value}</dd>
                  </div>
                ))}
              </dl>
              <p className="mt-2 text-xs text-zinc-500">{TOE_LABELS_NOTE}</p>
            </div>
          )}
        </section>
      )}

      {/* Both photos are kept: the upload as sent, and the worker's server-side clean copy. */}
      <section className="grid gap-6 sm:grid-cols-2">
        <Photo title="Your upload" url={submission.originalUrl} alt="The photo you uploaded" />
        <Photo
          title="Cleaned copy"
          url={submission.processedUrl}
          alt="The photo as re-encoded by FitFinder's server"
          missing="Created when your photo is measured."
        />
      </section>

      <DeleteSubmissionForm submissionId={submission.id} />
    </>
  );
}

function Photo({
  title,
  url,
  alt,
  missing = "Not available.",
}: {
  title: string;
  url: string | null;
  alt: string;
  missing?: string;
}) {
  return (
    <figure className="flex flex-col gap-2">
      <figcaption className="text-sm font-medium">{title}</figcaption>
      {url ? (
        // Signed, short-lived URLs from the private bucket; next/image would cache them.
        // eslint-disable-next-line @next/next/no-img-element
        <img src={url} alt={alt} className="w-full rounded-lg border border-zinc-200 dark:border-zinc-800" />
      ) : (
        <p className="flex aspect-[3/4] items-center justify-center rounded-lg border border-dashed border-zinc-300 p-4 text-center text-sm text-zinc-500 dark:border-zinc-700">
          {missing}
        </p>
      )}
    </figure>
  );
}
