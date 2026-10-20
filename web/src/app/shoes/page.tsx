import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { FIT_FILTERS, fitLabelRows, hasActiveFilters, insoleCount, MAX_SEARCH_LENGTH, parseShoeFilters, type ShoeFilters } from "@/lib/shoe-fit";
import { listShoes } from "@/lib/shoes";
import { CLASS_LABELS, formatMm, TOE_LABELS_NOTE } from "@/lib/submission-status";

export const metadata: Metadata = { title: "Shoes · FitFinder" };

export default function ShoesPage({ searchParams }: PageProps<"/shoes">) {
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-6 py-16">
      <section className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Shoes by fit</h1>
        <p className="text-zinc-600 dark:text-zinc-400">
          Measured from insoles our users photographed. Numbers are medians; labels are the most
          common ones.
        </p>
      </section>
      <Suspense fallback={<p className="text-zinc-500">Loading…</p>}>
        <ShoeSearch searchParams={searchParams} />
      </Suspense>
    </main>
  );
}

async function ShoeSearch({ searchParams }: { searchParams: PageProps<"/shoes">["searchParams"] }) {
  const filters = parseShoeFilters(await searchParams);
  const shoes = await listShoes(filters);

  return (
    <>
      <FilterForm filters={filters} />
      {shoes.length === 0 ? (
        <EmptyState filtered={hasActiveFilters(filters)} />
      ) : (
        <section aria-label="Shoes" className="flex flex-col gap-3">
          <ul className="divide-y divide-zinc-200 rounded-lg border border-zinc-200 dark:divide-zinc-800 dark:border-zinc-800">
            {shoes.map((shoe) => (
              <li key={shoe.shoe_model_id}>
                <Link
                  href={`/shoes/${shoe.shoe_model_id}`}
                  className="flex flex-col gap-2 px-4 py-3 hover:bg-zinc-50 dark:hover:bg-zinc-900"
                >
                  <span className="flex flex-wrap items-baseline justify-between gap-x-4">
                    <span className="font-medium">
                      {shoe.brand} {shoe.model} ({shoe.year})
                    </span>
                    <span className="text-sm text-zinc-500">
                      {insoleCount(shoe.submission_count)} · length {formatMm(shoe.median_length_mm)} ·
                      ball {formatMm(shoe.median_ball_width_mm)}
                    </span>
                  </span>
                  <dl className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
                    {fitLabelRows(shoe).map((row) => (
                      <div key={row.label} className="flex gap-1">
                        <dt className="text-zinc-500">{row.label}:</dt>
                        <dd>{row.value}</dd>
                      </div>
                    ))}
                  </dl>
                </Link>
              </li>
            ))}
          </ul>
          <p className="text-xs text-zinc-500">{TOE_LABELS_NOTE}</p>
        </section>
      )}
    </>
  );
}

/** A plain GET form: works without JavaScript and gives every search a shareable URL. */
function FilterForm({ filters }: { filters: ShoeFilters }) {
  const field = "rounded-md border border-zinc-300 bg-transparent px-2 py-1.5 dark:border-zinc-700";
  return (
    <form action="/shoes" method="get" role="search" className="flex flex-wrap items-end gap-3">
      <label className="flex grow flex-col gap-1 text-sm">
        <span>Brand or model</span>
        <input
          type="search"
          name="q"
          defaultValue={filters.q}
          maxLength={MAX_SEARCH_LENGTH}
          placeholder="e.g. Shimano RC7"
          className={field}
        />
      </label>
      {FIT_FILTERS.map(({ param, column }) => (
        <label key={param} className="flex flex-col gap-1 text-sm">
          <span>{CLASS_LABELS[column].label}</span>
          <select name={param} defaultValue={filters.classes[column] ?? ""} className={field}>
            <option value="">Any</option>
            {Object.entries(CLASS_LABELS[column].values).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
      ))}
      <button
        type="submit"
        className="rounded-md bg-zinc-900 px-4 py-1.5 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
      >
        Search
      </button>
    </form>
  );
}

function EmptyState({ filtered }: { filtered: boolean }) {
  if (filtered) {
    return (
      <p className="text-zinc-600 dark:text-zinc-400">
        No measured shoes match your search.{" "}
        <Link href="/shoes" className="font-medium underline">
          Show all shoes
        </Link>
      </p>
    );
  }
  return (
    <p className="text-zinc-600 dark:text-zinc-400">
      No shoes have been measured yet.{" "}
      <Link href="/upload" className="font-medium underline">
        Upload an insole
      </Link>{" "}
      to add the first one.
    </p>
  );
}
