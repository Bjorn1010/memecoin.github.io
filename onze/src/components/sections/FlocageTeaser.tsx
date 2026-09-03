"use client";

import { useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { Jersey } from "@/components/ui/Jersey";
import { Button } from "@/components/ui/Button";
import { Reveal } from "@/components/motion/Reveal";
import { clubs } from "@/lib/data/teams";
import { transition } from "@/lib/motion";

/* The flocage is the one thing a jersey shop can offer that a generic clothing
 * store cannot, so it gets its own section rather than hiding as a field on the
 * product page. Typing here updates the shirt live — the demo IS the pitch. */

const TEAM = clubs.find((c) => c.slug === "paris-saint-germain") ?? clubs[0];

export function FlocageTeaser() {
  const [name, setName] = useState("");
  const [number, setNumber] = useState("");
  const reduced = useReducedMotion();

  return (
    <section
      className="pitch-lines relative overflow-hidden border-y border-ink/8 bg-base py-24 lg:py-32"
      aria-labelledby="flocage"
    >
      <div aria-hidden className="floodlight pointer-events-none absolute inset-0" />

      <div className="relative mx-auto grid max-w-[1600px] items-center gap-12 px-5 lg:grid-cols-2 lg:px-10">
        <div>
          <Reveal>
            <p className="label-mono mb-4 flex items-center gap-3 text-pitch">
              <span className="inline-block h-px w-8 bg-pitch" />
              Flocage inclus
            </p>
          </Reveal>
          <Reveal index={1}>
            <h2 id="flocage" className="font-display text-display text-ink">
              Votre nom.
              <br />
              Votre <span className="text-pitch">numéro</span>.
            </h2>
          </Reveal>
          <Reveal index={2}>
            <p className="mt-5 max-w-md text-sm leading-relaxed text-steel-400">
              Nom, numéro et écusson appliqués à chaud avant expédition. Sans
              supplément, sur chaque maillot du catalogue.
            </p>
          </Reveal>

          <Reveal index={3}>
            <div className="mt-8 grid max-w-md grid-cols-[1fr_96px] gap-3">
              <label className="block">
                <span className="label-mono mb-2 block text-steel-500">Nom</span>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value.replace(/[^a-zA-ZÀ-ÿ .-]/g, ""))}
                  maxLength={12}
                  placeholder="VOTRE NOM"
                  aria-label="Nom à floquer"
                  className="number-plate w-full rounded-sm border border-ink/12 bg-surface px-3 py-3 uppercase tracking-wide text-ink outline-none transition-colors placeholder:text-steel-700 focus:border-pitch"
                />
              </label>
              <label className="block">
                <span className="label-mono mb-2 block text-steel-500">N°</span>
                <input
                  value={number}
                  onChange={(e) => setNumber(e.target.value.replace(/\D/g, "").slice(0, 2))}
                  inputMode="numeric"
                  placeholder="10"
                  aria-label="Numéro à floquer"
                  className="number-plate w-full rounded-sm border border-ink/12 bg-surface px-3 py-3 text-center text-lg text-ink outline-none transition-colors placeholder:text-steel-700 focus:border-pitch"
                />
              </label>
            </div>
          </Reveal>

          <Reveal index={4}>
            <Button href="/maillots" size="lg" className="mt-8">
              Choisir un maillot
            </Button>
          </Reveal>
        </div>

        {/* Live preview */}
        <motion.div
          initial={reduced ? undefined : { opacity: 0, scale: 0.94 }}
          whileInView={reduced ? undefined : { opacity: 1, scale: 1 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={transition.premium}
          className="relative mx-auto h-[420px] w-full max-w-[380px] lg:h-[520px]"
        >
          <div
            aria-hidden
            className="pointer-events-none absolute left-1/2 top-1/2 h-[65%] w-[65%] -translate-x-1/2 -translate-y-1/2 rounded-full blur-[90px]"
            style={{ background: `${TEAM.colorway.primary}44` }}
          />
          <Jersey
            colorway={TEAM.colorway}
            monogram={TEAM.monogram}
            view="back"
            playerName={name || "VOTRE NOM"}
            number={number || "10"}
          />
        </motion.div>
      </div>
    </section>
  );
}
