# Skill — frontend (Next.js + shadcn + Tailwind)

Read this when you are adding or modifying UI in `apps/web/`.

## Prerequisites

- Read `docs/UI_SPEC.md` end-to-end.
- Node 20+ and `pnpm` installed (SKILLS.sh).

## Stack reminders

- Next.js 15 App Router. Default to **server components**. Use `"use client"` only when the component needs state, effects, browser APIs, or GSAP.
- Tailwind CSS v4 — config is in `apps/web/styles/globals.css`, not `tailwind.config.js`.
- shadcn/ui components are copied into `apps/web/components/ui/`. Modify them freely; they are your code.
- Icons from `lucide-react`.
- State: React state + Supabase Realtime. No Redux, no Zustand unless proven necessary.

## Adding a shadcn component

```bash
pnpm dlx shadcn@latest add button dialog select
```

Components land in `apps/web/components/ui/`. Do not edit generated imports; adjust styles via Tailwind classes on the consumer.

## Conventions

1. **File naming:** components in `PascalCase.tsx`, hooks in `camelCase.ts`, utilities in `kebab-case.ts`.
2. **Colocate:** a component's test (`Component.test.tsx`) and its styles (if any) live next to the component.
3. **Props:** every component's props type is named `<Component>Props` and exported.
4. **Server actions:** live in `apps/web/app/<route>/actions.ts`, always marked `"use server"` at the top.
5. **Supabase clients:** one helper per side — `lib/supabase/client.ts` (browser) and `lib/supabase/server.ts` (server). Never `createClient` inline.

## Realtime subscriptions

Use the shared hook — do not open subscriptions ad-hoc.

```ts
// apps/web/hooks/useAgentLogs.ts  (already shipped in Phase 4)
const logs = useAgentLogs(jobId)
```

The hook auto-cleans on unmount and backfills existing rows on mount.

## Animations

All animations go through the GSAP wrapper in `apps/web/lib/gsap.ts`. Do not import `gsap` directly in components — the wrapper handles SSR guards and `prefers-reduced-motion`.

```ts
import { animate } from "@/lib/gsap"
animate(el, { y: 8, opacity: 0 }, { y: 0, opacity: 1, duration: 0.22 })
```

See `.agents/skills/gsap/SKILL.md` for animation patterns.

## Styling rules

- No inline styles except CSS variables driven by state.
- No arbitrary Tailwind values (`w-[137px]`) unless there is no token that fits.
- All colors through Tailwind tokens; no raw hex in components.
- Dark mode: assume `dark` class on `<html>`; component styles use `dark:` variants.

## Accessibility

- Every interactive element is keyboard reachable.
- `aria-label` on icon-only buttons.
- Use `Tooltip` from shadcn for any icon that might be ambiguous.
- `prefers-reduced-motion` is honored by the GSAP wrapper globally.

## Common failures

| Symptom | Fix |
|---|---|
| Hydration mismatch from dates | Use `<time dateTime={iso}>{format(iso)}</time>` or `suppressHydrationWarning` sparingly |
| GSAP runs on server and breaks SSR | Import from `@/lib/gsap` (wrapper is client-safe), not `gsap` directly |
| Supabase RLS blocks reads | You used the server client in a client component — switch to `createBrowserClient` |
| `cn()` not defined | Add `import { cn } from "@/lib/utils"` (shadcn default) |

## Related files

- `docs/UI_SPEC.md`
- `.agents/skills/gsap/SKILL.md`
- `apps/web/lib/gsap.ts`
- `apps/web/lib/supabase/*.ts`
