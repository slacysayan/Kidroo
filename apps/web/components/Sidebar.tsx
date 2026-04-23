"use client";

import { Plus } from "lucide-react";
import Link from "next/link";

import { ChannelHealthDot } from "@/components/ChannelHealthDot";
import { CommandMenu } from "@/components/CommandMenu";
import { Button } from "@/components/ui/Button";
import { Separator } from "@/components/ui/Separator";
import { type ChannelRow, useChannels } from "@/hooks/useChannels";
import { useCommandMenu } from "@/hooks/useCommandMenu";

export type SidebarProps = {
  initialChannels?: ChannelRow[];
  queue?: { activeJobs: number; scheduledVideos: number };
};

/**
 * Left rail. Brand / channels (with live OAuth health dots) / queue summary /
 * ⌘K shortcut. Responsive: hidden on mobile in favor of a top header.
 */
export function Sidebar({ initialChannels = [], queue }: SidebarProps) {
  const { channels } = useChannels(initialChannels);
  const menu = useCommandMenu();

  return (
    <>
      <aside className="hidden w-[260px] shrink-0 flex-col border-r border-border/60 bg-muted/20 md:flex">
        <div className="flex items-baseline gap-2 px-5 py-4">
          <Link href="/app" className="flex items-baseline gap-2">
            <span className="text-base font-semibold tracking-tight">Kidroo</span>
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
              agentic YT pipeline
            </span>
          </Link>
        </div>
        <Separator />

        <nav className="flex-1 space-y-5 overflow-y-auto px-4 py-5 text-sm">
          <section className="space-y-2">
            <header className="flex items-center justify-between">
              <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Channels
              </h3>
              <Link
                href="/channels/connect"
                aria-label="Connect a channel"
                className="inline-flex items-center gap-1 rounded-md border border-border/60 px-1.5 py-0.5 text-[10px] text-muted-foreground hover:bg-muted"
              >
                <Plus className="h-3 w-3" aria-hidden />
                new
              </Link>
            </header>
            <ul className="space-y-1">
              {channels.length === 0 ? (
                <li className="rounded-md border border-dashed border-border/60 px-3 py-4 text-center text-[11px] text-muted-foreground">
                  No channels yet.
                </li>
              ) : (
                channels.map((c) => (
                  <li
                    key={c.id}
                    className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-muted"
                  >
                    <ChannelHealthDot connected={c.connected} />
                    <span className="flex-1 truncate">{c.name}</span>
                    <span className="font-mono text-[10px] text-muted-foreground">
                      {c.composio_entity_id}
                    </span>
                  </li>
                ))
              )}
            </ul>
          </section>

          <Separator />

          <section className="space-y-2">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Queue
            </h3>
            <dl className="space-y-1 text-[12px]">
              <div className="flex items-center justify-between">
                <dt className="text-muted-foreground">Active jobs</dt>
                <dd className="font-mono">{queue?.activeJobs ?? 0}</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-muted-foreground">Videos scheduled</dt>
                <dd className="font-mono">{queue?.scheduledVideos ?? 0}</dd>
              </div>
            </dl>
          </section>

          <Separator />

          <section className="space-y-2">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Quick actions
            </h3>
            <Button
              variant="outline"
              size="sm"
              onClick={menu.toggle}
              className="w-full justify-between font-normal"
            >
              Command menu
              <kbd className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                ⌘K
              </kbd>
            </Button>
          </section>
        </nav>
      </aside>

      <CommandMenu open={menu.open} onOpenChange={menu.setOpen} channels={channels} />
    </>
  );
}
