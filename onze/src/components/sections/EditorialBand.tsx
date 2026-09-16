"use client";

import Link from "next/link";
import { useRef } from "react";
import { motion, useReducedMotion, useScroll, useTransform } from "motion/react";
import { ArrowRight } from "lucide-react";
import { Img } from "@/components/ui/Img";
import { cn } from "@/lib/utils";

/* A full-bleed photograph with a statement over it.
 *
 * This is the component that makes the homepage read as a campaign rather than
 * a catalogue, so it is deliberately the same shape every time it appears —
 * the rhythm comes from repetition, and varying the treatment per section
 * would just look like four different designers.
 *
 * `align` moves the copy to whichever side the photograph leaves empty. */
export function EditorialBand({
  image,
  eyebrow,
  title,
  body,
  cta,
  href,
  align = "left",
  tall = false,
}: {
  image: string;
  eyebrow: string;
  title: React.ReactNode;
  body?: string;
  cta: string;
  href: string;
  align?: "left" | "right" | "center";
  tall?: boolean;
}) {
  const ref = useRef<HTMLElement>(null);
  const reduced = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] });
  /* The image moves against the scroll across the whole band, which is what
     separates a parallax section from a static one with a background. */
  const y = useTransform(scrollYProgress, [0, 1], ["-8%", "8%"]);

  return (
    <section
      ref={ref}
      className={cn(
        "relative isolate flex overflow-hidden bg-void",
        tall ? "min-h-[88svh]" : "min-h-[62svh]",
        align === "center" ? "items-center" : "items-end",
      )}
    >
      <motion.div aria-hidden style={reduced ? undefined : { y }} className="absolute -inset-y-[8%] inset-x-0 -z-10">
        <Img name={image} alt="" ratio="16/9" sizes="100vw" className="h-full w-full object-cover" />
      </motion.div>
      <div
        aria-hidden
        className={cn(
          "absolute inset-0 -z-10",
          align === "center"
            ? "bg-void/70"
            : align === "right"
              ? "bg-gradient-to-l from-void via-void/75 to-void/10"
              : "bg-gradient-to-r from-void via-void/75 to-void/10",
        )}
      />

      <div
        className={cn(
          "mx-auto w-full max-w-[1600px] px-5 py-20 lg:px-10 lg:py-28",
          align === "center" && "text-center",
        )}
      >
        <motion.div
          initial={reduced ? undefined : { opacity: 0, y: 28 }}
          whileInView={reduced ? undefined : { opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.35 }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className={cn(
            "max-w-2xl",
            align === "right" && "ml-auto",
            align === "center" && "mx-auto",
          )}
        >
          <p className={cn("eyebrow label-mono mb-5", align === "center" && "justify-center")}>
            {eyebrow}
          </p>
          <h2 className="font-display text-display text-ink">{title}</h2>
          {body && (
            <p className="mt-6 max-w-lg text-base leading-relaxed text-steel-200">{body}</p>
          )}
          <Link
            href={href}
            className="group mt-9 inline-flex items-center gap-2 border-b-2 border-volt pb-2 font-display text-sm uppercase tracking-wide text-ink transition-colors hover:text-volt"
          >
            {cta}
            <ArrowRight size={16} strokeWidth={2.5} className="transition-transform group-hover:translate-x-1" />
          </Link>
        </motion.div>
      </div>
    </section>
  );
}
