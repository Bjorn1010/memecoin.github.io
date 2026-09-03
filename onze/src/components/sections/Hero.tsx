"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion, useScroll, useTransform } from "motion/react";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Jersey } from "@/components/ui/Jersey";
import { clubs } from "@/lib/data/teams";
import { revealCinematic, transition } from "@/lib/motion";

/* Three.js is ~150 kB gzipped. It must never sit in the initial bundle, so the
 * scene is a dynamic client-only import that is requested only once we've
 * decided this device should actually run it. */
const JerseyScene = dynamic(() => import("@/components/3d/JerseyScene"), {
  ssr: false,
});

/* Striped and high-chroma: the kit has to hold its own against a green pitch,
   and the stripes give the cloth drape something to deform. */
const HERO_TEAM = clubs.find((c) => c.slug === "barcelona") ?? clubs[0];

export function Hero() {
  const ref = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const [enable3D, setEnable3D] = useState(false);

  /* Gate the WebGL scene on: reduced motion off, a pointer that can actually
     drive it, enough cores to spare, and a viewport worth rendering into.
     Everyone else gets the SVG kit, which is not a downgrade — it is the same
     artwork, just not lit in real time. */
  useEffect(() => {
    if (reduced) return;
    const coarse = window.matchMedia("(pointer: coarse)").matches;
    const cores = navigator.hardwareConcurrency ?? 4;
    const narrow = window.innerWidth < 768;
    if (coarse || narrow || cores < 4) return;

    /* Defer past first paint so the 3D chunk never competes with LCP. */
    const id = window.setTimeout(() => setEnable3D(true), 600);
    return () => window.clearTimeout(id);
  }, [reduced]);

  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end start"],
  });

  const kitY = useTransform(scrollYProgress, [0, 1], ["0%", "16%"]);
  const copyY = useTransform(scrollYProgress, [0, 1], ["0%", "50%"]);
  const opacity = useTransform(scrollYProgress, [0, 0.8], [1, 0]);

  return (
    /* The pitch. Everything below this section is white — putting turf only
       here means the shop reads as football in the first half second without
       the whole site turning into a green wall. */
    <section
      ref={ref}
      className="turf pitch-lines grain relative flex min-h-[100svh] items-center overflow-hidden pt-24"
      aria-label="Nouvelle collection"
    >
      <div aria-hidden className="floodlight pointer-events-none absolute inset-0" />
      {/* Fade into the white page below, so the turf ends as a horizon rather
          than a hard band. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-void to-transparent"
      />

      <div className="relative mx-auto grid w-full max-w-[1600px] items-center gap-8 px-5 lg:grid-cols-2 lg:px-10">
        <motion.div
          style={reduced ? undefined : { y: copyY, opacity }}
          className="relative z-10 order-2 lg:order-1"
        >
          <motion.p
            custom={0}
            variants={revealCinematic}
            initial="hidden"
            animate="visible"
            className="label-mono mb-5 inline-flex items-center gap-2 rounded-full bg-cup px-3 py-1.5 text-ink"
          >
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-ink" />
            Saison 26/27 — disponible
          </motion.p>

          <h1 className="font-display text-hero text-paper">
            {["Le kit", "avant", "tout le monde"].map((line, i) => (
              <motion.span
                key={line}
                custom={i + 1}
                variants={revealCinematic}
                initial="hidden"
                animate="visible"
                className="block drop-shadow-[0_2px_12px_rgb(5_52_28_/_0.35)]"
              >
                {i === 2 ? (
                  <>
                    tout le <span className="text-cup">monde</span>
                  </>
                ) : (
                  line
                )}
              </motion.span>
            ))}
          </h1>

          <motion.p
            custom={4}
            variants={revealCinematic}
            initial="hidden"
            animate="visible"
            className="mt-6 max-w-md text-base leading-relaxed text-paper/85"
          >
            Maillots, kits enfants, rétros et éditions limitées. Flocage nom et
            numéro inclus, expédié sous 48&nbsp;h depuis la Suisse.
          </motion.p>

          <motion.div
            custom={5}
            variants={revealCinematic}
            initial="hidden"
            animate="visible"
            className="mt-8 flex flex-wrap items-center gap-3"
          >
            {/* White on green is the highest-contrast button available here, and
                it keeps the solid pitch-green CTA reserved for white sections. */}
            <Button
              href="/maillots"
              size="lg"
              variant="solid"
              className="bg-paper !text-pitch-deep hover:bg-cup"
            >
              Explorer les maillots
              <ArrowRight size={16} />
            </Button>
            <Button href="/collections/nouveautes" variant="onDark" size="lg">
              Voir les nouveautés
            </Button>
          </motion.div>

          <motion.dl
            custom={6}
            variants={revealCinematic}
            initial="hidden"
            animate="visible"
            className="mt-10 flex gap-8 border-t border-paper/25 pt-5 sm:gap-10"
          >
            {[
              { k: "Références", v: "180+" },
              { k: "Clubs & sélections", v: "36" },
              { k: "Expédition", v: "48 h" },
            ].map((s) => (
              <div key={s.k}>
                <dt className="label-mono text-paper/70">{s.k}</dt>
                <dd className="scoreboard mt-1 text-2xl text-paper">{s.v}</dd>
              </div>
            ))}
          </motion.dl>
        </motion.div>

        <motion.div
          style={reduced ? undefined : { y: kitY, opacity }}
          className="relative order-1 h-[46svh] min-h-[320px] lg:order-2 lg:h-[76svh]"
        >
          {/* Light bloom behind the kit so it separates from the turf. */}
          <div
            aria-hidden
            className="pointer-events-none absolute left-1/2 top-1/2 h-[70%] w-[70%] -translate-x-1/2 -translate-y-1/2 rounded-full bg-paper/20 blur-[100px]"
          />

          {enable3D ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.8 }}
              className="absolute inset-0"
            >
              <JerseyScene colorway={HERO_TEAM.colorway} monogram={HERO_TEAM.monogram} />
            </motion.div>
          ) : (
            /* Not a placeholder — the shipped experience for touch, reduced
               motion and low-core devices. */
            <motion.div
              initial={{ opacity: 0, scale: 0.94, filter: "blur(10px)" }}
              animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
              transition={{ ...transition.cinematic, delay: 0.15 }}
              className="absolute inset-0 grid place-items-center"
            >
              <div className="h-full max-h-[540px] w-auto drop-shadow-[0_20px_40px_rgb(5_52_28_/_0.4)]">
                <Jersey colorway={HERO_TEAM.colorway} monogram={HERO_TEAM.monogram} number="10" />
              </div>
            </motion.div>
          )}
        </motion.div>
      </div>

      <motion.div
        style={reduced ? undefined : { opacity }}
        className="pointer-events-none absolute bottom-7 left-1/2 hidden -translate-x-1/2 lg:block"
      >
        <span className="label-mono text-paper/60">Défiler</span>
      </motion.div>
    </section>
  );
}
