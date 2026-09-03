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
const StadiumScene = dynamic(() => import("@/components/3d/StadiumScene"), {
  ssr: false,
});

/* Three kits with distinct patterns and high-chroma colourways — a carousel of
   three whites would read as one object turning. */
const CAST = ["barcelona", "paris-saint-germain", "borussia-dortmund"]
  .map((slug) => clubs.find((c) => c.slug === slug))
  .filter((c): c is (typeof clubs)[number] => Boolean(c));

export function Hero() {
  const ref = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const [enable3D, setEnable3D] = useState(false);

  /* Gate the WebGL scene on: reduced motion off, a pointer that can actually
     drive it, enough cores to spare, and a viewport worth rendering into.
     Everyone else gets the drawn kits, which are the same artwork. */
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

  const sceneY = useTransform(scrollYProgress, [0, 1], ["0%", "14%"]);
  const copyY = useTransform(scrollYProgress, [0, 1], ["0%", "48%"]);
  const opacity = useTransform(scrollYProgress, [0, 0.8], [1, 0]);

  return (
    <section
      ref={ref}
      className="turf relative flex min-h-[100svh] items-center overflow-hidden pt-24"
      aria-label="Nouvelle collection"
    >
      {/* The stadium fills the whole hero and the copy sits over it, rather
          than the kit living in its own column — that is the difference
          between a product shot and a matchday. */}
      <motion.div
        style={reduced ? undefined : { y: sceneY }}
        className="pointer-events-none absolute inset-0"
        aria-hidden
      >
        {enable3D ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 1 }}
            className="absolute inset-0"
          >
            <StadiumScene teams={CAST} />
          </motion.div>
        ) : (
          /* Not a placeholder — the shipped experience for touch, reduced
             motion and low-core devices: the same three kits, drawn. */
          <div className="absolute inset-0 flex items-center justify-end gap-4 pr-[4vw] lg:pr-[6vw]">
            {CAST.map((team, i) => (
              <motion.div
                key={team.slug}
                initial={{ opacity: 0, y: 24, filter: "blur(10px)" }}
                animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                transition={{ ...transition.cinematic, delay: 0.15 + i * 0.12 }}
                className="drop-shadow-[0_18px_36px_rgb(5_52_28_/_0.45)]"
                style={{
                  height: i === 1 ? "58%" : "46%",
                  opacity: i === 1 ? 1 : 0.85,
                }}
              >
                <Jersey colorway={team.colorway} monogram={team.monogram} number={`${i + 9}`} />
              </motion.div>
            ))}
          </div>
        )}
      </motion.div>

      {/* Legibility scrim: the crowd and turf behind the copy are busy, and
          white type over them needs a ground of its own. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-gradient-to-r from-pitch-deep/85 via-pitch-deep/45 to-transparent"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-void to-transparent"
      />

      <div className="relative mx-auto w-full max-w-[1600px] px-5 lg:px-10">
        <motion.div
          style={reduced ? undefined : { y: copyY, opacity }}
          className="relative z-10 max-w-xl"
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
                className="block drop-shadow-[0_2px_14px_rgb(5_52_28_/_0.5)]"
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
            className="mt-6 max-w-md text-base leading-relaxed text-paper/90"
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
