"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { ArrowUpRight } from "lucide-react";
import type { Team } from "@/lib/types";
import { Jersey } from "@/components/ui/Jersey";
import { transition } from "@/lib/motion";

/* Shared by "Shop by club" and "Shop by country". One immersive card per team:
 * the colourway drives an animated field that only resolves on hover, so the
 * grid is calm at rest and alive under the pointer. */

export function TeamCard({
  team,
  count,
  href,
  index = 0,
  size = "md",
}: {
  team: Team;
  count: number;
  href: string;
  index?: number;
  size?: "md" | "lg";
}) {
  const reduced = useReducedMotion();

  return (
    <motion.div
      initial={{ opacity: 0, y: 28 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ ...transition.premium, delay: Math.min(index, 6) * 0.05 }}
    >
      <Link
        href={href}
        className={`group relative flex flex-col justify-between overflow-hidden rounded-xl border border-ink/8 bg-surface p-6 transition-colors duration-[--duration-standard] hover:border-ink/20 ${
          size === "lg" ? "min-h-[420px]" : "min-h-[300px]"
        }`}
      >
        {/* Colour field. Scales and brightens on hover — the "depth" cue. */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-45 transition-all duration-[--duration-premium] ease-[--ease-out-expo] group-hover:scale-110 group-hover:opacity-80"
          style={{
            background: `radial-gradient(75% 65% at 50% 110%, ${team.colorway.primary}88, transparent 72%),
                         radial-gradient(45% 45% at 15% 10%, ${team.colorway.secondary}44, transparent 70%)`,
          }}
        />

        {/* Oversized monogram, drifting slightly against the kit for parallax. */}
        <span
          aria-hidden
          className="pointer-events-none absolute -right-4 top-2 font-display text-[7rem] leading-none text-ink/6 transition-transform duration-[--duration-premium] ease-[--ease-out-expo] group-hover:-translate-y-2 group-hover:translate-x-1"
        >
          {team.monogram}
        </span>

        <div className="relative z-10 flex items-start justify-between">
          <div>
            <p className="font-display text-xl uppercase leading-tight text-ink">{team.name}</p>
            <p className="label-mono mt-1.5 text-steel-500">{count} références</p>
          </div>
          <ArrowUpRight
            size={18}
            className="shrink-0 text-steel-500 transition-all duration-[--duration-standard] group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-pitch"
          />
        </div>

        <div
          className={`pointer-events-none relative z-0 mx-auto mt-4 w-full transition-transform duration-[--duration-premium] ease-[--ease-out-expo] ${
            reduced ? "" : "group-hover:-translate-y-2 group-hover:scale-105"
          } ${size === "lg" ? "max-w-[240px]" : "max-w-[180px]"}`}
        >
          <Jersey colorway={team.colorway} monogram={team.monogram} number="9" />
        </div>
      </Link>
    </motion.div>
  );
}
