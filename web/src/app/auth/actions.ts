"use server";

import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { safeNextPath } from "@/lib/redirect";
import { createClient } from "@/lib/supabase/server";

export type LoginState =
  | { status: "idle" }
  | { status: "sent"; email: string }
  | { status: "error"; message: string };

// Deliberately loose: the real check is whether the email arrives.
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export async function sendMagicLink(_prev: LoginState, formData: FormData): Promise<LoginState> {
  const email = String(formData.get("email") ?? "").trim();
  if (!EMAIL_PATTERN.test(email)) {
    return { status: "error", message: "Please enter a valid email address." };
  }

  // The link must come back to the same site (and, with PKCE, the same browser).
  // Supabase only accepts redirect URLs on its allow-list (config.toml / dashboard).
  const origin = (await headers()).get("origin");
  if (!origin) {
    return { status: "error", message: "Something went wrong. Please reload and try again." };
  }
  const next = safeNextPath(formData.get("next"));
  const callback = new URL("/auth/callback", origin);
  callback.searchParams.set("next", next);

  const supabase = await createClient();
  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: { emailRedirectTo: callback.toString(), shouldCreateUser: true },
  });

  if (error) {
    // 429: Supabase limits how many emails one address/project can trigger.
    const message =
      error.status === 429
        ? "Too many login emails. Please wait a minute and try again."
        : "We couldn't send the email. Please try again.";
    return { status: "error", message };
  }
  return { status: "sent", email };
}

export async function signOut() {
  const supabase = await createClient();
  await supabase.auth.signOut();
  redirect("/");
}
