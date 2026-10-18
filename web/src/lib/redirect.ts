/**
 * Where to send the user after login. Only same-site paths are allowed: accepting any
 * URL from the query string would let a crafted link send people to another site
 * right after they logged in (an "open redirect").
 */
export function safeNextPath(value: unknown, fallback = "/account"): string {
  if (typeof value !== "string" || !value.startsWith("/")) {
    return fallback;
  }
  // "//evil.com" and "/\evil.com" are treated by browsers as other hosts.
  if (value.startsWith("//") || value.startsWith("/\\")) {
    return fallback;
  }
  return value;
}
