"use client";

import { cn } from "@/lib/utils";

export type TooltipProps = {
  label: React.ReactNode;
  side?: "top" | "bottom" | "left" | "right";
  children: React.ReactElement;
};

/**
 * Pure-CSS group-hover tooltip. No JS positioning, no portals — sufficient
 * for icon buttons and agent pills. For complex positioning use a Dialog or
 * upgrade to Radix later.
 */
export function Tooltip({ label, side = "top", children }: TooltipProps) {
  const sideCls: Record<NonNullable<TooltipProps["side"]>, string> = {
    top: "bottom-full mb-1.5 left-1/2 -translate-x-1/2",
    bottom: "top-full mt-1.5 left-1/2 -translate-x-1/2",
    left: "right-full mr-1.5 top-1/2 -translate-y-1/2",
    right: "left-full ml-1.5 top-1/2 -translate-y-1/2",
  };

  return (
    <span className="group relative inline-flex">
      {children}
      <span
        role="tooltip"
        className={cn(
          "pointer-events-none absolute z-50 whitespace-nowrap rounded-md border border-border bg-background px-2 py-1 text-[11px] text-foreground shadow-md",
          "opacity-0 transition-opacity duration-100 group-hover:opacity-100 group-focus-within:opacity-100",
          sideCls[side],
        )}
      >
        {label}
      </span>
    </span>
  );
}
