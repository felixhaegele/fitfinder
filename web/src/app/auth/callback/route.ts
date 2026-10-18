import type { NextRequest } from "next/server";

import { safeNextPath } from "@/lib/redirect";
import { createClient } from "@/lib/supabase/server";

/**
 * The magic link lands here with a one-time ?code=. Exchanging it needs the "code
 * verifier" cookie set when the link was requested, so it only works in that browser
 * (PKCE; cross-device links are #46). On success the session cookies are set and the
 * user continues to ?next=.
 */
export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const code = searchParams.get("code");
  const next = safeNextPath(searchParams.get("next"));

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return redirectTo(next);
    }
  }
  return redirectTo("/login?error=link");
}

// Relative Location on purpose: the browser stays on the host it used. An absolute URL
// built from request.nextUrl can name a different host (localhost vs 127.0.0.1, or the
// internal host behind a proxy), and the new session cookie wouldn't be sent there.
function redirectTo(path: string) {
  return new Response(null, { status: 303, headers: { Location: path } });
}
