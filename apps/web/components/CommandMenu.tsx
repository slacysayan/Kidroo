"use client";

import { Command } from "cmdk";
import { CalendarCheck, Link as LinkIcon, Plus, Radio, Settings } from "lucide-react";
import type { Route } from "next";
import { useRouter } from "next/navigation";

import { Dialog } from "@/components/ui/Dialog";
import type { ChannelRow } from "@/hooks/useChannels";

export type CommandMenuProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  channels?: ChannelRow[];
};

/**
 * ⌘K command palette — quick navigation between channels, new job,
 * settings, and the command shortcuts. Keyboard driven via `cmdk`.
 */
export function CommandMenu({ open, onOpenChange, channels = [] }: CommandMenuProps) {
  const router = useRouter();

  function go(href: string) {
    onOpenChange(false);
    router.push(href as Route);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange} className="max-w-lg p-0">
      <Command
        label="Command menu"
        className="flex flex-col overflow-hidden rounded-lg"
      >
        <Command.Input
          placeholder="Type a command, search channels…"
          className="w-full border-b border-border bg-transparent px-4 py-3 text-sm outline-none placeholder:text-muted-foreground"
        />
        <Command.List className="max-h-80 overflow-auto p-2 text-sm">
          <Command.Empty className="px-3 py-6 text-center text-xs text-muted-foreground">
            No matches.
          </Command.Empty>

          <Command.Group heading="Actions" className="px-1 text-xs text-muted-foreground">
            <Command.Item
              onSelect={() => go("/app")}
              className="flex cursor-pointer items-center gap-3 rounded-md px-3 py-2 text-foreground aria-selected:bg-muted"
            >
              <LinkIcon className="h-4 w-4" aria-hidden />
              Start a new upload
            </Command.Item>
            <Command.Item
              onSelect={() => go("/channels/connect")}
              className="flex cursor-pointer items-center gap-3 rounded-md px-3 py-2 text-foreground aria-selected:bg-muted"
            >
              <Plus className="h-4 w-4" aria-hidden />
              Connect a YouTube channel
            </Command.Item>
            <Command.Item
              onSelect={() => go("/app#queue")}
              className="flex cursor-pointer items-center gap-3 rounded-md px-3 py-2 text-foreground aria-selected:bg-muted"
            >
              <CalendarCheck className="h-4 w-4" aria-hidden />
              Jump to queue
            </Command.Item>
            <Command.Item
              onSelect={() => go("/app")}
              className="flex cursor-pointer items-center gap-3 rounded-md px-3 py-2 text-foreground aria-selected:bg-muted"
            >
              <Settings className="h-4 w-4" aria-hidden />
              Settings
            </Command.Item>
          </Command.Group>

          {channels.length > 0 ? (
            <Command.Group
              heading="Channels"
              className="mt-1 px-1 text-xs text-muted-foreground"
            >
              {channels.map((c) => (
                <Command.Item
                  key={c.id}
                  value={`${c.name} ${c.composio_entity_id}`}
                  onSelect={() => go("/app")}
                  className="flex cursor-pointer items-center gap-3 rounded-md px-3 py-2 text-foreground aria-selected:bg-muted"
                >
                  <Radio
                    className={
                      c.connected
                        ? "h-4 w-4 text-emerald-400"
                        : "h-4 w-4 text-muted-foreground"
                    }
                    aria-hidden
                  />
                  <span className="flex-1 truncate">{c.name}</span>
                  <span className="font-mono text-[10px] text-muted-foreground">
                    {c.composio_entity_id}
                  </span>
                </Command.Item>
              ))}
            </Command.Group>
          ) : null}
        </Command.List>
      </Command>
    </Dialog>
  );
}
