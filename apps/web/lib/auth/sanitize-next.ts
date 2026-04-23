/**
 * Restrict post-auth redirects to same-origin relative paths.
 *
 * The `?next=` search param is attacker-controlled; without this sanitizer a
 * crafted `?next=//evil.tld` or `?next=https://evil.tld` would let a
 * compromised link redirect the user off-site after a successful sign-in.
 *
 * Shared between the OAuth/magic-link callback route and the password-based
 * login page so both flows enforce the same policy.
 */
export function sanitizeNext(raw: string | null | undefined): string {
  if (!raw) return "/app";
  if (!raw.startsWith("/")) return "/app";
  if (raw.startsWith("//")) return "/app";
  if (raw.startsWith("/\\")) return "/app";
  return raw;
}
