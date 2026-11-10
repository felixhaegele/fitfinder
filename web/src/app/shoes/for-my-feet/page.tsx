import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { DEFAULT_WIGGLE_MM, FOOT_LIMITS, type Foot, type FootQuery, matchSizes, parseFootQuery } from "@/lib/foot-match";
import { fitLabel } from "@/lib/shoe-fit";
import { listShoeSizes } from "@/lib/shoes";
import { SIZE_SYSTEMS, type SizeSystem } from "@/lib/submission-form";
import { formatMm } from "@/lib/submission-status";

export const metadata: Metadata = { title: "Find by model · FitFinder" };

export default function FindByModelPage({ searchParams }: PageProps<"/shoes/for-my-feet">) {
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-6 py-16">
      <section className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Shoes for your feet</h1>
        <p className="text-zinc-600 dark:text-zinc-400">
          Enter your foot length and width, and we list the shoes with a measured size whose insole
          is long enough and wide enough. Measure standing, with your heel against a wall: length
          from the wall to your longest toe, width across the widest part of your forefoot.
        </p>
      </section>
      <Suspense fallback={<p className="text-zinc-500">Loading…</p>}>
        <FootSearch searchParams={searchParams} />
      </Suspense>
    </main>
  );
}

async function FootSearch({ searchParams }: { searchParams: PageProps<"/shoes/for-my-feet">["searchParams"] }) {
  const query = parseFootQuery(await searchParams);
  return (
    <>
      <FootForm query={query} />
      {query.error && (
        <p role="alert" className="text-red-600">
          {query.error}
        </p>
      )}
      {query.foot && <Matches foot={query.foot} />}
    </>
  );
}

/** A plain GET form, like /shoes: works without JavaScript and gives every search a URL. */
function FootForm({ query }: { query: FootQuery }) {
  const field = "w-32 rounded-md border border-zinc-300 bg-transparent px-2 py-1.5 dark:border-zinc-700";
  const fields = [
    { name: "length", label: "Foot length (mm)", value: query.values.length, limits: FOOT_LIMITS.length, required: true },
    { name: "width", label: "Foot width (mm)", value: query.values.width, limits: FOOT_LIMITS.width, required: true },
    { name: "wiggle", label: "Wiggle room (mm)", value: query.values.wiggle || String(DEFAULT_WIGGLE_MM), limits: FOOT_LIMITS.wiggle, required: false },
  ] as const;
  return (
    <form action="/shoes/for-my-feet" method="get" role="search" className="flex flex-col gap-2">
      <div className="flex flex-wrap items-end gap-3">
        {fields.map((f) => (
          <label key={f.name} className="flex flex-col gap-1 text-sm">
            <span>{f.label}</span>
            <input
              type="number"
              name={f.name}
              defaultValue={f.value}
              min={f.limits.min}
              max={f.limits.max}
              step={0.5}
              required={f.required}
              inputMode="decimal"
              className={field}
            />
          </label>
        ))}
        <button
          type="submit"
          className="rounded-md bg-zinc-900 px-4 py-1.5 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
        >
          Find shoes
        </button>
      </div>
      <p className="text-xs text-zinc-500">
        Wiggle room is added to your foot length: an insole must be at least that much longer than
        your foot. {DEFAULT_WIGGLE_MM} mm suits most riders; less for a snug race fit.
      </p>
    </form>
  );
}

async function Matches({ foot }: { foot: Foot }) {
  const matches = matchSizes(await listShoeSizes(), foot);
  const needed = foot.lengthMm + foot.wiggleMm;

  if (matches.length === 0) {
    return (
      <p className="text-zinc-600 dark:text-zinc-400">
        No measured size has an insole of about {formatMm(needed)} that is at least{" "}
        {formatMm(foot.widthMm)} wide. Try less wiggle room, or{" "}
        <Link href="/shoes" className="font-medium underline">
          browse by type
        </Link>
        .
      </p>
    );
  }

  return (
    <section aria-label="Matching shoes" className="flex flex-col gap-3">
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        Insoles of at least {formatMm(needed)} ({formatMm(foot.lengthMm)} + {foot.wiggleMm} mm wiggle
        room), closest fit first.
      </p>
      <ul className="divide-y divide-zinc-200 rounded-lg border border-zinc-200 dark:divide-zinc-800 dark:border-zinc-800">
        {matches.map(({ row, spareLengthMm, spareWidthMm }) => (
          <li key={row.shoe_model_id}>
            <Link
              href={`/shoes/${row.shoe_model_id}`}
              className="flex flex-col gap-1 px-4 py-3 hover:bg-zinc-50 dark:hover:bg-zinc-900"
            >
              <span className="flex flex-wrap items-baseline justify-between gap-x-4">
                <span className="font-medium">
                  {row.brand} {row.model} ({row.year})
                </span>
                <span className="text-sm">
                  Size {SIZE_SYSTEMS[row.size_system as SizeSystem]?.label ?? row.size_system} {row.size}
                </span>
              </span>
              <span className="text-sm text-zinc-500">
                Insole {formatMm(row.median_length_mm)} long ({formatMm(spareLengthMm)} longer than
                your foot), {formatMm(row.median_ball_width_mm)} at the ball (
                {formatMm(spareWidthMm)} spare) · Width: {fitLabel("width_class", row.width_class)}
              </span>
            </Link>
          </li>
        ))}
      </ul>
      <p className="text-xs text-zinc-500">
        Only sizes someone has measured can appear. Numbers are medians of the measured insoles.
      </p>
    </section>
  );
}
