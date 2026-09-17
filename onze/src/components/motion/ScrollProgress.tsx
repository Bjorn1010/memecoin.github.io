"use client";

import { motion, useScroll, useSpring } from "motion/react";

/* A hairline of volt across the top of the header showing how far through the
   page you are. Decorative, so it is hidden from assistive tech — a screen
   reader already knows where it is in the document. */
export function ScrollProgress() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 180, damping: 30, restDelta: 0.001 });

  return (
    <motion.div
      aria-hidden
      style={{ scaleX }}
      className="absolute inset-x-0 bottom-0 h-px origin-left bg-volt"
    />
  );
}
