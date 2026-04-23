"use client";

import { Check } from "lucide-react";
import { forwardRef } from "react";

import { cn } from "@/lib/utils";

export type CheckboxProps = Omit<
  React.InputHTMLAttributes<HTMLInputElement>,
  "type" | "size"
>;

/**
 * Controlled checkbox wrapped in a styled label.
 * Use `checked` + `onChange`; the visual check is rendered by a Lucide icon.
 */
export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, checked, ...props }, ref) => (
    <span className={cn("relative inline-flex h-4 w-4 shrink-0", className)}>
      <input
        ref={ref}
        type="checkbox"
        checked={checked}
        className="peer h-4 w-4 cursor-pointer appearance-none rounded border border-border bg-background transition-colors checked:border-foreground checked:bg-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/70 disabled:cursor-not-allowed disabled:opacity-50"
        {...props}
      />
      {checked ? (
        <Check
          className="pointer-events-none absolute inset-0 m-auto h-3 w-3 text-background"
          strokeWidth={3}
          aria-hidden
        />
      ) : null}
    </span>
  ),
);
Checkbox.displayName = "Checkbox";
