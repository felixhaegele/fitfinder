"use server";

import { redirect } from "next/navigation";

import {
  CONFIRMATION_WORD,
  deleteAccount,
  INSOLES_BUCKET,
  isConfirmed,
} from "@/lib/account-deletion";
import { getUser } from "@/lib/auth";
import { createAdminClient } from "@/lib/supabase/admin";
import { createClient } from "@/lib/supabase/server";

export type DeleteAccountState = { error: string } | null;

/**
 * Deletes the logged-in user's account, all their rows and all their photos (ADR 0006).
 * Anyone can POST to a server action, so everything is checked here, not in the page.
 */
export async function deleteMyAccount(
  _prev: DeleteAccountState,
  form: FormData,
): Promise<DeleteAccountState> {
  if (!isConfirmed(form.get("confirm"))) {
    return { error: `Please type ${CONFIRMATION_WORD} to confirm.` };
  }

  // The id comes from the verified session token only, never from the form, so a user
  // can only ever delete themselves.
  const user = await getUser();
  if (!user) {
    return { error: "Your session has expired. Please log in again." };
  }

  const admin = createAdminClient();
  try {
    await deleteAccount(
      { bucket: admin.storage.from(INSOLES_BUCKET), authAdmin: admin.auth.admin },
      user.id,
    );
  } catch (err) {
    console.error(`Deleting account ${user.id} failed:`, err);
    return {
      error:
        "We couldn't finish deleting your account. Please try again. If it keeps failing, contact us.",
    };
  }

  // The account is gone; clear the session cookies in this browser. "local" skips
  // signing out other devices: deleting the user already ended all their sessions.
  const supabase = await createClient();
  await supabase.auth.signOut({ scope: "local" });

  redirect("/account/deleted");
}
