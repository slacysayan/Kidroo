import { notFound, redirect } from "next/navigation";

import AgentLogTimeline from "@/components/AgentLogTimeline";
import Header from "@/components/Header";
import JobActions from "./JobActions";
import { createServerSupabaseClient } from "@/lib/supabase/server";

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

  const { data: job } = await supabase
    .from("jobs")
    .select("*")
    .eq("id", id)
    .maybeSingle();
  if (!job) notFound();

  const [{ data: videos }, { data: channels }] = await Promise.all([
    supabase
      .from("videos")
      .select("*")
      .eq("job_id", id)
      .order("created_at", { ascending: true }),
    supabase
      .from("channels")
      .select("id, name, composio_entity_id, connected")
      .eq("connected", true),
  ]);

  return (
    <div className="flex min-h-screen flex-col">
      <Header email={user.email} />

      <main className="mx-auto w-full max-w-5xl flex-1 space-y-6 px-6 py-10">
        <header className="space-y-1">
          <h1 className="break-all text-lg font-semibold">{job.source_url}</h1>
          <p className="font-mono text-xs text-muted-foreground">
            status={job.status} · job_id={job.id}
          </p>
        </header>

        <JobActions
          jobId={job.id}
          status={job.status as string}
          videos={videos ?? []}
          channels={channels ?? []}
        />

        <section className="space-y-2">
          <h2 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
            Agent timeline
          </h2>
          <div className="rounded-md border border-border bg-muted/20 p-3">
            <AgentLogTimeline jobId={job.id} />
          </div>
        </section>
      </main>
    </div>
  );
}
