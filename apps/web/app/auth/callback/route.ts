import { NextResponse } from "next/server";
import { createServerSupabaseClient } from "@/lib/supabase/server";

/**
 * Supabase OAuth / magic-link callback.
 * Exchanges the ?code param for a session and redirects to ?next (default /app).
 */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");

  // `next` is attacker-controlled; restrict to same-origin relative paths so
  // `?next=https://evil.tld` (or `?next=//evil.tld`) cannot redirect users
  // off-site after a successful auth exchange.
  const next = sanitizeNext(url.searchParams.get("next"));

  if (code) {
    const supabase = await createServerSupabaseClient();
    await supabase.auth.exchangeCodeForSession(code);
  }
  return NextResponse.redirect(new URL(next, url.origin));
}

function sanitizeNext(raw: string | null): string {
  if (!raw) return "/app";
  if (!raw.startsWith("/")) return "/app";
  if (raw.startsWith("//")) return "/app";
  if (raw.startsWith("/\\")) return "/app";
  return raw;
}
