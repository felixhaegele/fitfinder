import "server-only";

import { createClient } from "@/lib/supabase/server";

// Data access for the status pages. All queries run as the logged-in user, so RLS limits
// them to the user's own submissions: someone else's id simply returns nothing.

/** Signed URLs expire, so a copied link stops working after a while. */
const SIGNED_URL_SECONDS = 10 * 60;

export async function listMySubmissions() {
  const supabase = await createClient();
  const { data } = await supabase
    .from("submissions")
    .select("id, status, size, size_system, created_at, shoe_models(brand, model, year)")
    .order("created_at", { ascending: false });
  return data ?? [];
}

export async function getMySubmission(id: string) {
  const supabase = await createClient();
  const { data: submission } = await supabase
    .from("submissions")
    .select(
      `id, status, rejection_reason, size, size_system, insole_condition, created_at,
       image_path, processed_image_path,
       shoe_models(brand, model, year),
       measurements(pipeline_version, length_mm, ball_width_mm, heel_width_mm, arch_width_mm, created_at,
         classifications(classifier_version, width_class, arch_class, toe_box_shape, created_at))`,
    )
    .eq("id", id)
    .maybeSingle();
  if (!submission) {
    return null;
  }

  // Re-processing adds new versions next to old ones; show the newest.
  const measurement = newest(submission.measurements);
  const classification = measurement ? newest(measurement.classifications) : null;

  const [originalUrl, processedUrl] = await Promise.all([
    signedUrl(supabase, submission.image_path),
    submission.processed_image_path ? signedUrl(supabase, submission.processed_image_path) : null,
  ]);

  return { ...submission, measurement, classification, originalUrl, processedUrl };
}

function newest<T extends { created_at: string }>(rows: T[]): T | null {
  return rows.toSorted((a, b) => b.created_at.localeCompare(a.created_at))[0] ?? null;
}

async function signedUrl(supabase: Awaited<ReturnType<typeof createClient>>, path: string) {
  const { data } = await supabase.storage.from("insoles").createSignedUrl(path, SIGNED_URL_SECONDS);
  return data?.signedUrl ?? null;
}
