import { NextResponse } from "next/server";
import { sanitizeNext } from "@/lib/auth/sanitize-next";
import { createServerSupabaseClient } from "@/lib/supabase/server";

/**
 * Supabase OAuth / magic-link callback.
 * Exchanges the ?code param for a session and redirects to ?next (default /app).
 */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const next = sanitizeNext(url.searchParams.get("next"));

  if (code) {
    const supabase = await createServerSupabaseClient();
    await supabase.auth.exchangeCodeForSession(code);
  }
  return NextResponse.redirect(new URL(next, url.origin));
}
