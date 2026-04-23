# Skill — GSAP animations

Read this when you are writing or tuning animations.

## Prerequisites

- `apps/web/lib/gsap.ts` wrapper is already in place (Phase 4).
- Basic familiarity with GSAP timelines.

## Why GSAP (and not just Framer Motion)

- **Timeline control** — we animate sequences of agent-log rows, staggered entries, and scroll-triggered reveals. Framer Motion's imperative API handles per-component animations well but falls over for timeline choreography.
- **Flip plugin** — for status-badge transitions where layout and color change simultaneously, `Flip.from(prev)` gives correct physics for free.
- **Performance** — GSAP tweens run on the main thread with `gsap.ticker`, but at this scale that's fine; we do not run >30 concurrent tweens.

Framer Motion is kept for shadcn-native animations (dialog, popover, toast entrances) because those components ship with it.

## The wrapper

Always import from the wrapper, never from `gsap` directly:

```ts
import { animate, timeline, flip } from "@/lib/gsap"
```

The wrapper:
1. Lazy-loads GSAP on the client only (SSR-safe).
2. Registers `Flip` + `ScrollTrigger` plugins once.
3. Honors `window.matchMedia("(prefers-reduced-motion: reduce)")` — when reduced, all durations collapse to 0.

## Canonical patterns

### Agent-log row enter

```ts
import { animate } from "@/lib/gsap"

useLayoutEffect(() => {
  if (!rowRef.current) return
  animate(
    rowRef.current,
    { y: 8, opacity: 0, filter: "blur(2px)" },
    { y: 0, opacity: 1, filter: "blur(0px)", duration: 0.22, ease: "power2.out" },
  )
}, [log.id])
```

### Staggered list (video card)

```ts
import { timeline } from "@/lib/gsap"

useLayoutEffect(() => {
  const tl = timeline()
  tl.from("[data-video-row]", {
    y: 6, opacity: 0, duration: 0.2, ease: "power2.out", stagger: 0.02,
  })
  return () => tl.kill()
}, [videos.length])
```

### Status-badge transition (Flip)

```ts
import { flip } from "@/lib/gsap"

// Before state change
const state = flip.getState(badgeRef.current)

// After React commits the new badge
flip.from(state, { duration: 0.3, ease: "power2.out", absolute: true })
```

### Auto-scroll on new row

```ts
// Only scroll if user is within 80px of bottom
const el = listRef.current
if (el && el.scrollHeight - el.scrollTop - el.clientHeight < 80) {
  animate(el, {}, { scrollTop: el.scrollHeight, duration: 0.3, ease: "power2.out" })
}
```

## Performance rules

- Never animate more than 30 elements concurrently. Virtualize the agent-log feed when it exceeds ~200 rows.
- Never animate `width`/`height` — animate `scaleX`/`scaleY` (or use Flip). Width/height triggers layout.
- Prefer `transform` and `opacity` — they are compositor-friendly.
- Kill timelines on unmount: `return () => tl.kill()`.

## Common failures

| Symptom | Fix |
|---|---|
| Animation fires during SSR → hydration mismatch | Use `useLayoutEffect` (not `useEffect`); also the wrapper guards for `typeof window === "undefined"` |
| Animation runs twice on React 19 strict mode | Wrap in `useLayoutEffect` with a proper cleanup (`return () => tl.kill()`) |
| Flip doesn't animate layout change | Call `flip.getState(el)` **before** the React state update, not in the same effect |
| Reduced-motion users see no transitions | Expected — the wrapper collapses duration to 0 |

## Related files

- `apps/web/lib/gsap.ts` — wrapper
- `docs/UI_SPEC.md` — visual spec
- `.agents/skills/frontend/SKILL.md`
