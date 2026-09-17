"use client";

import { motion, useReducedMotion } from "motion/react";
import { cn } from "@/lib/utils";

/* Headline reveal, split by word.
 *
 * By word and not by character on purpose: a character split creates one DOM
 * node per letter, and on a headline this size that is a lot of nodes for an
 * effect nobody consciously notices. Words read as deliberate; characters read
 * as a typewriter.
 *
 * Accessibility: the visible words are hidden from assistive tech and the
 * whole string is exposed once on the wrapper, so a screen reader announces
 * "Un maillot n'est jamais qu'un maillot" rather than spelling out fragments.
 */
export function WordReveal({
  text,
  as: Tag = "h2",
  className,
  delay = 0,
}: {
  text: string;
  as?: "h1" | "h2" | "h3" | "p";
  className?: string;
  delay?: number;
}) {
  const reduced = useReducedMotion();
  const words = text.split(" ");

  if (reduced) return <Tag className={className}>{text}</Tag>;

  return (
    <Tag className={className} aria-label={text}>
      {words.map((word, i) => (
        <span key={`${word}-${i}`} aria-hidden className="inline-block overflow-hidden align-bottom">
          <motion.span
            className="inline-block"
            initial={{ y: "110%" }}
            whileInView={{ y: 0 }}
            viewport={{ once: true, amount: 0.4 }}
            transition={{
              duration: 0.75,
              delay: delay + i * 0.055,
              ease: [0.16, 1, 0.3, 1],
            }}
          >
            {word}
            {i < words.length - 1 ? " " : ""}
          </motion.span>
        </span>
      ))}
    </Tag>
  );
}

/* Same idea for a block of body copy: one fade, no per-word split. Splitting a
   paragraph is the anti-pattern — it slows reading and bloats the DOM. */
export function FadeUp({
  children,
  className,
  delay = 0,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  const reduced = useReducedMotion();
  if (reduced) return <div className={className}>{children}</div>;
  return (
    <motion.div
      className={cn(className)}
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.6, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  );
}
