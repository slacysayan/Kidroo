"use client";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import { ScrollArea } from "@/components/ui/ScrollArea";
import { StatusBadge } from "@/components/StatusBadge";
import type { VideoRow } from "@/hooks/useVideos";
import type { VideoStatus } from "@/lib/agents/constants";
import { cn } from "@/lib/utils";

export type ScheduleConfirmCardProps = {
  videos: VideoRow[];
  channelName?: string;
  schedule?: { per_day?: number; start_date?: string };
  className?: string;
};

function fmtPublish(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Post-submit card that lists each selected video with its current live status.
 * Status badge is Flip-animated on change (see StatusBadge).
 */
export function ScheduleConfirmCard({
  videos,
  channelName,
  schedule,
  className,
}: ScheduleConfirmCardProps) {
  const scheduledCount = videos.filter((v) => v.status === "scheduled").length;
  const failedCount = videos.filter((v) => v.status === "failed").length;
  const running = videos.length - scheduledCount - failedCount;

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader>
        <CardTitle>
          Publishing {videos.length} video{videos.length === 1 ? "" : "s"}
          {channelName ? ` to ${channelName}` : ""}
        </CardTitle>
        <p className="text-[11px] text-muted-foreground">
          {schedule?.per_day ? (
            <>
              {schedule.per_day} per day
              {schedule.start_date
                ? ` · starting ${new Date(schedule.start_date).toLocaleDateString()}`
                : ""}
            </>
          ) : null}
        </p>
        <div className="mt-2 flex items-center gap-3 font-mono text-[11px] text-muted-foreground">
          <span>running {running}</span>
          <span>· scheduled {scheduledCount}</span>
          {failedCount > 0 ? (
            <span className="text-red-300">· failed {failedCount}</span>
          ) : null}
        </div>
      </CardHeader>

      <CardContent className="p-0">
        <ScrollArea className="max-h-[420px]">
          <ul className="divide-y divide-border/40">
            {videos.map((v) => (
              <li
                key={v.id}
                className="flex items-center gap-3 px-4 py-2.5 text-sm"
              >
                <span className="flex-1 truncate">
                  {v.title ?? v.source_video_id ?? v.source_url}
                </span>
                <span className="hidden font-mono text-[11px] text-muted-foreground sm:inline">
                  {fmtPublish(v.publish_at)}
                </span>
                <StatusBadge status={v.status as VideoStatus} />
              </li>
            ))}
          </ul>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
