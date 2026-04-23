import { forwardRef } from "react";

import { cn } from "@/lib/utils";

export type ScrollAreaProps = React.HTMLAttributes<HTMLDivElement>;

/**
 * Thin wrapper over a native scrollable div. Kept as a component so we can
 * swap it out for radix-scroll-area later without touching consumers.
 */
export const ScrollArea = forwardRef<HTMLDivElement, ScrollAreaProps>(
  ({ className, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "relative overflow-auto",
        "scrollbar-thin scrollbar-thumb-border",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  ),
);
ScrollArea.displayName = "ScrollArea";
