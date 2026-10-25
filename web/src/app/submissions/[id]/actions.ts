"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { INSOLES_BUCKET } from "@/lib/account-deletion";
import { getUser } from "@/lib/auth";
import { deleteSubmission, type SubmissionRows } from "@/lib/submission-deletion";
import { createClient } from "@/lib/supabase/server";

export type DeleteSubmissionState = { error: string } | null;

const COLUMNS = "image_path, processed_image_path";

/**
 * Deletes one of the logged-in user's submissions and both its photos (#82).
 *
 * Runs with the user's own session, not the admin key: RLS lets users delete their own
 * rows, and the storage policy lets them delete any file in their own <user_id>/ folder,
 * which includes <user_id>/processed/. So someone else's id simply finds nothing.
 */
export async function deleteMySubmission(
  _prev: DeleteSubmissionState,
  form: FormData,
): Promise<DeleteSubmissionState> {
  const user = await getUser();
  if (!user) {
    return { error: "Your session has expired. Please log in again." };
  }
  const id = form.get("submissionId");
  if (typeof id !== "string") {
    return { error: "This upload doesn't exist." };
  }

  const supabase = await createClient();
  const rows: SubmissionRows = {
    async get(submissionId) {
      const { data, error } = await supabase
        .from("submissions")
        .select(COLUMNS)
        .eq("id", submissionId)
        .maybeSingle();
      if (error) throw new Error(`Reading submission failed: ${error.message}`);
      return data;
    },
    async delete(submissionId) {
      const { data, error } = await supabase
        .from("submissions")
        .delete()
        .eq("id", submissionId)
        .select(COLUMNS)
        .maybeSingle();
      if (error) throw new Error(`Deleting submission failed: ${error.message}`);
      return data;
    },
  };

  let found: boolean;
  try {
    found = await deleteSubmission(
      { bucket: supabase.storage.from(INSOLES_BUCKET), rows },
      user.id,
      id,
    );
  } catch (err) {
    console.error(`Deleting submission ${id} failed:`, err);
    return { error: "We couldn't delete this upload. Please try again." };
  }
  if (!found) {
    return { error: "This upload doesn't exist." };
  }

  revalidatePath("/submissions");
  redirect("/submissions");
}
