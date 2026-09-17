"use client";

import Link from "next/link";
import { useRef } from "react";
import { motion, useReducedMotion, useScroll, useTransform, type MotionValue } from "motion/react";
import { ArrowRight } from "lucide-react";
import { Jersey } from "@/components/ui/Jersey";
import type { Team } from "@/lib/types";

/* The pinned chapter.
 *
 * A tall scroll container with a sticky viewport inside it: the shirt holds
 * still while three statements hand over to each other, and the kit turns
 * from front to back as the flocage is described. It is the one place on the
 * page where scrolling drives a sequence rather than just moving down a
 * document.
 *
 * It earns its length by selling the thing that actually differentiates the
 * shop — the name on the back is included — instead of being a scroll effect
 * for its own sake.
 *
 * Under reduced motion the whole mechanism collapses to three stacked blocks,
 * because pinning is exactly the kind of motion that causes trouble.
 */

const BEATS = [
  {
    kicker: "01 — Choisissez",
    title: "Le club. La saison.",
    body: "Domicile, extérieur, third, ou une saison qu'on ne rejoue plus que de mémoire. Tout le catalogue est floqué sur demande.",
  },
  {
    kicker: "02 — Personnalisez",
    title: "Votre nom dans le dos.",
    body: "Nom et numéro appliqués à chaud avant l'expédition. Inclus sur chaque maillot — pas une option à cocher en fin de panier.",
  },
  {
    kicker: "03 — Recevez",
    title: "Sous 48 heures.",
    body: "Expédié de Suisse avec un numéro de suivi. Trente jours pour changer d'avis sur tout ce qui n'a pas été floqué sur mesure.",
  },
];

function Beat({
  beat,
  index,
  progress,
  isLast,
}: {
  beat: (typeof BEATS)[number];
  index: number;
  progress: MotionValue<number>;
  isLast: boolean;
}) {
  /* Each statement owns a third of the scroll and cross-fades with its
     neighbours at the seams.
     
     Derived with a function rather than an input/output range pair: the range
     form made Motion build keyframes whose offsets fell outside 0–1 for the
     first and last beat, which throws "offsets must be monotonically
     non-decreasing" at runtime. A plain function has no keyframes to order. */
  const span = 1 / BEATS.length;
  const start = index * span;
  const RAMP = 0.14;

  /* Each beat owns its slice outright: it is fully out by the time the next
     one starts to come in. An overlapping cross-fade sounds nicer but these
     statements are stacked in the same box, so any overlap renders as two
     headlines printed on top of each other.

     The final beat never ramps down — the section releases at progress 1, and
     fading out there would end the chapter on a half-dissolved sentence. */
  const window_ = (v: number) => {
    const local = (v - start) / span;
    if (local < 0) return 0;
    if (local > 1) return isLast ? 1 : 0;
    if (local < RAMP) return local / RAMP;
    if (!isLast && local > 1 - RAMP) return (1 - local) / RAMP;
    return 1;
  };

  const opacity = useTransform(progress, (v) => Math.min(1, Math.max(0, window_(v))));
  const y = useTransform(progress, (v) => 28 * (1 - Math.min(1, Math.max(0, window_(v)))));

  return (
    <motion.div style={{ opacity, y }} className="absolute inset-x-0 top-0">
      <p className="label-mono mb-5 text-volt">{beat.kicker}</p>
      <h3 className="font-display text-display text-ink">{beat.title}</h3>
      <p className="mt-6 max-w-md text-base leading-relaxed text-steel-200">{beat.body}</p>
    </motion.div>
  );
}

export function PinnedStory({ team }: { team: Team }) {
  const ref = useRef<HTMLElement>(null);
  const reduced = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end end"] });

  /* Front at the top of the chapter, back by the time the flocage beat is on
     screen — as a cross-fade between the two real views, not a 180° flip.
     Rotating the artwork mirrors it, so the crest and the number came out
     backwards; and the point of this beat is to show the actual printed back. */
  const frontOpacity = useTransform(scrollYProgress, [0.26, 0.42], [1, 0]);
  const backOpacity = useTransform(scrollYProgress, [0.26, 0.42], [0, 1]);
  /* A shallow turn either side of the swap, purely for dimensionality. */
  const rotate = useTransform(scrollYProgress, [0, 0.34, 1], [-10, 0, 10]);
  const kitScale = useTransform(scrollYProgress, [0, 0.5, 1], [0.92, 1, 0.94]);
  const railHeight = useTransform(scrollYProgress, [0, 1], ["0%", "100%"]);

  if (reduced) {
    return (
      <section className="border-y border-line bg-base">
        <div className="mx-auto max-w-[1600px] px-5 py-20 lg:px-10">
          <p className="eyebrow label-mono mb-10">Comment ça marche</p>
          <div className="grid gap-12 lg:grid-cols-3">
            {BEATS.map((b) => (
              <div key={b.kicker}>
                <p className="label-mono mb-4 text-volt">{b.kicker}</p>
                <h3 className="font-display text-title text-ink">{b.title}</h3>
                <p className="mt-4 text-sm leading-relaxed text-steel-200">{b.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    );
  }

  return (
    <section ref={ref} className="relative h-[320svh] border-y border-line bg-base">
      <div className="sticky top-0 flex h-svh items-center overflow-hidden">
        {/* Colour field from the featured kit, so the chapter is tinted by the
            shirt it is talking about. */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-40"
          style={{
            background: `radial-gradient(50% 60% at 78% 50%, ${team.colorway.primary}55, transparent 70%)`,
          }}
        />

        <div className="relative mx-auto grid w-full max-w-[1600px] items-center gap-10 px-5 lg:grid-cols-[1fr_0.9fr] lg:px-10">
          <div className="flex items-start gap-6">
            {/* Progress rail — the reader's position inside the chapter. */}
            <div aria-hidden className="relative mt-2 hidden h-40 w-px shrink-0 bg-line lg:block">
              <motion.div style={{ height: railHeight }} className="absolute inset-x-0 top-0 bg-volt" />
            </div>

            <div className="relative min-h-[320px] flex-1">
              {BEATS.map((beat, i) => (
                <Beat
                  key={beat.kicker}
                  beat={beat}
                  index={i}
                  progress={scrollYProgress}
                  isLast={i === BEATS.length - 1}
                />
              ))}

              {/* Anchored below the rotating statements so the exit is always
                  in the same place regardless of which beat is showing. */}
              <div className="absolute inset-x-0 top-[300px]">
                <Link
                  href="/maillots"
                  className="group inline-flex items-center gap-2 border-b-2 border-volt pb-2 font-display text-sm uppercase tracking-wide text-ink transition-colors hover:text-volt"
                >
                  Choisir un maillot
                  <ArrowRight
                    size={16}
                    strokeWidth={2.5}
                    className="transition-transform group-hover:translate-x-1"
                  />
                </Link>
              </div>
            </div>
          </div>

          <motion.div
            style={{ scale: kitScale }}
            className="pointer-events-none mx-auto w-full max-w-[260px] lg:max-w-[380px]"
          >
            <motion.div style={{ rotateY: rotate }} className="relative [perspective:1200px]">
              <motion.div style={{ opacity: frontOpacity }}>
                <Jersey colorway={team.colorway} monogram={team.monogram} number="10" />
              </motion.div>
              <motion.div style={{ opacity: backOpacity }} className="absolute inset-0">
                <Jersey
                  colorway={team.colorway}
                  monogram={team.monogram}
                  number="10"
                  view="back"
                  playerName={team.name.toUpperCase()}
                />
              </motion.div>
            </motion.div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
