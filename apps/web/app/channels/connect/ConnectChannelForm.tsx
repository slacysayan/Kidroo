"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { createBrowserSupabaseClient } from "@/lib/supabase/client";

function slugify(input: string): string {
  return input
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 48);
}

export function ConnectChannelForm({ userId }: { userId: string }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [entity, setEntity] = useState("");
  const [pending, setPending] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    try {
      const supabase = createBrowserSupabaseClient();
      const entityId = entity.trim() || slugify(name);
      if (!entityId) {
        toast.error("enter a channel name");
        return;
      }
      const { data, error } = await supabase
        .from("channels")
        .insert({
          user_id: userId,
          name: name.trim(),
          composio_entity_id: entityId,
          connected: false,
        })
        .select("id")
        .single();
      if (error || !data) {
        toast.error(error?.message ?? "could not create channel");
        return;
      }
      toast.success(
        "channel created — finish the Composio OAuth flow from the dashboard",
      );
      router.replace("/app");
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-muted-foreground">Channel name</span>
        <input
          type="text"
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            if (!entity) setEntity(slugify(e.target.value));
          }}
          required
          placeholder="e.g. Finance Daily"
          className="rounded-md border border-border bg-background px-3 py-2 outline-none focus:border-foreground/50"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-muted-foreground">Composio entity id (alias)</span>
        <input
          type="text"
          value={entity}
          onChange={(e) => setEntity(slugify(e.target.value))}
          placeholder="finance_daily"
          className="rounded-md border border-border bg-background px-3 py-2 font-mono outline-none focus:border-foreground/50"
        />
      </label>
      <button
        type="submit"
        disabled={pending}
        className="rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background disabled:opacity-50"
      >
        {pending ? "creating…" : "Create channel"}
      </button>
    </form>
  );
}
