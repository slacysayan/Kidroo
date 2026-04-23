"use client";

/**
 * SSR-safe GSAP wrapper.
 *
 * - Lazy-loads GSAP + Flip + ScrollTrigger on the client only.
 * - Honors `prefers-reduced-motion`: collapses durations to 0.
 * - Never throws when called during SSR — callers receive a no-op promise.
 *
 * Import `animate`, `timeline`, and `flip` from here. Never `import "gsap"` directly.
 *
 * See `.agents/skills/gsap/SKILL.md` for canonical usage patterns.
 */

type GsapModule = typeof import("gsap").gsap;
type FlipModule = typeof import("gsap/Flip").Flip;
type TweenInstance = ReturnType<GsapModule["to"]>;

let _gsapPromise: Promise<GsapModule> | null = null;
let _flipPromise: Promise<FlipModule> | null = null;

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return true;
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

async function loadGsap(): Promise<GsapModule> {
  if (!_gsapPromise) {
    _gsapPromise = (async () => {
      const [{ gsap }, { ScrollTrigger }] = await Promise.all([
        import("gsap"),
        import("gsap/ScrollTrigger"),
      ]);
      gsap.registerPlugin(ScrollTrigger);
      return gsap;
    })();
  }
  return _gsapPromise;
}

async function loadFlip(): Promise<FlipModule> {
  if (!_flipPromise) {
    _flipPromise = (async () => {
      const [{ gsap }, { Flip }] = await Promise.all([
        import("gsap"),
        import("gsap/Flip"),
      ]);
      gsap.registerPlugin(Flip);
      return Flip;
    })();
  }
  return _flipPromise;
}

type TweenVars = Record<string, unknown>;

/** `gsap.fromTo(target, fromVars, toVars)` with reduced-motion guard. */
export async function animate(
  target: gsap.TweenTarget,
  fromVars: TweenVars,
  toVars: TweenVars & { duration?: number; ease?: string; delay?: number },
): Promise<TweenInstance | null> {
  if (typeof window === "undefined" || !target) return null;
  const gsap = await loadGsap();
  const vars = prefersReducedMotion() ? { ...toVars, duration: 0 } : toVars;
  return gsap.fromTo(target, fromVars, vars);
}

/** Returns a GSAP timeline. Durations collapse to 0 under reduced-motion. */
export async function timeline(): Promise<gsap.core.Timeline | null> {
  if (typeof window === "undefined") return null;
  const gsap = await loadGsap();
  const tl = gsap.timeline();
  if (prefersReducedMotion()) {
    tl.timeScale(Number.POSITIVE_INFINITY);
  }
  return tl;
}

/**
 * Flip helpers. Capture state *before* the React state update, then `apply` after.
 *
 * ```ts
 * const state = await flip.getState(el);
 * // ... mutate DOM via React ...
 * await flip.apply(state, { duration: 0.3 });
 * ```
 */
export const flip = {
  async getState(
    targets: Element | Element[] | string | null,
  ): Promise<ReturnType<FlipModule["getState"]> | null> {
    if (typeof window === "undefined" || !targets) return null;
    const Flip = await loadFlip();
    return Flip.getState(targets);
  },
  async apply(
    state: ReturnType<FlipModule["getState"]> | null,
    vars: TweenVars = {},
  ): Promise<void> {
    if (typeof window === "undefined" || !state) return;
    const Flip = await loadFlip();
    const finalVars = prefersReducedMotion() ? { ...vars, duration: 0 } : vars;
    Flip.from(state, finalVars);
  },
};

/**
 * Smoothly scroll an element to its bottom *only* if the user is near the bottom
 * already (within `threshold` px). Preserves reading position otherwise.
 */
export async function autoScrollToBottom(
  el: HTMLElement | null,
  threshold = 80,
): Promise<void> {
  if (typeof window === "undefined" || !el) return;
  if (el.scrollHeight - el.scrollTop - el.clientHeight >= threshold) return;
  const gsap = await loadGsap();
  const duration = prefersReducedMotion() ? 0 : 0.3;
  gsap.to(el, { scrollTop: el.scrollHeight, duration, ease: "power2.out" });
}
