import type { EmailOtpType } from "@supabase/supabase-js";
import type { NextRequest } from "next/server";

import { safeNextPath } from "@/lib/redirect";
import { createClient } from "@/lib/supabase/server";

/**
 * The magic link from the email lands here with a one-time ?token_hash=. Verifying it
 * needs nothing from the browser that requested the link, so it works on another device
 * too (#46). On success the session cookies are set and the user continues to ?next=.
 *
 * Also accepts ?code= (PKCE): a hosted project still on Supabase's default email
 * template redirects here with a code instead. That only works in the requesting
 * browser, but it means login keeps working while the dashboard templates are updated.
 */
export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const tokenHash = searchParams.get("token_hash");
  const type = searchParams.get("type") as EmailOtpType | null;
  const code = searchParams.get("code");
  const next = safeNextPath(searchParams.get("next"));

  if (tokenHash && type) {
    const supabase = await createClient();
    const { error } = await supabase.auth.verifyOtp({ type, token_hash: tokenHash });
    if (!error) {
      return redirectTo(next);
    }
  } else if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return redirectTo(next);
    }
  }
  return redirectTo("/login?error=link");
}

// Relative on purpose, so the browser stays on the host it used (see auth/callback).
function redirectTo(path: string) {
  return new Response(null, { status: 303, headers: { Location: path } });
}
