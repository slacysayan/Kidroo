# UI specification

## Visual language

- **Typography:** Geist Sans for body, Geist Mono for agent-log text and code. Loaded via `next/font/google` in `apps/web/app/layout.tsx`:

  ```ts
  import { Geist, Geist_Mono } from "next/font/google";

  const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"], display: "swap" });
  const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"], display: "swap" });
  ```

  The CSS variables `--font-geist-sans` / `--font-geist-mono` are wired into Tailwind v4 `@theme` in `apps/web/app/globals.css` and become the default `font-sans` / `font-mono`. No other font system is used anywhere in the app.
- **Color:** shadcn default neutral palette. Agent color tokens (pill backgrounds) are defined once in `apps/web/styles/tokens.css` and used everywhere.
- **Spacing:** 4 px base grid. All paddings/margins are `p-{n}` / `m-{n}` Tailwind tokens.
- **Radius:** `rounded-md` (6 px) default. `rounded-lg` (8 px) for cards. Never `rounded-full` except avatars and badges.
- **Motion:** GSAP is the primary animation library; Framer Motion is used only for shadcn-native entrances (popover, dialog).

## Component inventory (shadcn/ui)

| Component | Where used |
|---|---|
| `Button` | Send, upload, schedule, confirm |
| `Input` + `Textarea` | Chat input |
| `Card` | Video-selection card, schedule-confirmation card |
| `Badge` | Per-video status (queued → scheduled), agent pills |
| `ScrollArea` | Agent log feed, video list |
| `Select` | Target channel dropdown, schedule picker |
| `Checkbox` | Video-selection checkboxes |
| `Separator` | Between message groups |
| `Avatar` | Agent identity in log feed |
| `Skeleton` | Scanning / loading states |
| `Tooltip` | Agent pill tooltips (full name, latency) |
| `Dialog` | Connect-channel OAuth redirect, confirm-delete |
| `Sonner` | Toasts for errors / successes |

## Agent log feed — visual spec

Each log entry is a single row:

```
[AgentPill]   [monospace message text]                             [timestamp]
              [optional metadata row: tool, latency, retry count]
```

### Agent color tokens

| Agent | Pill background | Pill text |
|---|---|---|
| `orchestrator` | `bg-violet-500/15` | `text-violet-300` |
| `research` | `bg-sky-500/15` | `text-sky-300` |
| `metadata` | `bg-amber-500/15` | `text-amber-300` |
| `download` | `bg-teal-500/15` | `text-teal-300` |
| `upload` | `bg-rose-500/15` | `text-rose-300` |

Message text uses `font-mono text-xs text-muted-foreground`. Timestamps are `text-[10px] text-muted-foreground/60` right-aligned.

### Animation (GSAP)

New log rows animate in with a single GSAP timeline per row:

```ts
gsap.fromTo(el,
  { y: 8, opacity: 0, filter: "blur(2px)" },
  { y: 0, opacity: 1, filter: "blur(0px)", duration: 0.22, ease: "power2.out" }
)
```

Stagger is automatic because new rows arrive over Realtime one at a time. If a burst arrives (>3 rows within 50 ms), use `gsap.timeline()` with `stagger: 0.04`.

Scroll behavior: if the user is within 80 px of the bottom when a new row arrives, smooth-scroll to bottom (`scrollTo` with `ease: "power2.out", duration: 0.3`). Otherwise do not scroll — preserves the user's reading position.

## Video selection card

Rendered inline in the chat when scan completes.

```
┌────────────────────────────────────────────────────────────────┐
│  Found 47 videos on @sourcechannel                 [Select all] │
├────────────────────────────────────────────────────────────────┤
│  ☐  Why the iPhone 16 changes everything      12:04             │
│  ☐  The Vision Pro is doomed                   8:31             │
│  ☐  ...                                                         │
├────────────────────────────────────────────────────────────────┤
│  Target:      [ Finance Daily ▼ ]                               │
│  Schedule:    [ 2 / day starting Mon ▼ ]                        │
│                                                                 │
│                                        [ Cancel ]  [ Proceed ]  │
└────────────────────────────────────────────────────────────────┘
```

