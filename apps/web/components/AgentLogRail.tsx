"use client";

import { useLayoutEffect, useRef } from "react";

import {
  AGENT_PILL,
  STEP_GLYPH,
  type AgentName,
} from "@/lib/agents/constants";
import { animate, autoScrollToBottom } from "@/lib/gsap";
import { cn } from "@/lib/utils";
import { type AgentLogRow, useAgentLogs } from "@/hooks/useAgentLogs";
import { ScrollArea } from "@/components/ui/ScrollArea";

export type AgentLogRailProps = {
  jobId: string;
  className?: string;
};

/**
 * Live agent-log rail. Rows stream in over Supabase Realtime, each entering
 * with a GSAP fromTo slide-up + blur-off. Auto-scrolls iff the user is within
 * 80 px of the bottom. `prefers-reduced-motion` collapses all durations to 0.
 *
 * See docs/UI_SPEC.md "Agent log feed" and .agents/skills/gsap/SKILL.md.
 */
export function AgentLogRail({ jobId, className }: AgentLogRailProps) {
  const { rows, loading } = useAgentLogs(jobId);
  const listRef = useRef<HTMLOListElement>(null);
  const animatedIds = useRef<Set<string | number>>(new Set());

  // biome-ignore lint/correctness/useExhaustiveDependencies: rows.length is the trigger; we inspect DOM, not rows array contents.
  useLayoutEffect(() => {
    if (!listRef.current) return;
    const items = listRef.current.querySelectorAll<HTMLLIElement>("li[data-log-row]");
    const latest = items[items.length - 1];
    if (!latest) return;
    const id = latest.dataset.logId;
    if (!id || animatedIds.current.has(id)) return;
    animatedIds.current.add(id);
    void animate(
      latest,
      { y: 8, opacity: 0, filter: "blur(2px)" },
      {
        y: 0,
        opacity: 1,
        filter: "blur(0px)",
        duration: 0.22,
        ease: "power2.out",
      },
    );
    void autoScrollToBottom(listRef.current);
  }, [rows.length]);

  if (loading && rows.length === 0) {
    return (
      <div
        className={cn(
          "flex h-40 items-center justify-center rounded-md border border-dashed border-border/60 px-4 text-center text-xs text-muted-foreground",
          className,
        )}
      >
        Waiting for the agents to start…
      </div>
    );
  }

  return (
    <ScrollArea
      className={cn(
        "max-h-[420px] rounded-md border border-border/60 bg-muted/10",
        className,
      )}
    >
      <ol
        ref={listRef}
        aria-live="polite"
        aria-relevant="additions"
        className="space-y-0.5 px-3 py-3 font-mono text-xs"
      >
        {rows.map((row) => (
          <AgentLogItem key={row.id} row={row} />
        ))}
      </ol>
    </ScrollArea>
  );
}

function AgentLogItem({ row }: { row: AgentLogRow }) {
  const agent = row.agent as AgentName;
  const pill = AGENT_PILL[agent] ?? AGENT_PILL.orchestrator;
  const glyph = STEP_GLYPH[row.step] ?? "·";
  const messageTone =
    row.step === "error"
      ? "text-red-300"
      : row.step === "fallback"
        ? "text-amber-300"
        : "text-foreground/90";

  return (
    <li
      data-log-row
      data-log-id={row.id}
      className="flex items-start gap-3 rounded px-2 py-1 hover:bg-muted/40"
    >
      <span
        className={cn(
          "inline-flex min-w-[96px] items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide",
          pill.bg,
          pill.fg,
        )}
        title={`${row.step}${row.metadata?.latency_ms ? ` · ${row.metadata.latency_ms as number}ms` : ""}`}
      >
        <span aria-hidden>{glyph}</span>
        <span>{pill.label}</span>
      </span>
      <span className={cn("flex-1 whitespace-pre-wrap break-words", messageTone)}>
        {row.message}
      </span>
      <time
        dateTime={row.created_at}
        className="shrink-0 text-[10px] text-muted-foreground/60"
      >
        {new Date(row.created_at).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        })}
      </time>
    </li>
  );
}
