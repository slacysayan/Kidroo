"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
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
    <form onSubmit={submit} className="space-y-4">
      <label className="flex flex-col gap-1.5 text-sm">
        <span className="text-xs font-medium text-muted-foreground">Channel name</span>
        <Input
          type="text"
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            if (!entity) setEntity(slugify(e.target.value));
          }}
          required
          placeholder="e.g. Finance Daily"
        />
      </label>
      <label className="flex flex-col gap-1.5 text-sm">
        <span className="text-xs font-medium text-muted-foreground">
          Composio entity id (alias)
        </span>
        <Input
          type="text"
          value={entity}
          onChange={(e) => setEntity(slugify(e.target.value))}
          placeholder="finance_daily"
          className="font-mono"
        />
      </label>
      <Button type="submit" disabled={pending} className="w-full">
        {pending ? "creating…" : "Create channel"}
      </Button>
    </form>
  );
}
