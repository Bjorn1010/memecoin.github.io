"use client";

import { useEffect, useState } from "react";
import { motion, useReducedMotion, AnimatePresence } from "motion/react";

/* The boot screen: the wordmark resolves out of the black, a counter ticks
 * to 100, then the page is released. It is the one un-restrained gesture the
 * identity allows itself, once, before it settles into a page that otherwise
 * never raises its voice.
 *
 * It runs once per full page load, not once per visit — a client-side route
 * change keeps this component mounted, so it only reappears on an actual
 * reload. A hard timeout guarantees it is never a real gate: whatever else is
 * still loading, the page is released within ~2.4s.
 */
export function Boot() {
  const reduced = useReducedMotion();
  const [progress, setProgress] = useState(0);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (reduced) {
      setDone(true);
      return;
    }
    if (typeof document !== "undefined" && document.body) {
      document.body.style.overflow = "hidden";
    }

    const start = performance.now();
    const DURATION = 1400;
    let raf = 0;

    function tick(now: number) {
      const t = Math.min(1, (now - start) / DURATION);
      /* easeOutQuint: fast through the middle, a deliberate slow settle onto
         100 — a linear count reads like a spinner, not an arrival. */
      const eased = 1 - Math.pow(1 - t, 5);
      setProgress(Math.round(eased * 100));
      if (t < 1) raf = requestAnimationFrame(tick);
      else window.setTimeout(() => setDone(true), 280);
    }
    raf = requestAnimationFrame(tick);

    /* Hard ceiling, independent of the counter above — if a tab is
       backgrounded mid-animation and rAF throttles, this still releases
       the page rather than leaving it stuck under the overlay. */
    const ceiling = window.setTimeout(() => setDone(true), 2400);

    return () => {
      cancelAnimationFrame(raf);
      window.clearTimeout(ceiling);
    };
  }, [reduced]);

  useEffect(() => {
    if (done && typeof document !== "undefined" && document.body) {
      document.body.style.overflow = "";
    }
  }, [done]);

  if (reduced) return null;

  return (
    <AnimatePresence>
      {!done && (
        <motion.div
          aria-hidden
          initial={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="fixed inset-0 z-[300] flex flex-col items-center justify-center gap-8 bg-void"
        >
          <motion.p
            initial={{ opacity: 0.06 }}
            animate={{ opacity: 0.06 + (progress / 100) * 0.94 }}
            className="font-display text-[14vw] leading-none tracking-[-0.02em] text-ink sm:text-[9rem]"
          >
            ONZE<span className="text-volt">.</span>
          </motion.p>
          <p className="scoreboard tabular text-sm text-steel-400">{progress}%</p>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
