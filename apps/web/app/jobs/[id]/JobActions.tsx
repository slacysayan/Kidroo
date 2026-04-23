"use client";

import { useMemo, useState, useTransition } from "react";
import { toast } from "sonner";

import { createBrowserSupabaseClient } from "@/lib/supabase/client";

type VideoRow = {
  id: string;
  source_video_id: string | null;
  title: string | null;
  duration_secs: number | null;
  status: string;
};
type ChannelRow = {
  id: string;
  name: string;
  composio_entity_id: string;
  connected: boolean;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function callApi(
  path: string,
  token: string,
  body?: unknown,
): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    method: body ? "POST" : "POST",
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${token}`,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
}

export default function JobActions({
  jobId,
  status,
  videos,
  channels,
}: {
  jobId: string;
  status: string;
  videos: VideoRow[];
  channels: ChannelRow[];
}) {
  const [pending, startTransition] = useTransition();
  const [selectedChannel, setSelectedChannel] = useState(
    channels[0]?.id ?? "",
  );
  const [perDay, setPerDay] = useState(1);
  const [startDate, setStartDate] = useState(() =>
    new Date(Date.now() + 60 * 60 * 1000).toISOString().slice(0, 16),
  );
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(videos.map((v) => v.id)),
  );

  const canScan = videos.length === 0 && status === "pending";
  const canStart = videos.length > 0 && status !== "running" && status !== "complete";
  const selectedCount = selected.size;

  const selectedIds = useMemo(() => Array.from(selected), [selected]);

  async function token(): Promise<string | null> {
    const supabase = createBrowserSupabaseClient();
    const { data } = await supabase.auth.getSession();
    return data.session?.access_token ?? null;
  }

  function runScan() {
    startTransition(async () => {
      const t = await token();
      if (!t) {
        toast.error("please sign in again");
        return;
      }
      const res = await callApi(`/jobs/${jobId}/scan`, t);
      if (!res.ok) {
        toast.error(`scan failed (${res.status})`);
        return;
      }
      toast.success("scan started — videos will appear below");
      // Realtime will refresh the videos list.
    });
  }

  function runStart() {
    if (!selectedChannel) {
      toast.error("select a channel");
      return;
    }
    if (selectedIds.length === 0) {
      toast.error("select at least one video");
      return;
    }
    startTransition(async () => {
      const t = await token();
      if (!t) {
        toast.error("please sign in again");
        return;
      }
      const res = await callApi(`/jobs/${jobId}/start`, t, {
        channel_id: selectedChannel,
        video_ids: selectedIds,
        per_day: perDay,
        start_date: new Date(startDate).toISOString(),
      });
      if (!res.ok) {
        toast.error(`start failed (${res.status})`);
        return;
      }
      toast.success("pipeline running — watch the timeline");
    });
  }

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <section className="space-y-3 rounded-md border border-border bg-muted/10 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={!canScan || pending}
          onClick={runScan}
          className="rounded-md border border-border px-3 py-1.5 text-xs disabled:opacity-40"
        >
          {pending ? "…" : "1. Scan source"}
        </button>
        <span className="text-xs text-muted-foreground">
          {videos.length} video{videos.length === 1 ? "" : "s"} detected
        </span>
      </div>

      {videos.length > 0 ? (
        <>
          <div className="max-h-56 overflow-auto rounded-md border border-border/60">
            <table className="w-full text-xs">
              <thead className="bg-muted/40 font-mono uppercase tracking-wide">
                <tr>
                  <th className="p-2 text-left">pick</th>
                  <th className="p-2 text-left">title</th>
                  <th className="p-2 text-left">duration</th>
                  <th className="p-2 text-left">status</th>
                </tr>
              </thead>
              <tbody>
                {videos.map((v) => (
                  <tr key={v.id} className="border-t border-border/40">
                    <td className="p-2">
                      <input
                        type="checkbox"
                        checked={selected.has(v.id)}
                        onChange={() => toggle(v.id)}
                      />
                    </td>
                    <td className="max-w-xs truncate p-2">{v.title ?? v.source_video_id}</td>
                    <td className="p-2 font-mono text-muted-foreground">
                      {v.duration_secs ?? "—"}s
                    </td>
                    <td className="p-2 font-mono text-muted-foreground">{v.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-end gap-3 text-xs">
            <label className="flex flex-col gap-1">
              <span className="text-muted-foreground">channel</span>
              <select
                value={selectedChannel}
                onChange={(e) => setSelectedChannel(e.target.value)}
                className="rounded border border-border bg-background px-2 py-1.5"
              >
                {channels.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-muted-foreground">per day</span>
              <input
                type="number"
                min={1}
                max={6}
                value={perDay}
                onChange={(e) => setPerDay(Number(e.target.value))}
                className="w-16 rounded border border-border bg-background px-2 py-1.5"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-muted-foreground">start (UTC)</span>
              <input
                type="datetime-local"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="rounded border border-border bg-background px-2 py-1.5"
              />
            </label>
            <button
              type="button"
              disabled={!canStart || pending}
              onClick={runStart}
              className="rounded-md bg-foreground px-3 py-1.5 text-background disabled:opacity-40"
            >
              2. Start pipeline ({selectedCount})
            </button>
          </div>
        </>
      ) : null}
    </section>
  );
}
