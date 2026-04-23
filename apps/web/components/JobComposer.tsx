"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { createBrowserSupabaseClient } from "@/lib/supabase/client";

/**
 * Minimal "paste a link, go" composer. Creates a job row via Supabase
 * (RLS-scoped insert) and navigates to the live job view. Scan + start are
 * kicked off by the FastAPI job endpoints, triggered by `/jobs/[id]`.
 */
export function JobComposer() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [pending, setPending] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    setPending(true);
    try {
      const supabase = createBrowserSupabaseClient();
      const {
        data: { user },
        error: authError,
      } = await supabase.auth.getUser();
      if (authError || !user) {
        toast.error(authError?.message ?? "please sign in again");
        return;
      }
      const { data, error } = await supabase
        .from("jobs")
        .insert({
          user_id: user.id,
          source_url: url.trim(),
          status: "pending",
        })
        .select("id")
        .single();
      if (error || !data) {
        toast.error(error?.message ?? "could not create job");
        return;
      }
      router.push(`/jobs/${data.id}`);
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex gap-2">
      <input
        type="url"
        placeholder="Paste a YouTube channel, playlist, or video URL"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        required
        className="flex-1 rounded-md border border-border bg-background px-4 py-3 text-sm outline-none focus:border-foreground/50"
      />
      <button
        type="submit"
        disabled={pending}
        className="rounded-md bg-foreground px-4 py-3 text-sm font-medium text-background disabled:opacity-50"
      >
        {pending ? "creating…" : "start →"}
      </button>
    </form>
  );
}
