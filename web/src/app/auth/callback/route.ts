import type { NextRequest } from "next/server";

import { safeNextPath } from "@/lib/redirect";
import { createClient } from "@/lib/supabase/server";

/**
 * PKCE code exchange: the default Supabase magic link (?code=), which only works in the
 * browser that requested it. Our email templates now link to /auth/confirm instead
 * (#46); this route stays for links sent before that change and for a hosted project
 * whose dashboard templates haven't been updated yet.
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
