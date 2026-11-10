import type { NextRequest } from "next/server";

import { parseShoeFilters, shoesToCsv } from "@/lib/shoe-fit";
import { listShoes } from "@/lib/shoes";

/**
 * The shoes on /shoes as a CSV file (#122), with the same filters as the page. Shoe-level
 * aggregates only, from the same function as the page (ADR 0011).
 */
export async function GET(request: NextRequest) {
  // getAll, like the page's searchParams: a repeated parameter uses its first value there too.
  const { searchParams } = request.nextUrl;
  const filters = parseShoeFilters(
    Object.fromEntries([...searchParams.keys()].map((key) => [key, searchParams.getAll(key)])),
  );
  const csv = shoesToCsv(await listShoes(filters));
  const date = new Date().toISOString().slice(0, 10);
  // The byte order mark makes Excel read the file as UTF-8, so accents in brand names survive.
  return new Response(`﻿${csv}`, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="fitfinder-shoes-${date}.csv"`,
      "Cache-Control": "no-store",
    },
  });
}
