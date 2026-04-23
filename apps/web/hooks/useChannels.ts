"use client";

import { useEffect, useState } from "react";

import { createBrowserSupabaseClient } from "@/lib/supabase/client";

export type ChannelRow = {
  id: string;
  name: string;
  composio_entity_id: string;
  connected: boolean;
  yt_channel_id: string | null;
};

/**
 * Live-subscribed list of the authenticated user's channels. RLS scopes rows
 * to the current user automatically.
 */
export function useChannels(initial: ChannelRow[] = []): {
  channels: ChannelRow[];
} {
  const [channels, setChannels] = useState<ChannelRow[]>(initial);

  useEffect(() => {
    const supabase = createBrowserSupabaseClient();
    let active = true;

    (async () => {
      const { data } = await supabase
        .from("channels")
        .select("id, name, composio_entity_id, connected, yt_channel_id")
        .order("created_at", { ascending: false });
      if (!active) return;
      if (data) setChannels(data as ChannelRow[]);
    })();

    const channel = supabase
      .channel("channels:me")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "channels" },
        (payload) => {
          setChannels((prev) => {
            if (payload.eventType === "INSERT") {
              const row = payload.new as ChannelRow;
              if (prev.some((c) => c.id === row.id)) return prev;
              return [row, ...prev];
            }
            if (payload.eventType === "UPDATE") {
              const row = payload.new as ChannelRow;
              return prev.map((c) => (c.id === row.id ? row : c));
            }
            if (payload.eventType === "DELETE") {
              const row = payload.old as { id: string };
              return prev.filter((c) => c.id !== row.id);
            }
            return prev;
          });
        },
      )
      .subscribe();

    return () => {
      active = false;
      void supabase.removeChannel(channel);
    };
  }, []);

  return { channels };
}
