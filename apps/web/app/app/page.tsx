import { redirect } from "next/navigation";

import Header from "@/components/Header";
import JobComposer from "@/components/JobComposer";
import { createServerSupabaseClient } from "@/lib/supabase/server";

/**
 * Main app dashboard (authenticated). Shows connected channels, recent jobs,
 * and the paste-a-link composer.
 */
export default async function AppPage() {
  const supabase = await createServerSupabaseClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const [{ data: channels }, { data: jobs }] = await Promise.all([
    supabase
      .from("channels")
      .select("id, name, composio_entity_id, created_at, connected")
      .order("created_at", { ascending: false }),
    supabase
      .from("jobs")
      .select("id, source_url, status, created_at")
      .order("created_at", { ascending: false })
      .limit(10),
  ]);

  return (
    <div className="flex min-h-screen flex-col">
      <Header email={user.email} />

      <main className="mx-auto w-full max-w-4xl flex-1 space-y-10 px-6 py-10">
        <section className="space-y-3">
          <h1 className="text-xl font-semibold tracking-tight">Start a new upload</h1>
          <JobComposer />
        </section>

        <section className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
              Channels
            </h2>
            <a
              href="/channels/connect"
              className="text-xs underline-offset-2 hover:underline"
            >
              connect a YouTube channel →
            </a>
          </div>
          {channels && channels.length > 0 ? (
            <ul className="divide-y divide-border rounded-md border border-border">
              {channels.map((c) => (
                <li
                  key={c.id}
                  className="flex items-center justify-between px-4 py-3"
                >
                  <div>
                    <div className="font-medium">{c.name}</div>
                    <div className="font-mono text-xs text-muted-foreground">
                      {c.composio_entity_id}
                    </div>
                  </div>
                  <span
                    className={
                      c.connected
                        ? "text-xs text-emerald-400"
                        : "text-xs text-amber-400"
                    }
                  >
                    {c.connected ? "connected" : "pending"}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="rounded-md border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
              No channels yet. Connect your first YouTube channel to get started.
            </div>
          )}
        </section>

        <section className="space-y-2">
          <h2 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
            Recent jobs
          </h2>
          {jobs && jobs.length > 0 ? (
            <ul className="divide-y divide-border rounded-md border border-border">
              {jobs.map((j) => (
                <li key={j.id} className="flex items-center justify-between px-4 py-3">
                  <a
                    href={`/jobs/${j.id}`}
                    className="truncate text-sm hover:underline"
                  >
                    {j.source_url}
                  </a>
                  <span className="font-mono text-xs text-muted-foreground">
                    {j.status}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="rounded-md border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
              No jobs yet.
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
