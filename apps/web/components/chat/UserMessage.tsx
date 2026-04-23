"use client";

import { useLayoutEffect, useRef } from "react";

import { Avatar } from "@/components/ui/Avatar";
import { animate } from "@/lib/gsap";
import { cn } from "@/lib/utils";

export type UserMessageProps = {
  email?: string | null;
  children: React.ReactNode;
  className?: string;
};

/** A single user chat bubble — right-aligned, avatar last. */
export function UserMessage({ email, children, className }: UserMessageProps) {
  const ref = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    if (!ref.current) return;
    void animate(
      ref.current,
      { y: 12, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.24, ease: "power2.out" },
    );
  }, []);

  const initials = (email ?? "me").slice(0, 2).toUpperCase();

  return (
    <div ref={ref} className={cn("flex items-start justify-end gap-3", className)}>
      <div className="max-w-[68%] rounded-lg rounded-tr-sm border border-border/80 bg-background/80 px-4 py-2.5 text-sm shadow-sm">
        {children}
      </div>
      <Avatar>{initials}</Avatar>
    </div>
  );
}
