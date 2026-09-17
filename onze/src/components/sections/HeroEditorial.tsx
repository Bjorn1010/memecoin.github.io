"use client";

import Link from "next/link";
import { motion, useReducedMotion, useScroll, useTransform } from "motion/react";
import { useRef } from "react";
import { ArrowRight } from "lucide-react";
import { Img } from "@/components/ui/Img";
import { Counter } from "@/components/motion/Counter";
import { Magnetic } from "@/components/motion/Magnetic";

/* The hero.
 *
 * One photograph, one sentence, two ways in. The entrance is staged rather
 * than simultaneous — the image resolves first, then the line lands word by
 * word, then the buttons arrive — because a hero that appears all at once
 * reads as a page loading, and a hero that arrives in order reads as a title
 * sequence. Every part of it is skipped under prefers-reduced-motion.
 */

const LINES = ["Portez", "le jeu."];

export function HeroEditorial({ references, clubCount }: { references: number; clubCount: number }) {
  const ref = useRef<HTMLElement>(null);
  const reduced = useReducedMotion();

  /* Parallax: the photograph drifts slower than the page, which is what makes
     the type feel like it is sitting in front of the stadium rather than on
     top of it. Deliberately shallow — past ~12% it reads as a glitch. */
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] });
  const imageY = useTransform(scrollYProgress, [0, 1], ["0%", "12%"]);
  const imageScale = useTransform(scrollYProgress, [0, 1], [1, 1.12]);
  const copyY = useTransform(scrollYProgress, [0, 1], ["0%", "-18%"]);
  const copyFade = useTransform(scrollYProgress, [0, 0.8], [1, 0]);

  return (
    <section
      ref={ref}
      className="relative isolate flex min-h-[92svh] items-end overflow-hidden bg-void"
    >
      <motion.div
        aria-hidden
        style={reduced ? undefined : { y: imageY, scale: imageScale }}
        initial={reduced ? undefined : { scale: 1.16, opacity: 0 }}
        animate={reduced ? undefined : { scale: 1, opacity: 1 }}
        transition={{ duration: 1.5, ease: [0.16, 1, 0.3, 1] }}
        className="absolute inset-0 -z-10"
      >
        <Img
          name="hero"
          alt=""
          ratio="16/9"
          priority
          sizes="100vw"
          className="h-full w-full object-cover"
        />
      </motion.div>

      {/* Two veils rather than one: a bottom-weighted wash for the copy, and a
          left-weighted one so the headline never fights the floodlights. */}
      <div
        aria-hidden
        className="absolute inset-0 -z-10 bg-gradient-to-t from-void via-void/70 to-void/20"
      />
      <div
        aria-hidden
        className="absolute inset-0 -z-10 bg-gradient-to-r from-void/85 via-void/30 to-transparent"
      />

      <motion.div
        style={reduced ? undefined : { y: copyY, opacity: copyFade }}
        className="mx-auto w-full max-w-[1600px] px-5 pb-16 pt-40 lg:px-10 lg:pb-24"
      >
        <motion.p
          initial={reduced ? undefined : { opacity: 0, y: 12 }}
          animate={reduced ? undefined : { opacity: 1, y: 0 }}
          transition={{ delay: 0.5, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="eyebrow label-mono mb-6"
        >
          Saison 26/27 — en ligne
        </motion.p>

        <h1 className="font-display text-mega text-ink">
          {LINES.map((line, i) => (
            <span key={line} className="block overflow-hidden">
              <motion.span
                className="block"
                initial={reduced ? undefined : { y: "100%" }}
                animate={reduced ? undefined : { y: 0 }}
                transition={{ delay: 0.62 + i * 0.1, duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
              >
                {line}
              </motion.span>
            </span>
          ))}
        </h1>

        <motion.div
          initial={reduced ? undefined : { opacity: 0, y: 16 }}
          animate={reduced ? undefined : { opacity: 1, y: 0 }}
          transition={{ delay: 0.95, duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          className="mt-8 flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between"
        >
          <p className="max-w-md text-base leading-relaxed text-steel-200">
            Maillots de club et de sélection, rétros et éditions limitées. Flocage nom et numéro
            inclus, expédié sous 48&nbsp;h depuis la Suisse.
          </p>

          <div className="flex flex-wrap items-center gap-3">
            <Magnetic className="inline-block">
              <Link
                href="/maillots"
                className="group inline-flex items-center gap-2 bg-volt px-7 py-4 font-display text-sm uppercase tracking-wide text-on-volt transition-colors hover:bg-ink"
              >
                Voir les maillots
                <ArrowRight
                  size={16}
                  className="transition-transform group-hover:translate-x-1"
                  strokeWidth={2.5}
                />
              </Link>
            </Magnetic>
            <Link
              href="/collections/nouveautes"
              className="inline-flex items-center gap-2 border border-ink/25 px-7 py-4 font-display text-sm uppercase tracking-wide text-ink transition-colors hover:border-ink hover:bg-ink hover:text-void"
            >
              Nouveautés
            </Link>
          </div>
        </motion.div>

        {/* The numbers are read off the catalogue, not written into the copy,
            so they cannot drift away from what the shop actually stocks. */}
        <motion.dl
          initial={reduced ? undefined : { opacity: 0 }}
          animate={reduced ? undefined : { opacity: 1 }}
          transition={{ delay: 1.15, duration: 0.8 }}
          className="mt-12 flex flex-wrap gap-x-12 gap-y-4 border-t border-ink/15 pt-6"
        >
          <div>
            <dt className="label-mono text-steel-400">Références</dt>
            <dd className="scoreboard mt-1 text-2xl text-ink">
              <Counter value={references} />
            </dd>
          </div>
          <div>
            <dt className="label-mono text-steel-400">Clubs &amp; sélections</dt>
            <dd className="scoreboard mt-1 text-2xl text-ink">
              <Counter value={clubCount} />
            </dd>
          </div>
          <div>
            <dt className="label-mono text-steel-400">Expédition</dt>
            <dd className="scoreboard mt-1 text-2xl text-ink">48 h</dd>
          </div>
          <div>
            <dt className="label-mono text-steel-400">Flocage</dt>
            <dd className="scoreboard mt-1 text-2xl text-volt">Inclus</dd>
          </div>
        </motion.dl>
      </motion.div>
    </section>
  );
}
