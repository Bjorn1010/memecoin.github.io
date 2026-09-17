"use client";

import Link from "next/link";
import { useRef } from "react";
import { motion, useReducedMotion, useScroll, useTransform } from "motion/react";
import { ArrowUpRight } from "lucide-react";
import { Jersey } from "@/components/ui/Jersey";
import type { Team } from "@/lib/types";

/* Horizontal rail, driven by vertical scroll.
 *
 * Twenty-two clubs is too many for a grid on the homepage and too few to hide
 * behind a link. Scrolling the page pushes the row sideways, so the whole
 * roster passes the viewport without the reader doing anything unusual.
 *
 * The accessibility trap with this pattern is that the off-screen items are
 * unreachable by keyboard and by touch. So: the container is a real
 * overflow-x region with its own scrollbar hidden, focusable links inside it,
 * and under reduced motion — or on touch, where scroll-jacking is worst — the
 * scroll-driven transform is dropped and it becomes an ordinary swipeable row.
 */
export function ClubRail({ teams, counts }: { teams: Team[]; counts: Record<string, number> }) {
  const ref = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] });
  /* Modest travel: the row drifts by a third of its own width, which is
     enough to feel alive without outrunning the reader. */
  const x = useTransform(scrollYProgress, [0, 1], ["2%", "-32%"]);

  return (
    <div ref={ref} className="relative overflow-hidden py-2">
      <motion.ul
        style={reduced ? undefined : { x }}
        className="no-scrollbar flex gap-4 overflow-x-auto pb-2 lg:overflow-visible"
      >
        {teams.map((team) => (
          <li key={team.slug} className="w-[240px] shrink-0 lg:w-[260px]">
            <Link
              href={`/clubs/${team.slug}`}
              className="group relative flex h-[300px] flex-col justify-between overflow-hidden border border-line bg-base p-5 transition-colors hover:border-steel-600 lg:h-[340px]"
            >
              <div
                aria-hidden
                className="pointer-events-none absolute inset-0 opacity-40 transition-all duration-[--duration-premium] ease-[--ease-out-expo] group-hover:scale-110 group-hover:opacity-75"
                style={{
                  background: `radial-gradient(70% 60% at 50% 112%, ${team.colorway.primary}88, transparent 72%)`,
                }}
              />
              <span
                aria-hidden
                className="pointer-events-none absolute -right-3 top-1 font-display text-[5rem] leading-none text-ink/[0.06]"
              >
                {team.monogram}
              </span>

              <div className="relative flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate font-display text-lg uppercase leading-tight text-ink">
                    {team.name}
                  </p>
                  <p className="label-mono mt-1.5 text-steel-500">{counts[team.slug] ?? 0} réf.</p>
                </div>
                <ArrowUpRight
                  size={16}
                  className="shrink-0 text-steel-500 transition-all group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-volt"
                />
              </div>

              <div className="pointer-events-none relative mx-auto mt-3 w-full max-w-[150px] transition-transform duration-[--duration-premium] ease-[--ease-out-expo] group-hover:-translate-y-2">
                <Jersey colorway={team.colorway} monogram={team.monogram} number="9" />
              </div>
            </Link>
          </li>
        ))}
      </motion.ul>
    </div>
  );
}
