"use client";

import { useEffect, useRef } from "react";
import Lenis from "lenis";
import { useReducedMotion } from "motion/react";

/* Inertia scrolling, site-wide.
 *
 * The native scrollbar accelerates and stops instantly; Lenis smooths that
 * into a short glide, which is most of what makes a black-and-white product
 * site like this feel expensive rather than just austere. It is entirely a
 * feel change — it never intercepts scroll position, so anchors, the browser
 * back button and scroll-linked animations elsewhere on the page keep working
 * exactly as before.
 *
 * Skipped outright under prefers-reduced-motion: smoothing a reduced-motion
 * visitor's scroll is exactly the kind of motion that setting exists to
 * suppress, even though it isn't a transform-based animation. */
export function SmoothScroll({ children }: { children: React.ReactNode }) {
  const reduced = useReducedMotion();
  const raf = useRef<number>(0);

  useEffect(() => {
    if (reduced) return;

    const lenis = new Lenis({
      duration: 1.1,
      easing: (t: number) => 1 - Math.pow(1 - t, 3),
      smoothWheel: true,
    });

    function loop(time: number) {
      lenis.raf(time);
      raf.current = requestAnimationFrame(loop);
    }
    raf.current = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(raf.current);
      lenis.destroy();
    };
  }, [reduced]);

  return <>{children}</>;
}
