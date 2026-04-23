/**
 * Single source of truth for agent + status display metadata.
 * Consumed by `AgentLogRail`, `StatusBadge`, and the command menu.
 */

export type AgentName =
  | "orchestrator"
  | "research"
  | "metadata"
  | "download"
  | "upload";

export type AgentStep =
  | "status"
  | "tool_call"
  | "reasoning"
  | "fallback"
  | "error";

export const AGENT_ORDER: readonly AgentName[] = [
  "orchestrator",
  "research",
  "metadata",
  "download",
  "upload",
] as const;

export const AGENT_PILL: Record<AgentName, { bg: string; fg: string; label: string }> = {
  orchestrator: {
    bg: "bg-violet-500/15",
    fg: "text-violet-300",
    label: "orchestrator",
  },
  research: {
    bg: "bg-sky-500/15",
    fg: "text-sky-300",
    label: "research",
  },
  metadata: {
    bg: "bg-amber-500/15",
    fg: "text-amber-300",
    label: "metadata",
  },
  download: {
    bg: "bg-teal-500/15",
    fg: "text-teal-300",
    label: "download",
  },
  upload: {
    bg: "bg-rose-500/15",
    fg: "text-rose-300",
    label: "upload",
  },
};

export const STEP_GLYPH: Record<AgentStep, string> = {
  status: "●",
  tool_call: "⚒",
  reasoning: "∿",
  fallback: "↪",
  error: "✕",
};

export type VideoStatus =
  | "queued"
  | "fetching"
  | "downloading"
  | "generating"
  | "uploading"
  | "scheduled"
  | "failed";

export const VIDEO_STATUS_ORDER: readonly VideoStatus[] = [
  "queued",
  "fetching",
  "downloading",
  "generating",
  "uploading",
  "scheduled",
] as const;
