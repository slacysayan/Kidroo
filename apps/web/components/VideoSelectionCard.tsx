"use client";

import { useLayoutEffect, useMemo, useRef, useState, useTransition } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import { Checkbox } from "@/components/ui/Checkbox";
import { ScrollArea } from "@/components/ui/ScrollArea";
import { Select } from "@/components/ui/Select";
import { Separator } from "@/components/ui/Separator";
import type { ChannelRow } from "@/hooks/useChannels";
import type { VideoRow } from "@/hooks/useVideos";
import { timeline } from "@/lib/gsap";
import { createBrowserSupabaseClient } from "@/lib/supabase/client";
import { cn } from "@/lib/utils";

export type VideoSelectionCardProps = {
  jobId: string;
  sourceLabel?: string;
  videos: VideoRow[];
  channels: ChannelRow[];
  onSubmitted?: () => void;
  className?: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function fmtDuration(secs: number | null): string {
  if (!secs) return "—";
  const m = Math.floor(secs / 60);
  const s = (secs % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

function defaultStart(): string {
  // 1h from now, "YYYY-MM-DDTHH:mm" (datetime-local expects local)
  const d = new Date(Date.now() + 60 * 60 * 1000);
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/**
 * Inline video-selection card rendered in the chat when a scan completes.
 * Submits `POST /jobs/:id/start` with selected video ids + channel + schedule.
 *
 * Layout matches docs/UI_SPEC.md §Video selection card.
 */
export function VideoSelectionCard({
  jobId,
  sourceLabel,
  videos,
  channels,
  onSubmitted,
  className,
}: VideoSelectionCardProps) {
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(videos.map((v) => v.id)),
  );
  const [channelId, setChannelId] = useState(channels[0]?.id ?? "");
  const [perDay, setPerDay] = useState(2);
  const [startDate, setStartDate] = useState(defaultStart);
  const [pending, startTransition] = useTransition();

  const listRef = useRef<HTMLUListElement>(null);
  const selectedIds = useMemo(() => Array.from(selected), [selected]);
  const canSubmit = selectedIds.length > 0 && Boolean(channelId);

  useLayoutEffect(() => {
    if (!listRef.current) return;
    let cancelled = false;
    (async () => {
      const tl = await timeline();
      if (!tl || cancelled) return;
      tl.from(listRef.current?.querySelectorAll("[data-video-row]") ?? [], {
        y: 6,
        opacity: 0,
        duration: 0.2,
        ease: "power2.out",
        stagger: 0.02,
      });
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  function toggleOne(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    setSelected((prev) =>
      prev.size === videos.length ? new Set() : new Set(videos.map((v) => v.id)),
    );
  }

  async function submit() {
    if (!canSubmit) return;
    const supabase = createBrowserSupabaseClient();
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (!token) {
      toast.error("please sign in again");
      return;
    }
    startTransition(async () => {
      const res = await fetch(`${API_BASE}/jobs/${jobId}/start`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          channel_id: channelId,
          video_ids: selectedIds,
          per_day: perDay,
          start_date: new Date(startDate).toISOString(),
        }),
      });
      if (!res.ok) {
        toast.error(`start failed (${res.status})`);
        return;
      }
      toast.success("pipeline running — watch the timeline");
      onSubmitted?.();
    });
  }

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader className="flex-row items-center justify-between">
        <div className="space-y-0.5">
          <CardTitle>
            Found {videos.length} video{videos.length === 1 ? "" : "s"}
            {sourceLabel ? (
              <span className="ml-1 font-mono text-xs text-muted-foreground">
                on {sourceLabel}
              </span>
            ) : null}
          </CardTitle>
          <p className="text-[11px] text-muted-foreground">
            Pick what to publish. You can refine the schedule below.
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={toggleAll}>
          {selected.size === videos.length ? "Clear" : "Select all"}
        </Button>
      </CardHeader>

      <CardContent className="p-0">
        <ScrollArea className="max-h-[420px]">
          <ul ref={listRef} className="divide-y divide-border/40 px-1">
            {videos.map((v) => {
              const isSel = selected.has(v.id);
              return (
                <li
                  key={v.id}
                  data-video-row
                  className="flex items-center gap-3 px-3 py-2 text-sm hover:bg-muted/40"
                >
                  <label className="flex flex-1 cursor-pointer items-center gap-3">
                    <Checkbox
                      checked={isSel}
                      onChange={() => toggleOne(v.id)}
                      aria-label={v.title ?? "video"}
                    />
                    <span className="flex-1 truncate">
                      {v.title ?? v.source_video_id ?? v.source_url}
                    </span>
                  </label>
                  <span className="font-mono text-[11px] text-muted-foreground">
                    {fmtDuration(v.duration_secs)}
                  </span>
                </li>
              );
            })}
          </ul>
        </ScrollArea>
      </CardContent>

      <Separator />

      <CardContent className="grid gap-3 sm:grid-cols-3">
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-muted-foreground">Target channel</span>
          <Select
            value={channelId}
            onChange={(e) => setChannelId(e.target.value)}
            disabled={channels.length === 0}
          >
            {channels.length === 0 ? (
              <option value="">No channels connected</option>
            ) : (
              channels.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))
            )}
          </Select>
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-muted-foreground">Per day</span>
          <Select
            value={String(perDay)}
            onChange={(e) => setPerDay(Number(e.target.value))}
          >
            {[1, 2, 3, 4, 5, 6].map((n) => (
              <option key={n} value={n}>
                {n} / day
              </option>
            ))}
          </Select>
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-muted-foreground">Start (local)</span>
          <input
            type="datetime-local"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="flex h-9 w-full rounded-md border border-border bg-background px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/70"
          />
        </label>
      </CardContent>

      <CardFooter>
        <span className="mr-auto text-xs text-muted-foreground">
          {selected.size} of {videos.length} selected
        </span>
        <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>
          Cancel
        </Button>
        <Button
          size="sm"
          disabled={!canSubmit || pending}
          onClick={submit}
        >
          {pending ? "Starting…" : "Proceed →"}
        </Button>
      </CardFooter>
    </Card>
  );
}
