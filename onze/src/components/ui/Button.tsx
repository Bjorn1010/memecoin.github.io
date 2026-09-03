"use client";

import { motion, type HTMLMotionProps } from "motion/react";
import Link from "next/link";
import { forwardRef } from "react";
import { cn } from "@/lib/utils";
import { transition } from "@/lib/motion";

/* One button, four intents. Every clickable surface on the site goes through
 * here so press feedback, focus rings and disabled states stay identical. */

type Variant = "pitch" | "solid" | "ghost" | "outline" | "onDark";
type Size = "sm" | "md" | "lg";

const base =
  "relative inline-flex items-center justify-center gap-2 font-display uppercase " +
  "tracking-[0.08em] whitespace-nowrap select-none rounded-md " +
  "transition-colors duration-[--duration-fast] " +
  "disabled:pointer-events-none disabled:opacity-40";

const variants: Record<Variant, string> = {
  /* The primary action. Pitch green on white is the shop's loudest element,
     which is exactly why only one of these appears per view. */
  pitch: "bg-pitch text-paper hover:bg-pitch-dark shadow-[0_6px_20px_rgb(10_156_74_/_0.32)]",
  solid: "bg-ink text-paper hover:bg-pitch-deep",
  ghost: "text-steel-300 hover:text-ink hover:bg-ink/5",
  outline: "border-2 border-ink/15 text-steel-200 hover:border-pitch hover:text-pitch",
  /* For the turf sections, where the page background is green and an outline
     in ink would disappear. */
  onDark: "border-2 border-paper/45 text-paper hover:border-paper hover:bg-paper/10",
};

const sizes: Record<Size, string> = {
  sm: "h-9 px-4 text-[0.7rem]",
  md: "h-12 px-6 text-[0.8rem]",
  lg: "h-14 px-9 text-[0.9rem]",
};

/* `children` is narrowed back to ReactNode: HTMLMotionProps widens it to accept
   MotionValues, which Link cannot render. */
interface ButtonProps extends Omit<HTMLMotionProps<"button">, "ref" | "children"> {
  variant?: Variant;
  size?: Size;
  href?: string;
  children?: React.ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "pitch", size = "md", href, className, children, onClick, ...props },
  ref,
) {
  const classes = cn(base, variants[variant], sizes[size], className);

  /* Press is a scale-down rather than a colour shift: it survives reduced
     motion (the CSS clamp turns it near-instant) and reads on any background. */
  const feedback = {
    whileHover: { y: -1 },
    whileTap: { scale: 0.97 },
    transition: transition.micro,
  } as const;

  if (href) {
    /* onClick is forwarded explicitly: callers use it to close the drawer or
       overlay they are navigating out of, and dropping it silently would leave
       the panel open over the new page. */
    return (
      <motion.div {...feedback} className="inline-flex">
        <Link
          href={href}
          className={classes}
          onClick={onClick as React.MouseEventHandler<HTMLAnchorElement> | undefined}
        >
          {children}
        </Link>
      </motion.div>
    );
  }

  return (
    <motion.button ref={ref} className={classes} onClick={onClick} {...feedback} {...props}>
      {children}
    </motion.button>
  );
});
