import Link from "next/link";
import { redirect } from "next/navigation";

import { ChatComposer } from "@/components/chat/ChatComposer";
import { Header } from "@/components/Header";
import { Sidebar } from "@/components/Sidebar";
import { Badge } from "@/components/ui/Badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import type { ChannelRow } from "@/hooks/useChannels";
import { createServerSupabaseClient } from "@/lib/supabase/server";

const JOB_STATUS_VARIANT: Record<
  string,
  "secondary" | "info" | "warning" | "success" | "destructive" | "default"
> = {
  pending: "secondary",
  scanning: "info",
  awaiting_selection: "warning",
  running: "info",
  complete: "success",
  failed: "destructive",
  cancelled: "secondary",
};

/**
 * Main dashboard (authenticated). Sidebar + hero "start a new upload"
 * composer + recent jobs. Entry point after login.
 */
export default async function AppPage() {
  const supabase = await createServerSupabaseClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const [channelsRes, jobsRes, activeCountRes, scheduledCountRes] = await Promise.all([
    supabase
      .from("channels")
      .select("id, name, composio_entity_id, connected, yt_channel_id, created_at")
      .order("created_at", { ascending: false }),
    supabase
      .from("jobs")
      .select("id, source_url, status, created_at")
      .order("created_at", { ascending: false })
      .limit(10),
    supabase
      .from("jobs")
      .select("id", { count: "exact", head: true })
      .in("status", ["pending", "scanning", "awaiting_selection", "running"]),
    supabase
      .from("videos")
      .select("id", { count: "exact", head: true })
      .eq("status", "scheduled"),
  ]);
  if (channelsRes.error) throw channelsRes.error;
  if (jobsRes.error) throw jobsRes.error;
  const channels = (channelsRes.data ?? []) as ChannelRow[];
  const jobs = jobsRes.data ?? [];

  return (
    <div className="flex min-h-screen">
      <Sidebar
        initialChannels={channels}
        queue={{
          activeJobs: activeCountRes.count ?? 0,
          scheduledVideos: scheduledCountRes.count ?? 0,
        }}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <Header email={user.email} />

        <main className="mx-auto w-full max-w-3xl flex-1 space-y-10 px-6 py-10">
          <section className="space-y-4 text-center sm:text-left">
            <div className="space-y-1">
              <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
                Start a new upload
              </h1>
              <p className="text-sm text-muted-foreground">
                Paste a YouTube channel, playlist, or video URL. Agents will
                handle research, metadata, downloading, and scheduled upload.
              </p>
            </div>
            <ChatComposer />
            <p className="text-[11px] text-muted-foreground">
              Press <kbd className="rounded border border-border px-1 font-mono text-[10px]">⌘K</kbd>{" "}
              any time for quick navigation.
            </p>
          </section>

          <section id="queue" className="space-y-3">
            <header className="flex items-end justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                Recent jobs
              </h2>
              <Link
                href="/channels/connect"
                className="text-xs text-muted-foreground underline-offset-2 hover:underline"
              >
                Connect a channel →
              </Link>
            </header>
            {jobs.length > 0 ? (
              <ul className="space-y-2">
                {jobs.map((j) => (
                  <li key={j.id}>
                    <Link
                      href={`/jobs/${j.id}`}
                      className="group block rounded-md border border-border/60 bg-background/60 px-4 py-3 transition-colors hover:border-foreground/30 hover:bg-muted/40"
                    >
                      <div className="flex items-center gap-3">
                        <span className="flex-1 truncate text-sm">
                          {j.source_url}
                        </span>
                        <Badge variant={JOB_STATUS_VARIANT[j.status] ?? "secondary"}>
                          {j.status}
                        </Badge>
                      </div>
                      <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                        {new Date(j.created_at).toLocaleString()}
                      </p>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <Card>
                <CardHeader>
                  <CardTitle>No jobs yet</CardTitle>
                  <CardDescription>
                    Start your first job by pasting a URL above.
                  </CardDescription>
                </CardHeader>
                <CardContent />
              </Card>
            )}
          </section>
        </main>
      </div>
    </div>
  );
}
