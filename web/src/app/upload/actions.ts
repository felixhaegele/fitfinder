"use server";

import { redirect } from "next/navigation";

import { getUser } from "@/lib/auth";
import { parseSubmission, type SubmissionInput } from "@/lib/submission-form";
import { createClient } from "@/lib/supabase/server";

export type CreateSubmissionState = { error: string } | null;

type Supabase = Awaited<ReturnType<typeof createClient>>;

/**
 * Called after the browser has uploaded the photo to the private bucket.
 * Creates the shoe model if it's new, then the submission (which enqueues the job).
 */
export async function createSubmission(form: FormData): Promise<CreateSubmissionState> {
  const user = await getUser();
  if (!user) {
    return { error: "Your session has expired. Please log in again." };
  }

  const parsed = parseSubmission(form, user.id);
  if (!parsed.ok) {
    return { error: parsed.error };
  }
  const input = parsed.value;

  const supabase = await createClient();
  const shoeModelId = await resolveShoeModel(supabase, input.shoe);
  if (!shoeModelId) {
    return { error: "We couldn't save the shoe model. Please try again." };
  }

  const { error } = await supabase.from("submissions").insert({
    shoe_model_id: shoeModelId,
    size: input.size,
    size_system: input.sizeSystem,
    insole_condition: input.insoleCondition,
    image_path: input.imagePath,
    // Set here, on the server, at the moment the user submitted the consented form.
    consent_at: new Date().toISOString(),
  });

  if (error) {
    // P0429: daily limit trigger (supabase/migrations/*_submissions_daily_limit.sql)
    if (error.code === "P0429") {
      return { error: "You've reached today's limit of 20 uploads. Please try again tomorrow." };
    }
    return { error: "We couldn't save your upload. Please try again." };
  }

  redirect("/account?submitted=1");
}

async function resolveShoeModel(
  supabase: Supabase,
  shoe: SubmissionInput["shoe"],
): Promise<string | null> {
  if (shoe.kind === "existing") {
    return shoe.id;
  }

  const { data, error } = await supabase
    .from("shoe_models")
    .insert({ brand: shoe.brand, model: shoe.model, year: shoe.year })
    .select("id")
    .single();
  if (data) {
    return data.id;
  }

  // 23505: someone already added this shoe (the unique index ignores case and spacing).
  if (error?.code === "23505") {
    const { data: existing } = await supabase
      .from("shoe_models")
      .select("id")
      .ilike("brand", escapeLike(shoe.brand))
      .ilike("model", escapeLike(shoe.model))
      .eq("year", shoe.year)
      .limit(1)
      .maybeSingle();
    return existing?.id ?? null;
  }
  return null;
}

/** ilike treats % and _ as wildcards; a shoe called "100%" must match literally. */
function escapeLike(value: string): string {
  return value.replace(/[\\%_]/g, (c) => `\\${c}`);
}
