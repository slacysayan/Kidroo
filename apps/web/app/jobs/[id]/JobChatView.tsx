"use client";

import { Link as LinkIcon, Search } from "lucide-react";
import { useMemo, useState, useTransition } from "react";
import { toast } from "sonner";

import { AgentLogRail } from "@/components/AgentLogRail";
import { AgentMessage } from "@/components/chat/AgentMessage";
import { UserMessage } from "@/components/chat/UserMessage";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { ScheduleConfirmCard } from "@/components/ScheduleConfirmCard";
import { VideoSelectionCard } from "@/components/VideoSelectionCard";
import type { ChannelRow } from "@/hooks/useChannels";
import { type VideoRow, useVideos } from "@/hooks/useVideos";
import { createBrowserSupabaseClient } from "@/lib/supabase/client";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type JobChatViewProps = {
  job: {
    id: string;
    source_url: string;
    status: string;
    schedule?: { per_day?: number; start_date?: string } | null;
    channel_id?: string | null;
  };
  userEmail?: string | null;
  initialVideos: VideoRow[];
  channels: ChannelRow[];
};

/**
 * Chat-style job view. Structure:
 *   [user] pasted URL
 *   [agent] scanning / scan-trigger
 *   [agent] video selection card
 *   [agent] schedule confirmation card with live status badges
 *   [agent log rail] at the bottom
 */
export function JobChatView({
  job,
  userEmail,
  initialVideos,
  channels,
}: JobChatViewProps) {
  const { videos } = useVideos(job.id, initialVideos);
  const [scanPending, startScan] = useTransition();
  const [submitted, setSubmitted] = useState(
    job.status === "running" || job.status === "complete",
  );

  const selectedChannel = useMemo(
    () => channels.find((c) => c.id === job.channel_id) ?? null,
    [channels, job.channel_id],
  );

  const showSelectionCard = videos.length > 0 && !submitted;
  const showConfirmCard =
    submitted || videos.some((v) => v.status !== "queued");
  const showScanTrigger = videos.length === 0 && job.status !== "scanning";

  async function triggerScan() {
    const supabase = createBrowserSupabaseClient();
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (!token) {
      toast.error("please sign in again");
      return;
    }
    startScan(async () => {
      const res = await fetch(`${API_BASE}/jobs/${job.id}/scan`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          authorization: `Bearer ${token}`,
        },
      });
      if (!res.ok) {
        toast.error(`scan failed (${res.status})`);
        return;
      }
      toast.success("scanning source — videos will appear below");
    });
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-4 py-8 sm:px-6">
      <UserMessage email={userEmail}>
        <div className="flex items-start gap-2">
          <LinkIcon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
          <span className="break-all">{job.source_url}</span>
        </div>
      </UserMessage>

      <AgentMessage label="Orchestrator">
        I'll scan that source and pull out every video so you can pick what to
        publish.
      </AgentMessage>

      {showScanTrigger ? (
        <AgentMessage label="Research · download" variant="inline-card">
          <Card>
            <CardHeader>
              <CardTitle>Ready to scan</CardTitle>
              <p className="text-[11px] text-muted-foreground">
                We'll use <code className="font-mono">yt-dlp</code> to fetch
                metadata without downloading the video bytes.
              </p>
            </CardHeader>
            <CardContent>
              <Button
                onClick={triggerScan}
                disabled={scanPending}
                className="gap-2"
                size="sm"
              >
                <Search className="h-3.5 w-3.5" aria-hidden />
                {scanPending ? "Scanning…" : "Scan source"}
              </Button>
            </CardContent>
          </Card>
        </AgentMessage>
      ) : null}

      {videos.length === 0 && job.status === "scanning" ? (
        <AgentMessage label="Download">
          <span className="font-mono text-xs">
            scanning… videos will stream in as they're discovered.
          </span>
        </AgentMessage>
      ) : null}

      {showSelectionCard ? (
        <AgentMessage label="Orchestrator" variant="inline-card">
          <VideoSelectionCard
            jobId={job.id}
            sourceLabel={new URL(job.source_url).hostname}
            videos={videos}
            channels={channels}
            onSubmitted={() => setSubmitted(true)}
          />
        </AgentMessage>
      ) : null}

      {showConfirmCard ? (
        <AgentMessage label="Upload" variant="inline-card">
          <ScheduleConfirmCard
            videos={videos}
            channelName={selectedChannel?.name}
            schedule={job.schedule ?? undefined}
          />
        </AgentMessage>
      ) : null}

      <section className="space-y-2">
        <header className="flex items-center justify-between">
          <h2 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Agent timeline
          </h2>
          <span className="font-mono text-[10px] text-muted-foreground">
            job {job.id.slice(0, 8)} · {job.status}
          </span>
        </header>
        <AgentLogRail jobId={job.id} />
      </section>
    </div>
  );
}