- Scan list uses `ScrollArea` bounded to `max-h-[420px]`.
- Checkbox state is local React state until "Proceed"; submission posts to `POST /jobs/:id/select`.
- "Proceed" is disabled when 0 videos are selected.

## Schedule-confirmation card

Rendered after the user submits. Shows per-video status badges that live-update from Supabase Realtime:

```
queued → fetching → downloading → generating → uploading → scheduled
                                                          └→ failed (retrying…)
```

Each state maps to a `Badge` variant:

| State | Variant | Icon |
|---|---|---|
| `queued` | `secondary` | `Clock` |
| `fetching` | `secondary` | `Loader2 animate-spin` |
| `downloading` | `default` (blue) | `ArrowDownToLine` |
| `generating` | `default` (amber) | `Sparkles` |
| `uploading` | `default` (rose) | `ArrowUpFromLine` |
| `scheduled` | `success` (teal) | `CalendarCheck` |
| `failed` | `destructive` | `AlertCircle` |

## Sidebar

Left-hand, 260 px wide, collapsible.

```
┌──────────────────────┐
│  Kidroo              │
├──────────────────────┤
│  CHANNELS            │
│  ● Finance Daily     │   ← green dot = OAuth healthy
│  ● Tech Weekly       │
│  ○ Travel Vlogs      │   ← grey dot = OAuth expired
│  + Connect channel   │
├──────────────────────┤
│  QUEUE               │
│  3 jobs active       │
│  12 videos scheduled │
├──────────────────────┤
│  QUICK ACTIONS       │
│  ⌘ K  Command menu   │
└──────────────────────┘
```

OAuth health dot is powered by a polling check to `GET /channels/:id/health`, which calls Composio `YOUTUBE_GET_CHANNEL` and returns green on 200, grey on 401.

## GSAP patterns

### Chat message enter

```ts
gsap.from(messageEl, {
  y: 12, opacity: 0, duration: 0.24, ease: "power2.out"
})
```

### Video-card entry (staggered list)

```ts
gsap.from(cardEl.querySelectorAll("[data-video-row]"), {
  y: 6, opacity: 0, duration: 0.2, ease: "power2.out", stagger: 0.02
})
```

### Status-badge transition

Use a `<Flip>` plugin-style pattern via the GSAP `Flip` plugin when a badge changes state — keeps layout stable while animating color/shape.

All GSAP primitives are wrapped in `apps/web/lib/gsap.ts` which lazy-loads GSAP + `Flip` + `ScrollTrigger` only on the client.

## Accessibility

- Every interactive element is keyboard reachable.
- All animations honor `prefers-reduced-motion` — GSAP wrapper checks the media query and sets `duration: 0` when reduced.
- Agent-log screen-reader announcements are throttled (aria-live="polite", rate-limited to 1/s via a queue).
- Color is never the sole carrier of meaning (status badges always include an icon).

## Live components shipped in Phase 1 / 2

| Component | File | Purpose |
|---|---|---|
| `Header` | `apps/web/components/Header.tsx` | Brand + email + sign-out |
| `SignOutButton` | `apps/web/components/SignOutButton.tsx` | Calls `supabase.auth.signOut()` and redirects to `/login` |
| `JobComposer` | `apps/web/components/JobComposer.tsx` | Paste-a-link form; inserts `jobs` row via RLS and navigates to `/jobs/[id]` |
| `AgentLogTimeline` | `apps/web/components/AgentLogTimeline.tsx` | Supabase-Realtime subscription to `agent_logs`, GSAP entrance per row |
| `JobActions` | `apps/web/app/jobs/[id]/JobActions.tsx` | Scan / select / schedule / start controls; calls FastAPI `/jobs/{id}/scan` + `/start` |
| `ConnectChannelForm` | `apps/web/app/channels/connect/ConnectChannelForm.tsx` | Creates a `channels` row with a Composio entity alias |
