import "server-only";

import type { ShoeFilters } from "@/lib/shoe-fit";
import { createClient } from "@/lib/supabase/server";

// Data access for the public shoe pages. The fit numbers come from security-definer
// functions that return shoe-level aggregates (ADR 0011) and per-insole shoe data (ADR
// 0014) only; the rows behind them stay protected by RLS. Works the same for anonymous and
// logged-in visitors.

export async function listShoes(filters: ShoeFilters) {
  const supabase = await createClient();
  let query = supabase.rpc("shoe_fit_summaries", filters.q ? { search: filters.q } : {});
  // Label filters run as PostgREST equality filters on the function's result. The values
  // are already limited to known labels by parseShoeFilters.
  for (const [column, value] of Object.entries(filters.classes)) {
    query = query.eq(column, value);
  }
  const { data, error } = await query;
  if (error) {
    throw new Error(`Could not load shoes: ${error.message}`);
  }
  return data;
}

export async function getShoe(id: string) {
  const supabase = await createClient();
  const [model, summary, sizes, insoles] = await Promise.all([
    supabase.from("shoe_models").select("id, brand, model, year").eq("id", id).maybeSingle(),
    supabase.rpc("shoe_fit_summaries").eq("shoe_model_id", id).maybeSingle(),
    supabase.rpc("shoe_fit_by_size", { shoe_model: id }),
    supabase.rpc("shoe_insoles", { shoe_model: id }),
  ]);
  const error = model.error ?? summary.error ?? sizes.error ?? insoles.error;
  if (error) {
    throw new Error(`Could not load shoe: ${error.message}`);
  }
  if (!model.data) {
    return null;
  }
  return { ...model.data, summary: summary.data, sizes: sizes.data ?? [], insoles: insoles.data ?? [] };
}

/** One measured insole with its shoe and outline, for the printable PDF (ADR 0014). */
export async function getInsole(insoleId: string) {
  const supabase = await createClient();
  const { data, error } = await supabase.rpc("shoe_insole", { insole: insoleId }).maybeSingle();
  if (error) {
    throw new Error(`Could not load insole: ${error.message}`);
  }
  return data;
}
