import "server-only";

import { createClient } from "@supabase/supabase-js";

import type { Database } from "@/lib/database.types";

import { supabaseUrl } from "./env";

/**
 * Supabase client with the secret (service-role) key. It bypasses Row-Level Security
 * and can use the Auth admin API, so:
 *
 * - only import it from server code ("server-only" makes a client import fail the build),
 * - only use it for the few things a user's own session can't do (ADR 0006),
 * - always take the user id from the verified session, never from request input.
 */
export function createAdminClient() {
  const secretKey = process.env.SUPABASE_SECRET_KEY;
  if (!secretKey) {
    throw new Error("Missing environment variable SUPABASE_SECRET_KEY. See .env.example.");
  }
  return createClient<Database>(supabaseUrl(), secretKey, {
    // No user session: don't store or refresh tokens.
    auth: { persistSession: false, autoRefreshToken: false },
  });
}
