"use client";

import {
  AlertCircle,
  ArrowDownToLine,
  ArrowUpFromLine,
  CalendarCheck,
  Clock,
  Loader2,
  Sparkles,
} from "lucide-react";
import { useLayoutEffect, useRef } from "react";

import { Badge, type BadgeVariant } from "@/components/ui/Badge";
import type { VideoStatus } from "@/lib/agents/constants";
import { flip } from "@/lib/gsap";

export type StatusBadgeProps = {
  status: VideoStatus;
  className?: string;
};

type StatusConfig = {
  variant: BadgeVariant;
  label: string;
  Icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
  spin?: boolean;
};

const STATUS: Record<VideoStatus, StatusConfig> = {
  queued: { variant: "secondary", label: "queued", Icon: Clock },
  fetching: { variant: "secondary", label: "fetching", Icon: Loader2, spin: true },
  downloading: { variant: "info", label: "downloading", Icon: ArrowDownToLine },
  generating: { variant: "warning", label: "generating", Icon: Sparkles },
  uploading: {
    variant: "default",
    label: "uploading",
    Icon: ArrowUpFromLine,
  },
  scheduled: { variant: "success", label: "scheduled", Icon: CalendarCheck },
  failed: { variant: "destructive", label: "failed", Icon: AlertCircle },
};

/**
 * Per-video status badge. Uses GSAP `Flip` to animate the shape/colour change
 * as state transitions (queued → fetching → … → scheduled). Icon conveys
 * meaning in addition to colour for a11y.
 */
export function StatusBadge({ status, className }: StatusBadgeProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const prevStatus = useRef<VideoStatus>(status);

  useLayoutEffect(() => {
    if (prevStatus.current === status || !ref.current) {
      prevStatus.current = status;
      return;
    }
    let cancelled = false;
    (async () => {
      const state = await flip.getState(ref.current);
      if (cancelled) return;
      // React has already committed the new status in this render.
      await flip.apply(state, { duration: 0.3, ease: "power2.out" });
    })();
    prevStatus.current = status;
    return () => {
      cancelled = true;
    };
  }, [status]);

  const cfg = STATUS[status];
  const { Icon } = cfg;

  return (
    <Badge
      ref={ref}
      variant={cfg.variant}
      className={className}
      aria-label={`status: ${cfg.label}`}
    >
      <Icon
        className={cfg.spin ? "h-3 w-3 animate-spin" : "h-3 w-3"}
        aria-hidden
      />
      {cfg.label}
    </Badge>
  );
}
