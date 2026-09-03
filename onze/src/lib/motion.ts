import type { Transition, Variants } from "motion/react";

/* =========================================================================
   MOTION SYSTEM
   One vocabulary for the whole site. Components import from here rather than
   inventing durations, so timing stays coherent across every surface.

   Tiers (mirrors the CSS tokens in globals.css):
     micro     140–220ms  hover, press, toggle, icon state
     standard  320–420ms  cards, drawers, filter changes, menus
     premium   720–1100ms hero, cinematic reveals, section transitions
   ========================================================================= */

export const duration = {
  micro: 0.14,
  fast: 0.22,
  standard: 0.32,
  slow: 0.42,
  premium: 0.72,
  cinematic: 1.1,
} as const;

/* Easing curves as cubic-bezier arrays, matching the CSS custom properties.
   expoOut is the workhorse: fast departure, long settle — reads as "engineered"
   rather than bouncy. */
export const ease = {
  outExpo: [0.16, 1, 0.3, 1],
  outQuint: [0.22, 1, 0.36, 1],
  inOutSoft: [0.65, 0, 0.35, 1],
  spring: [0.34, 1.56, 0.64, 1],
} as const;

export const transition = {
  micro: { duration: duration.micro, ease: ease.outQuint },
  fast: { duration: duration.fast, ease: ease.outQuint },
  standard: { duration: duration.standard, ease: ease.outExpo },
  slow: { duration: duration.slow, ease: ease.outExpo },
  premium: { duration: duration.premium, ease: ease.outExpo },
  cinematic: { duration: duration.cinematic, ease: ease.outExpo },
} satisfies Record<string, Transition>;

/* Physical springs for anything the pointer drives directly. A tween on a
   cursor-following element always feels laggy; a spring does not. */
export const spring = {
  /* Pointer parallax, 3D tilt — light and quick to settle. */
  pointer: { type: "spring", stiffness: 150, damping: 20, mass: 0.6 },
  /* Drawers and sheets — heavier, no visible overshoot. */
  panel: { type: "spring", stiffness: 260, damping: 32, mass: 0.9 },
  /* Cart badge, counters — a small deliberate overshoot reads as "landed". */
  pop: { type: "spring", stiffness: 480, damping: 18, mass: 0.7 },
} satisfies Record<string, Transition>;

/* -------------------------------------------------------------------------
   Reveal variants
   `custom` carries the stagger index so a single variant object drives a whole
   list without a wrapper per item.
   ------------------------------------------------------------------------- */

export const revealUp: Variants = {
  hidden: { opacity: 0, y: 28 },
  visible: (i: number = 0) => ({
    opacity: 1,
    y: 0,
    transition: { ...transition.premium, delay: i * 0.06 },
  }),
};

export const revealFade: Variants = {
  hidden: { opacity: 0 },
  visible: (i: number = 0) => ({
    opacity: 1,
    transition: { ...transition.slow, delay: i * 0.05 },
  }),
};

/* Hero words. The blur is what makes it read as cinematic rather than as a
   generic slide-up — it mimics a lens pulling into focus. */
export const revealCinematic: Variants = {
  hidden: { opacity: 0, y: 48, filter: "blur(12px)" },
  visible: (i: number = 0) => ({
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: { ...transition.cinematic, delay: 0.1 + i * 0.09 },
  }),
};

export const staggerChildren: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.06, delayChildren: 0.05 } },
};

/* Drawers and bottom sheets. */
export const slideInRight: Variants = {
  hidden: { x: "100%" },
  visible: { x: 0, transition: spring.panel },
  exit: { x: "100%", transition: transition.standard },
};

export const slideUpSheet: Variants = {
  hidden: { y: "100%" },
  visible: { y: 0, transition: spring.panel },
  exit: { y: "100%", transition: transition.standard },
};

export const scrim: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: transition.fast },
  exit: { opacity: 0, transition: transition.fast },
};

/* Shared viewport config: fire once, slightly before the element is fully in
   frame so the animation is already settling when the user reaches it. */
export const inView = { once: true, amount: 0.2, margin: "0px 0px -80px 0px" } as const;
