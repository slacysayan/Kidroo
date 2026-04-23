"use client";

import { ArrowUp } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Textarea } from "@/components/ui/Textarea";
import { createBrowserSupabaseClient } from "@/lib/supabase/client";
import { cn } from "@/lib/utils";

export type ChatComposerProps = {
  placeholder?: string;
  className?: string;
  autoFocus?: boolean;
};

/**
 * Chat-style input. Submit = Enter (Shift+Enter for newline).
 * Creates a `jobs` row via RLS and navigates to `/jobs/[id]`.
 */
export function ChatComposer({
  placeholder = "Paste a YouTube channel, playlist, or video URL…",
  className,
  autoFocus = true,
}: ChatComposerProps) {
  const router = useRouter();
  const [value, setValue] = useState("");
  const [pending, setPending] = useState(false);

  async function submit() {
    const trimmed = value.trim();
    if (!trimmed || pending) return;
    setPending(true);
    try {
      const supabase = createBrowserSupabaseClient();
      const { data, error } = await supabase
        .from("jobs")
        .insert({ source_url: trimmed, status: "pending" })
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

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void submit();
    }
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
      className={cn(
        "group relative flex items-end gap-2 rounded-lg border border-border/80 bg-background/70 p-2 shadow-sm backdrop-blur focus-within:border-foreground/30",
        className,
      )}
    >
      <Textarea
        autoFocus={autoFocus}
        placeholder={placeholder}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKeyDown}
        rows={1}
        className="min-h-[44px] border-0 bg-transparent px-2 py-2 text-[15px] shadow-none focus-visible:ring-0"
      />
      <button
        type="submit"
        aria-label="Submit"
        disabled={pending || !value.trim()}
        className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-foreground text-background transition-opacity disabled:opacity-30"
      >
        <ArrowUp className="h-4 w-4" aria-hidden />
      </button>
    </form>
  );
}
