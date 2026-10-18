import { createServerClient } from "@supabase/ssr";
import { type NextRequest, NextResponse } from "next/server";

import type { Database } from "@/lib/database.types";

import { supabasePublishableKey, supabaseUrl } from "./env";

/**
 * Refreshes the user's session before the page renders. The access token expires after
 * an hour; without this, Server Components would see an expired session because they
 * can't write the refreshed cookies themselves.
 *
 * This is not an authorization check: pages still check the user themselves (lib/auth.ts).
 */
export async function updateSession(request: NextRequest) {
  let response = NextResponse.next({ request });

  const supabase = createServerClient<Database>(supabaseUrl(), supabasePublishableKey(), {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet, headers) {
        // Pass refreshed cookies both to the page (request) and to the browser (response).
        for (const { name, value } of cookiesToSet) {
          request.cookies.set(name, value);
        }
        response = NextResponse.next({ request });
        for (const { name, value, options } of cookiesToSet) {
          response.cookies.set(name, value, options);
        }
        // No-cache headers, so a CDN never serves one user's session cookie to another.
        for (const [key, value] of Object.entries(headers)) {
          response.headers.set(key, value);
        }
      },
    },
  });

  // Must run before anything else: this is what triggers the refresh.
  await supabase.auth.getClaims();

  return response;
}
