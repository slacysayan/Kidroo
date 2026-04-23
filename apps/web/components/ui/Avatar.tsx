import { forwardRef } from "react";

import { cn } from "@/lib/utils";

export type AvatarProps = React.HTMLAttributes<HTMLDivElement>;

export const Avatar = forwardRef<HTMLDivElement, AvatarProps>(
  ({ className, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "inline-flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-full bg-muted text-[11px] font-semibold uppercase text-foreground/80",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  ),
);
Avatar.displayName = "Avatar";
