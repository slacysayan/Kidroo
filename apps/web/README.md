# `apps/web` — Kidroo frontend

Next.js 15 (App Router, Turbopack), React 19, Tailwind CSS v4, Supabase Auth + Realtime, GSAP.

## Fonts

Typography is the **Geist** family, loaded via `next/font/google` so the binaries are self-hosted by Next (no FOUT, no runtime network hop):

```ts
// app/layout.tsx
import { Geist, Geist_Mono } from "next/font/google";
const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });
```

The CSS variables are wired into Tailwind v4 via `@theme { --font-sans / --font-mono }` in `app/globals.css`. Everything uses `Geist Sans` by default; `code`, `pre`, and `.font-mono` get `Geist Mono`.

## Auth

**Full Supabase Auth** (not magic-link-only):

- **Email + password** (default flow) — see `app/login/page.tsx`.
- **Magic link** — same form, toggle.
- **OAuth (Google)** — same form, separate button; enable the provider in the Supabase Dashboard first.
- **Email allowlist** is enforced server-side via a `before_signup` Edge Function + RLS on the `allowed_emails` table.

Session state persists via `@supabase/ssr` cookies. `middleware.ts` refreshes the session on every request and redirects unauthenticated users to `/login`. All routes are protected by default; only `/login` and `/auth/*` are public.

## Structure

```
apps/web/
├── app/
│   ├── layout.tsx          # Geist fonts + Toaster
│   ├── globals.css         # Tailwind v4 + theme vars
│   ├── page.tsx            # root redirect → /login or /app
│   ├── login/page.tsx      # auth form (password / magic / signup / Google)
│   ├── auth/callback/route.ts  # OAuth + magic-link exchange
│   └── app/page.tsx        # authenticated dashboard (channels list)
├── lib/supabase/
│   ├── client.ts           # browser client
│   └── server.ts           # RSC / route-handler client
├── middleware.ts           # session refresh + gate
├── next.config.ts
├── tsconfig.json
└── postcss.config.mjs
```

## Commands

```bash
pnpm --filter @kidroo/web dev        # dev server on :3000
pnpm --filter @kidroo/web build
pnpm --filter @kidroo/web typecheck  # tsc --noEmit
pnpm --filter @kidroo/web test       # vitest
pnpm --filter @kidroo/web test:e2e   # playwright
```
