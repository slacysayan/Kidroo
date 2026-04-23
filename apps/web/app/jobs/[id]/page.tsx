import { notFound, redirect } from "next/navigation";

import { Header } from "@/components/Header";
import { Sidebar } from "@/components/Sidebar";
import type { ChannelRow } from "@/hooks/useChannels";
import type { VideoRow } from "@/hooks/useVideos";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import { JobChatView } from "./JobChatView";

export default async function JobPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const supabase = await createServerSupabaseClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: job, error: jobError } = await supabase
    .from("jobs")
    .select("*")
    .eq("id", id)
    .maybeSingle();
  if (jobError) throw jobError;
  if (!job) notFound();

  const [{ data: videos, error: videosError }, { data: channels, error: channelsError }] =
    await Promise.all([
      supabase
        .from("videos")
        .select("*")
        .eq("job_id", id)
        .order("created_at", { ascending: true }),
      supabase
        .from("channels")
        .select("id, name, composio_entity_id, connected, yt_channel_id")
        .order("created_at", { ascending: false }),
    ]);
  if (videosError) throw videosError;
  if (channelsError) throw channelsError;

  const [{ count: activeJobs }, { count: scheduledVideos }] = await Promise.all([
    supabase
      .from("jobs")
      .select("id", { count: "exact", head: true })
      .in("status", ["pending", "scanning", "awaiting_selection", "running"]),
    supabase
      .from("videos")
      .select("id", { count: "exact", head: true })
      .eq("status", "scheduled"),
  ]);

  return (
    <div className="flex min-h-screen">
      <Sidebar
        initialChannels={(channels ?? []) as ChannelRow[]}
        queue={{
          activeJobs: activeJobs ?? 0,
          scheduledVideos: scheduledVideos ?? 0,
        }}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header email={user.email} />
        <main className="flex-1 overflow-y-auto">
          <JobChatView
            job={{
              id: job.id,
              source_url: job.source_url,
              status: job.status,
              schedule: job.schedule,
              channel_id: job.channel_id,
            }}
            userEmail={user.email}
            initialVideos={(videos ?? []) as VideoRow[]}
            channels={((channels ?? []) as ChannelRow[]).filter((c) => c.connected)}
          />
        </main>
      </div>
    </div>
  );
}
