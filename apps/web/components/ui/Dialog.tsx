"use client";

import { X } from "lucide-react";
import { useEffect } from "react";

import { cn } from "@/lib/utils";

export type DialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: React.ReactNode;
  description?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
};

/**
 * Minimal modal. Closes on Escape and on backdrop click. For complex trap-focus
 * / portal behavior swap in Radix later.
 */
export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  className,
}: DialogProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onOpenChange(false);
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onOpenChange]);

  if (!open) return null;

  return (
    <div
      aria-modal="true"
      // biome-ignore lint/a11y/useSemanticElements: <dialog> element has well-known styling quirks; this modal is keyboard- and screen-reader-accessible via aria-modal + Escape handler.
      role="dialog"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      <button
        type="button"
        aria-label="Close dialog"
        onClick={() => onOpenChange(false)}
        className="absolute inset-0 h-full w-full bg-black/50 backdrop-blur-sm"
      />
      <div
        className={cn(
          "relative z-10 w-full max-w-lg rounded-lg border border-border bg-background p-6 shadow-xl",
          className,
        )}
      >
        <button
          type="button"
          aria-label="Close"
          onClick={() => onOpenChange(false)}
          className="absolute right-3 top-3 rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <X className="h-4 w-4" aria-hidden />
        </button>
        {title ? (
          <h2 className="text-base font-semibold tracking-tight">{title}</h2>
        ) : null}
        {description ? (
          <p className="mt-1 text-xs text-muted-foreground">{description}</p>
        ) : null}
        {children ? <div className="mt-4">{children}</div> : null}
      </div>
    </div>
  );
}
