import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { FIT_FILTERS, fitLabel, fitLabelRows, insoleCount } from "@/lib/shoe-fit";
import { getShoe } from "@/lib/shoes";
import { SIZE_SYSTEMS, type SizeSystem } from "@/lib/submission-form";
import { CLASS_LABELS, formatMm, TOE_LABELS_NOTE } from "@/lib/submission-status";

export const metadata: Metadata = { title: "Shoe fit · FitFinder" };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default function ShoePage({ params }: PageProps<"/shoes/[id]">) {
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-8 px-6 py-16">
      <Link href="/shoes" className="text-sm text-zinc-600 dark:text-zinc-400">
        ← All shoes
      </Link>
      <Suspense fallback={<p className="text-zinc-500">Loading…</p>}>
        <ShoeDetails params={params} />
      </Suspense>
    </main>
  );
}

async function ShoeDetails({ params }: { params: PageProps<"/shoes/[id]">["params"] }) {
  const { id } = await params;
  // Not a uuid → can't exist; skip the query (Postgres would error on the cast).
  const shoe = UUID.test(id) ? await getShoe(id) : null;
  if (!shoe) {
    notFound();
  }

  const { summary, sizes } = shoe;

  return (
    <>
      <section className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">
          {shoe.brand} {shoe.model} ({shoe.year})
        </h1>
        {summary && (
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            {insoleCount(summary.submission_count)}, all sizes. Numbers are medians; labels are the
            most common ones.
          </p>
        )}
      </section>

      {summary ? (
        <section className="grid gap-6 sm:grid-cols-2">
          <div>
            <h2 className="mb-2 font-semibold">Insole measurements</h2>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
              <dt>Length</dt>
              <dd>{formatMm(summary.median_length_mm)}</dd>
              <dt>Ball width</dt>
              <dd>{formatMm(summary.median_ball_width_mm)}</dd>
              <dt>Arch width</dt>
              <dd>{formatMm(summary.median_arch_width_mm)}</dd>
              <dt>Heel width</dt>
              <dd>{formatMm(summary.median_heel_width_mm)}</dd>
            </dl>
          </div>
          <div>
            <h2 className="mb-2 font-semibold">Fit</h2>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
              {fitLabelRows(summary).map((row) => (
                <div key={row.label} className="contents">
                  <dt>{row.label}</dt>
                  <dd>{row.value}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-2 text-xs text-zinc-500">{TOE_LABELS_NOTE}</p>
          </div>
        </section>
      ) : (
        <p className="text-zinc-600 dark:text-zinc-400">
          Nobody has measured this shoe yet.{" "}
          <Link href="/upload" className="font-medium underline">
            Upload an insole
          </Link>{" "}
          to add the first measurement.
        </p>
      )}

      {sizes.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="font-semibold">By size</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-zinc-500">
                <tr>
                  <th className="py-1 pr-4 font-medium">Size</th>
                  <th className="py-1 pr-4 font-medium">Insoles</th>
                  <th className="py-1 pr-4 font-medium">Length</th>
                  <th className="py-1 pr-4 font-medium">Ball width</th>
                  {FIT_FILTERS.map(({ column }) => (
                    <th key={column} className="py-1 pr-4 font-medium">
                      {CLASS_LABELS[column].label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                {sizes.map((row) => (
                  <tr key={`${row.size_system}-${row.size}`}>
                    <td className="py-1 pr-4">
                      {SIZE_SYSTEMS[row.size_system as SizeSystem]?.label ?? row.size_system} {row.size}
                    </td>
                    <td className="py-1 pr-4">{row.submission_count}</td>
                    <td className="py-1 pr-4">{formatMm(row.median_length_mm)}</td>
                    <td className="py-1 pr-4">{formatMm(row.median_ball_width_mm)}</td>
                    {FIT_FILTERS.map(({ column }) => (
                      <td key={column} className="py-1 pr-4">
                        {fitLabel(column, row[column])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}
