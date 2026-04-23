"use client";

import { Bot } from "lucide-react";
import { useLayoutEffect, useRef } from "react";

import { Avatar } from "@/components/ui/Avatar";
import { animate } from "@/lib/gsap";
import { cn } from "@/lib/utils";

export type AgentMessageProps = {
  label?: string;
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "inline-card";
};

/** A single assistant/agent chat bubble — left-aligned, bot avatar first. */
export function AgentMessage({
  label = "Kidroo",
  children,
  className,
  variant = "default",
}: AgentMessageProps) {
  const ref = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    if (!ref.current) return;
    void animate(
      ref.current,
      { y: 12, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.24, ease: "power2.out" },
    );
  }, []);

  return (
    <div ref={ref} className={cn("flex items-start gap-3", className)}>
      <Avatar className="bg-foreground text-background">
        <Bot className="h-3.5 w-3.5" aria-hidden />
      </Avatar>
      <div className="min-w-0 flex-1">
        <div className="mb-1 text-[11px] uppercase tracking-wider text-muted-foreground">
          {label}
        </div>
        <div
          className={
            variant === "inline-card"
              ? "" // caller renders a Card inside
              : "max-w-[80%] rounded-lg rounded-tl-sm border border-border/80 bg-muted/40 px-4 py-2.5 text-sm"
          }
        >
          {children}
        </div>
      </div>
    </div>
  );
}
