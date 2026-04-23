"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { sanitizeNext } from "@/lib/auth/sanitize-next";
import { createBrowserSupabaseClient } from "@/lib/supabase/client";

/**
 * Login screen.
 *
 * Supports three Supabase auth flows:
 *   1. Email + password  — default submit.
 *   2. Magic link        — "Send me a link instead" toggle.
 *   3. OAuth             — Google button (toggle on in Supabase Dashboard first).
 *
 * Email allowlist is enforced server-side via a `before_signup` Edge Function
 * + RLS on the `allowed_emails` table (see docs/security).
 */
export default function LoginPage() {
  const router = useRouter();
  const params = useSearchParams();
  const next = sanitizeNext(params.get("next"));

  const [mode, setMode] = useState<"password" | "magic" | "signup">("password");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const supabase = createBrowserSupabaseClient();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      if (mode === "password") {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        router.replace(next);
      } else if (mode === "signup") {
        const { error } = await supabase.auth.signUp({
          email,
          password,
          options: {
            emailRedirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(next)}`,
          },
        });
        if (error) throw error;
        toast.success("Check your inbox to verify your email.");
      } else {
        const { error } = await supabase.auth.signInWithOtp({
          email,
          options: {
            emailRedirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(next)}`,
          },
        });
        if (error) throw error;
        toast.success("Magic link sent — check your inbox.");
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Sign-in failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleGoogle() {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback?next=${next}` },
    });
    if (error) toast.error(error.message);
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md items-center justify-center px-6">
      <form onSubmit={handleSubmit} className="w-full space-y-4">
        <header className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">Kidroo</h1>
          <p className="text-sm text-muted-foreground">
            {mode === "signup" ? "Create an account" : "Sign in to continue"}
          </p>
        </header>

        <label className="block space-y-1 text-sm">
          <span>Email</span>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2"
            autoComplete="email"
          />
        </label>

        {mode !== "magic" && (
          <label className="block space-y-1 text-sm">
            <span>Password</span>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-md border border-border bg-background px-3 py-2"
              autoComplete={mode === "signup" ? "new-password" : "current-password"}
              minLength={8}
            />
          </label>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-md bg-foreground px-4 py-2 text-background transition hover:opacity-90 disabled:opacity-50"
        >
          {loading
            ? "Working..."
            : mode === "magic"
              ? "Send magic link"
              : mode === "signup"
                ? "Create account"
                : "Sign in"}
        </button>

        <button
          type="button"
          onClick={handleGoogle}
          className="w-full rounded-md border border-border px-4 py-2 text-sm hover:bg-muted"
        >
          Continue with Google
        </button>

        <div className="flex justify-between text-xs text-muted-foreground">
          <button
            type="button"
            onClick={() => setMode(mode === "magic" ? "password" : "magic")}
            className="underline-offset-2 hover:underline"
          >
            {mode === "magic" ? "Use password" : "Use magic link"}
          </button>
          <button
            type="button"
            onClick={() => setMode(mode === "signup" ? "password" : "signup")}
            className="underline-offset-2 hover:underline"
          >
            {mode === "signup" ? "Have an account? Sign in" : "Create an account"}
          </button>
        </div>
      </form>
    </main>
  );
}
