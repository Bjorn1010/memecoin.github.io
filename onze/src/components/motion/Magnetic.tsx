"use client";

import { useRef } from "react";
import { motion, useMotionValue, useReducedMotion, useSpring } from "motion/react";

/* Magnetic pull on a control.
 *
 * The element leans a few pixels toward the pointer inside its own bounds. It
 * is a tiny effect and that is the point: past ~10px the button stops feeling
 * attracted and starts feeling broken, and the click target drifts away from
 * where the user aimed.
 *
 * Only fires for a fine pointer — on touch there is no hover to lean into, and
 * the transform would just fight the tap.
 */
export function Magnetic({
  children,
  strength = 8,
  className,
}: {
  children: React.ReactNode;
  strength?: number;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const reduced = useReducedMotion();
  const x = useSpring(useMotionValue(0), { stiffness: 260, damping: 22, mass: 0.4 });
  const y = useSpring(useMotionValue(0), { stiffness: 260, damping: 22, mass: 0.4 });

  function move(e: React.PointerEvent<HTMLSpanElement>) {
    if (reduced || e.pointerType !== "mouse" || !ref.current) return;
    const r = ref.current.getBoundingClientRect();
    x.set(((e.clientX - (r.left + r.width / 2)) / (r.width / 2)) * strength);
    y.set(((e.clientY - (r.top + r.height / 2)) / (r.height / 2)) * strength);
  }

  return (
    <motion.span
      ref={ref}
      style={{ x, y }}
      onPointerMove={move}
      onPointerLeave={() => {
        x.set(0);
        y.set(0);
      }}
      className={className}
    >
      {children}
    </motion.span>
  );
}
