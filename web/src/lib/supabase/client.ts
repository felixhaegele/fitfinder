import { createBrowserClient } from "@supabase/ssr";

import type { Database } from "@/lib/database.types";

import { supabasePublishableKey, supabaseUrl } from "./env";

/** Supabase client for Client Components (runs in the browser). */
export function createClient() {
  return createBrowserClient<Database>(supabaseUrl(), supabasePublishableKey());
}
