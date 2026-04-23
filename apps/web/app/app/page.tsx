import { createServerSupabaseClient } from "@/lib/supabase/server";

/**
 * Main app screen (authenticated). Phase 1 stub — shows the connected channels
 * and a placeholder composer. Phase 4 replaces this with the real chat UI.
 */
export default async function AppPage() {
  const supabase = await createServerSupabaseClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { data: channels } = await supabase
    .from("channels")
    .select("id, name, composio_entity_id, created_at")
    .order("created_at", { ascending: false });

  return (
    <main className="mx-auto max-w-4xl space-y-8 px-6 py-10">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Kidroo</h1>
          <p className="text-sm text-muted-foreground">Signed in as {user?.email}</p>
        </div>
        <a
          href="/channels/connect"
          className="rounded-md bg-foreground px-4 py-2 text-sm text-background hover:opacity-90"
        >
          Connect a YouTube channel
        </a>
      </header>

      <section className="space-y-2">
        <h2 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
          Channels
        </h2>
        {channels && channels.length > 0 ? (
          <ul className="divide-y divide-border rounded-md border border-border">
            {channels.map((c) => (
              <li key={c.id} className="flex items-center justify-between px-4 py-3">
                <div>
                  <div className="font-medium">{c.name}</div>
                  <div className="font-mono text-xs text-muted-foreground">
                    {c.composio_entity_id}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <div className="rounded-md border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
            No channels yet. Connect your first YouTube channel to get started.
          </div>
        )}
      </section>
    </main>
  );
}
