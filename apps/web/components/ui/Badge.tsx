import { forwardRef } from "react";

import { cn } from "@/lib/utils";

export type BadgeVariant =
  | "default"
  | "secondary"
  | "success"
  | "warning"
  | "destructive"
  | "info"
  | "outline";

export type BadgeProps = React.HTMLAttributes<HTMLSpanElement> & {
  variant?: BadgeVariant;
};

const VARIANT: Record<BadgeVariant, string> = {
  default: "bg-foreground/10 text-foreground",
  secondary: "bg-muted text-muted-foreground",
  success: "bg-teal-500/15 text-teal-300",
  warning: "bg-amber-500/15 text-amber-300",
  destructive: "bg-red-500/15 text-red-300",
  info: "bg-sky-500/15 text-sky-300",
  outline: "border border-border text-foreground/80",
};

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant = "default", ...props }, ref) => (
    <span
      ref={ref}
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide",
        VARIANT[variant],
        className,
      )}
      {...props}
    />
  ),
);
Badge.displayName = "Badge";
