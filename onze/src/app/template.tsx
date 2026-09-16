"use client";

import { motion, useReducedMotion } from "motion/react";

/* Page transition.
 *
 * A template re-mounts on every navigation (a layout does not), which is what
 * makes it the right place for this. The move is deliberately small — a short
 * fade with a few pixels of rise — because a storefront is a place people
 * navigate quickly, and a long transition taxes every single click.
 *
 * There is no exit animation: without the View Transition API the old page is
 * already gone by the time this mounts, so animating "out" would only add
 * latency before the new page appears.
 */
export default function Template({ children }: { children: React.ReactNode }) {
  const reduced = useReducedMotion();

  if (reduced) return <>{children}</>;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  );
}
