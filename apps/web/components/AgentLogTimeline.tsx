"use client";

import { gsap } from "gsap";
import { useEffect, useRef, useState } from "react";

import { createBrowserSupabaseClient } from "@/lib/supabase/client";

export type AgentLogRow = {
  id: number | string;
  job_id: string;
  video_id: string | null;
  agent: "orchestrator" | "research" | "metadata" | "download" | "upload";
  step: "status" | "tool_call" | "reasoning" | "fallback" | "error";
  message: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
};

const AGENT_COLOR: Record<AgentLogRow["agent"], string> = {
  orchestrator: "bg-blue-500/20 text-blue-200",
  research: "bg-purple-500/20 text-purple-200",
  metadata: "bg-amber-500/20 text-amber-200",
  download: "bg-emerald-500/20 text-emerald-200",
  upload: "bg-pink-500/20 text-pink-200",
};

const STEP_ICON: Record<AgentLogRow["step"], string> = {
  status: "●",
  tool_call: "⚒",
  reasoning: "∿",
  fallback: "↪",
  error: "✕",
};

/**
 * Subscribes to agent_logs via Supabase Realtime and renders a live timeline.
 * Uses GSAP for new-row entrance choreography and streaming-token flicker on
 * consecutive `reasoning` rows from the same agent.
 */
export function AgentLogTimeline({ jobId }: { jobId: string }) {
  const [rows, setRows] = useState<AgentLogRow[]>([]);
  const listRef = useRef<HTMLOListElement>(null);

  // Initial fetch + realtime subscription
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
      if (active && data) {
        setRows(data as AgentLogRow[]);
      }
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

  // Animate the newest row with GSAP
  useEffect(() => {
    if (!listRef.current) return;
    const items = listRef.current.querySelectorAll<HTMLLIElement>("li");
    const latest = items[items.length - 1];
    if (!latest) return;
    gsap.fromTo(
      latest,
      { opacity: 0, y: 6, filter: "blur(2px)" },
      { opacity: 1, y: 0, filter: "blur(0px)", duration: 0.25, ease: "power2.out" },
    );
    latest.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [rows.length]);

  if (rows.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-border/60 px-4 py-10 text-center text-sm text-muted-foreground">
        Waiting for the agents to start…
      </div>
    );
  }

  return (
    <ol ref={listRef} className="space-y-1 font-mono text-xs">
      {rows.map((row) => (
        <li
          key={row.id}
          className="flex items-start gap-3 rounded px-2 py-1 hover:bg-muted/40"
        >
          <span
            className={`inline-flex min-w-[88px] items-center gap-1 rounded px-1.5 py-0.5 ${AGENT_COLOR[row.agent] ?? ""}`}
            title={row.step}
          >
            <span aria-hidden>{STEP_ICON[row.step] ?? "·"}</span>
            <span className="uppercase tracking-wide">{row.agent}</span>
          </span>
          <span
            className={
              row.step === "error"
                ? "flex-1 whitespace-pre-wrap text-red-300"
                : row.step === "fallback"
                  ? "flex-1 whitespace-pre-wrap text-amber-300"
                  : "flex-1 whitespace-pre-wrap"
            }
          >
            {row.message}
          </span>
          <time className="text-[10px] text-muted-foreground">
            {new Date(row.created_at).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            })}
          </time>
        </li>
      ))}
    </ol>
  );
}

export default AgentLogTimeline;
