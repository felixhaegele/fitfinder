import "server-only";

import { redirect } from "next/navigation";
import { connection } from "next/server";

import { createClient } from "@/lib/supabase/server";

export type User = {
  id: string;
  email: string;
};

/**
 * The logged-in user, or null. getClaims() verifies the session token instead of just
 * trusting the cookie, so this is safe to use for access decisions.
 * Reads cookies, so callers must render inside a <Suspense> boundary.
 */
export async function getUser(): Promise<User | null> {
  // Always check at request time. The token check compares its expiry with the current
  // time, which Next.js won't let run during prerendering or prefetching. Caching the
  // result ("use cache: private") would be faster but could show a stale login state.
  await connection();
  const supabase = await createClient();
  const { data, error } = await supabase.auth.getClaims();
  if (error || !data) {
    return null;
  }
  return { id: data.claims.sub, email: data.claims.email ?? "" };
}

/** The logged-in user; sends everyone else to /login and back here afterwards. */
export async function requireUser(returnTo: string): Promise<User> {
  const user = await getUser();
  if (!user) {
    redirect(`/login?next=${encodeURIComponent(returnTo)}`);
  }
  return user;
}
