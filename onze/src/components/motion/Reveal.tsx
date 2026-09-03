"use client";

import { motion, useReducedMotion, type Variants } from "motion/react";
import { inView, revealCinematic, revealFade, revealUp } from "@/lib/motion";

/* Scroll reveals go through this one component rather than being hand-rolled
 * per section, so the whole site enters with the same timing and the same
 * reduced-motion behaviour. */

const presets = {
  up: revealUp,
  fade: revealFade,
  cinematic: revealCinematic,
} satisfies Record<string, Variants>;

export function Reveal({
  children,
  preset = "up",
  index = 0,
  className,
  as = "div",
}: {
  children: React.ReactNode;
  preset?: keyof typeof presets;
  /** Stagger position. Keep under ~8 or the last item feels broken. */
  index?: number;
  className?: string;
  as?: "div" | "section" | "li" | "article" | "h2" | "p";
}) {
  const reduced = useReducedMotion();
  const Component = motion[as];

  /* Under reduced motion the element is simply present. No transform, no
     blur, no delay — a staggered fade is still motion. */
  if (reduced) return <Component className={className}>{children}</Component>;

  return (
    <Component
      className={className}
      custom={index}
      variants={presets[preset]}
      initial="hidden"
      whileInView="visible"
      viewport={inView}
    >
      {children}
    </Component>
  );
}
