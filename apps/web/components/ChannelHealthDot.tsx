import { cn } from "@/lib/utils";

export type ChannelHealthDotProps = {
  connected: boolean;
  className?: string;
};

/**
 * OAuth health indicator — green = healthy, grey = expired/pending.
 * Colour is paired with an `aria-label` so it never carries meaning alone.
 */
export function ChannelHealthDot({ connected, className }: ChannelHealthDotProps) {
  return (
    <span
      role="status"
      aria-label={connected ? "OAuth healthy" : "OAuth expired or pending"}
      className={cn(
        "inline-flex h-2 w-2 shrink-0 rounded-full",
        connected
          ? "bg-emerald-400 shadow-[0_0_8px_rgb(52_211_153/0.6)]"
          : "bg-muted-foreground/50",
        className,
      )}
    />
  );
}
