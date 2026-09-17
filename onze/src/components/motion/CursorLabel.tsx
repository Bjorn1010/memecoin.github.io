"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion, useMotionValue, useSpring } from "motion/react";

/* A label that follows the pointer over media.
 *
 * Deliberately additive: the real cursor is never hidden. Replacing the system
 * cursor is the version of this effect that breaks things — it hides the
 * pointer's own affordances, fails the moment the script does, and helps
 * nobody using a screen magnifier. This just adds a word next to it.
 *
 * Opt in by putting data-cursor="VOIR" on any element.
 */
export function CursorLabel() {
  const [label, setLabel] = useState<string | null>(null);
  const x = useSpring(useMotionValue(0), { stiffness: 450, damping: 35, mass: 0.3 });
  const y = useSpring(useMotionValue(0), { stiffness: 450, damping: 35, mass: 0.3 });

  useEffect(() => {
    /* Pointer-precision and motion preference are both checked here rather
       than in CSS, so the listeners are never attached on a touch device. */
    if (!window.matchMedia("(pointer: fine)").matches) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const onMove = (e: PointerEvent) => {
      x.set(e.clientX);
      y.set(e.clientY);
      const hit = (e.target as Element | null)?.closest?.("[data-cursor]");
      setLabel(hit ? hit.getAttribute("data-cursor") : null);
    };
    const onLeave = () => setLabel(null);

    window.addEventListener("pointermove", onMove, { passive: true });
    document.addEventListener("pointerleave", onLeave);
    return () => {
      window.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerleave", onLeave);
    };
  }, [x, y]);

  return (
    <AnimatePresence>
      {label && (
        <motion.div
          aria-hidden
          style={{ x, y }}
          initial={{ opacity: 0, scale: 0.7 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.7 }}
          transition={{ duration: 0.16 }}
          className="pointer-events-none fixed left-0 top-0 z-[200] hidden lg:block"
        >
          <span className="label-mono ml-4 mt-4 inline-block bg-volt px-2.5 py-1.5 text-on-volt">
            {label}
          </span>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
