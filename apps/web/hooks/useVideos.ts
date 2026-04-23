"use client";

import { useEffect, useState } from "react";

import type { VideoStatus } from "@/lib/agents/constants";
import { createBrowserSupabaseClient } from "@/lib/supabase/client";

export type VideoRow = {
  id: string;
  job_id: string;
  source_url: string;
  source_video_id: string | null;
  title: string | null;
  duration_secs: number | null;
  status: VideoStatus;
  yt_video_id: string | null;
  publish_at: string | null;
  error_message: string | null;
};

/**
 * Live per-job videos. Refetches on INSERT/UPDATE via Realtime so that
 * per-video status badges transition queued → scheduled as the pipeline runs.
 */
export function useVideos(
  jobId: string,
  initial: VideoRow[] = [],
): { videos: VideoRow[] } {
  const [videos, setVideos] = useState<VideoRow[]>(initial);

  useEffect(() => {
    const supabase = createBrowserSupabaseClient();
    let active = true;

    (async () => {
      const { data } = await supabase
        .from("videos")
        .select("*")
        .eq("job_id", jobId)
        .order("created_at", { ascending: true });
      if (!active) return;
      if (data) setVideos(data as VideoRow[]);
    })();

    const channel = supabase
      .channel(`videos:${jobId}`)
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "videos",
          filter: `job_id=eq.${jobId}`,
        },
        (payload) => {
          setVideos((prev) => {
            if (payload.eventType === "INSERT") {
              const row = payload.new as VideoRow;
              if (prev.some((v) => v.id === row.id)) return prev;
              return [...prev, row];
            }
            if (payload.eventType === "UPDATE") {
              const row = payload.new as VideoRow;
              return prev.map((v) => (v.id === row.id ? row : v));
            }
            if (payload.eventType === "DELETE") {
              const row = payload.old as { id: string };
              return prev.filter((v) => v.id !== row.id);
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
  }, [jobId]);

  return { videos };
}
