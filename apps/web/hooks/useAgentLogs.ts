"use client";

import { useEffect, useState } from "react";

import type { AgentName, AgentStep } from "@/lib/agents/constants";
import { createBrowserSupabaseClient } from "@/lib/supabase/client";

export type AgentLogRow = {
  id: number | string;
  job_id: string;
  video_id: string | null;
  agent: AgentName;
  step: AgentStep;
  message: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
};

/**
 * Subscribe to `agent_logs` for a job via Supabase Realtime.
 *
 * - Backfills existing rows on mount (up to 500).
 * - Appends inserts live.
 * - Cleans up channel on unmount.
 */
export function useAgentLogs(jobId: string): {
  rows: AgentLogRow[];
  loading: boolean;
} {
  const [rows, setRows] = useState<AgentLogRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const supabase = createBrowserSupabaseClient();
    let active = true;

    (async () => {
      const { data } = await supabase
        .from("agent_logs")
        .select("*")
        .eq("job_id", jobId)
        .order("id", { ascending: true })
        .limit(500);
      if (!active) return;
      setRows((data as AgentLogRow[] | null) ?? []);
      setLoading(false);
    })();

    const channel = supabase
      .channel(`agent_logs:${jobId}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "agent_logs",
          filter: `job_id=eq.${jobId}`,
        },
        (payload) => {
          setRows((prev) => [...prev, payload.new as AgentLogRow]);
        },
      )
      .subscribe();

    return () => {
      active = false;
      void supabase.removeChannel(channel);
    };
  }, [jobId]);

  return { rows, loading };
}
