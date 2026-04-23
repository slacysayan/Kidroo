import { redirect } from "next/navigation";

import { Header } from "@/components/Header";
import { Sidebar } from "@/components/Sidebar";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/Card";
import type { ChannelRow } from "@/hooks/useChannels";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import { ConnectChannelForm } from "./ConnectChannelForm";

/**
 * "Connect a YouTube channel" screen.
 *
 * Phase 4 UX: chat-dashboard-consistent layout (sidebar + hero card).
 * Still creates a Supabase `channels` row with a Composio entity alias; the
 * actual OAuth hop happens via Composio's console for now.
 */
export default async function ConnectChannelPage() {
  const supabase = await createServerSupabaseClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const [channelsRes, activeCountRes, scheduledCountRes] = await Promise.all([
    supabase
      .from("channels")
      .select("id, name, composio_entity_id, connected, yt_channel_id, created_at")
      .order("created_at", { ascending: false }),
    supabase
      .from("jobs")
      .select("id", { count: "exact", head: true })
      .in("status", ["pending", "scanning", "awaiting_selection", "running"]),
    supabase
      .from("videos")
      .select("id", { count: "exact", head: true })
      .eq("status", "scheduled"),
  ]);
  const channels = (channelsRes.data ?? []) as ChannelRow[];

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
        <main className="mx-auto w-full max-w-xl flex-1 space-y-6 px-6 py-10">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Connect a YouTube channel</CardTitle>
              <CardDescription>
                Kidroo uses Composio to hold the OAuth tokens for each of your
                YouTube channels. Give the channel a friendly name and an alias
                (used as the Composio entity id).
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ConnectChannelForm userId={user.id} />
            </CardContent>
          </Card>
        </main>
      </div>
    </div>
  );
}
