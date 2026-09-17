"use client";

import { useEffect, useRef, useState } from "react";
import { useInView, useReducedMotion } from "motion/react";

/* A number that counts up once, when it arrives.
 *
 * It renders the final value on the server and only rewinds after hydration,
 * so the real figure is what a crawler reads and what someone without JS
 * sees — a counter that starts at zero in the HTML is a counter that shows
 * zero when the script fails. */
export function Counter({ value, suffix = "" }: { value: number; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.6 });
  const reduced = useReducedMotion();
  const [display, setDisplay] = useState(value);

  useEffect(() => {
    if (reduced || !inView) return;
    let raf = 0;
    const DURATION = 900;
    const start = performance.now();
    setDisplay(0);
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / DURATION);
      /* easeOutExpo: fast off the mark, long settle — reads like a readout
         landing rather than a linear tally. */
      const eased = t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
      setDisplay(Math.round(value * eased));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, reduced, value]);

  return (
    <span ref={ref} className="tabular">
      {display}
      {suffix}
    </span>
  );
}
