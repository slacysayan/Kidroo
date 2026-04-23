import { redirect } from "next/navigation";

import { Header } from "@/components/Header";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import { ConnectChannelForm } from "./ConnectChannelForm";

/**
 * "Connect a YouTube channel" screen.
 *
 * Phase 1 UX: the user names the channel + picks a Composio entity id (alias).
 * Phase 2 adds the actual Composio OAuth hop — we create a Composio connected
 * account via the backend and link the channel row to the returned entity.
 */
export default async function ConnectChannelPage() {
  const supabase = await createServerSupabaseClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return (
    <div className="flex min-h-screen flex-col">
      <Header email={user.email} />
      <main className="mx-auto w-full max-w-xl flex-1 space-y-6 px-6 py-10">
        <header className="space-y-1">
          <h1 className="text-xl font-semibold">Connect a YouTube channel</h1>
          <p className="text-sm text-muted-foreground">
            Kidroo uses Composio to hold the OAuth tokens for each of your
            YouTube channels. Give the channel a friendly name and an alias
            (used as the Composio entity id).
          </p>
        </header>
        <ConnectChannelForm userId={user.id} />
      </main>
    </div>
  );
}
