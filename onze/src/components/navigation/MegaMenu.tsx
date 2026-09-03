"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { ArrowUpRight } from "lucide-react";
import { clubs, countries, leagues } from "@/lib/data/teams";
import { collections } from "@/lib/data/collections";
import { Jersey } from "@/components/ui/Jersey";
import { transition } from "@/lib/motion";

export type MenuKey = "maillots" | "kits" | "collections" | "retros" | "survetements";

/* The panel is a single element that swaps content, so moving between triggers
 * slides rather than tearing down and rebuilding. */

function Column({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <p className="label-mono mb-4 text-steel-500">{title}</p>
      <ul className="space-y-1.5">{children}</ul>
    </div>
  );
}

function Item({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <li>
      <Link
        href={href}
        className="block truncate py-0.5 text-[0.9rem] text-steel-300 transition-colors hover:text-pitch"
      >
        {children}
      </Link>
    </li>
  );
}

/* A featured kit anchors each panel visually — without it the mega menu is
   just a wall of links, which is the exact Shopify look we're avoiding. */
function Feature({ teamSlug }: { teamSlug: string }) {
  const team = [...clubs, ...countries].find((t) => t.slug === teamSlug) ?? clubs[0];
  return (
    <Link
      href={`/maillots?club=${team.slug}`}
      className="group relative flex min-h-[240px] flex-col justify-between overflow-hidden rounded-lg border border-ink/8 bg-surface p-5"
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-40 transition-opacity duration-[--duration-slow] group-hover:opacity-70"
        style={{
          background: `radial-gradient(70% 60% at 50% 100%, ${team.colorway.primary}55, transparent 70%)`,
        }}
      />
      <p className="label-mono relative z-10 text-steel-400">À la une</p>
      <div className="pointer-events-none absolute inset-x-0 bottom-0 top-8 opacity-90 transition-transform duration-[--duration-premium] ease-[--ease-out-expo] group-hover:scale-105">
        <Jersey colorway={team.colorway} monogram={team.monogram} number="10" />
      </div>
      <p className="relative z-10 mt-auto flex items-center gap-1 font-display text-lg text-ink">
        {team.name}
        <ArrowUpRight size={16} className="transition-transform group-hover:translate-x-0.5" />
      </p>
    </Link>
  );
}

export function MegaMenu({ menu, onClose }: { menu: MenuKey; onClose: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={transition.standard}
      className="absolute inset-x-0 top-full hidden border-b border-ink/8 bg-void/95 backdrop-blur-2xl lg:block"
      onMouseLeave={onClose}
    >
      <div className="mx-auto grid max-w-[1600px] grid-cols-[repeat(4,minmax(0,1fr))_320px] gap-10 px-10 py-10">
        {menu === "maillots" && (
          <>
            {leagues.slice(0, 3).map((league) => (
              <Column key={league} title={league}>
                {clubs
                  .filter((c) => c.league === league)
                  .map((c) => (
                    <Item key={c.slug} href={`/maillots?club=${c.slug}`}>
                      {c.name}
                    </Item>
                  ))}
              </Column>
            ))}
            <Column title="Sélections">
              {countries.slice(0, 9).map((c) => (
                <Item key={c.slug} href={`/maillots?pays=${c.slug}`}>
                  {c.name}
                </Item>
              ))}
            </Column>
            <Feature teamSlug="real-madrid" />
          </>
        )}

        {menu === "kits" && (
          <>
            <Column title="Par âge">
              {["4 ans", "6 ans", "8 ans", "10 ans", "12 ans", "14 ans"].map((a) => (
                <Item key={a} href={`/collections/kits-enfants?taille=${a.split(" ")[0]}A`}>
                  {a}
                </Item>
              ))}
            </Column>
            <Column title="Clubs">
              {clubs.slice(0, 8).map((c) => (
                <Item key={c.slug} href={`/collections/kits-enfants?club=${c.slug}`}>
                  {c.name}
                </Item>
              ))}
            </Column>
            <Column title="Sélections">
              {countries.slice(0, 8).map((c) => (
                <Item key={c.slug} href={`/collections/kits-enfants?pays=${c.slug}`}>
                  {c.name}
                </Item>
              ))}
            </Column>
            <Column title="Ensembles">
              <Item href="/collections/kits-enfants">Kit complet</Item>
              <Item href="/collections/kits-enfants?kit=domicile">Domicile</Item>
              <Item href="/collections/kits-enfants?kit=exterieur">Extérieur</Item>
            </Column>
            <Feature teamSlug="bresil" />
          </>
        )}

        {menu === "collections" && (
          <>
            <div className="col-span-4 grid grid-cols-4 gap-4">
              {collections.map((c) => (
                <Link
                  key={c.slug}
                  href={`/collections/${c.slug}`}
                  className="group relative overflow-hidden rounded-md border border-ink/8 bg-surface p-5 transition-colors hover:border-ink/20"
                >
                  <div
                    aria-hidden
                    className="absolute inset-0 opacity-0 transition-opacity duration-[--duration-standard] group-hover:opacity-100"
                    style={{ background: `radial-gradient(80% 80% at 20% 0%, ${c.accent}22, transparent)` }}
                  />
                  <p className="relative font-display text-lg text-ink">{c.title}</p>
                  <p className="relative mt-1 text-xs leading-relaxed text-steel-400">{c.tagline}</p>
                  <p className="label-mono relative mt-3 text-steel-500">{c.count} pièces</p>
                </Link>
              ))}
            </div>
            <Feature teamSlug="juventus" />
          </>
        )}

        {menu === "retros" && (
          <>
            <Column title="Décennies">
              {["Années 90", "Années 2000", "Années 2010"].map((d) => (
                <Item key={d} href="/collections/retros">
                  {d}
                </Item>
              ))}
            </Column>
            <Column title="Clubs légendaires">
              {clubs.slice(0, 8).map((c) => (
                <Item key={c.slug} href={`/collections/retros?club=${c.slug}`}>
                  {c.name}
                </Item>
              ))}
            </Column>
            <Column title="Saisons">
              {["98/99", "02/03", "06/07", "10/11"].map((s) => (
                <Item key={s} href={`/collections/retros?saison=${s}`}>
                  {s}
                </Item>
              ))}
            </Column>
            <Column title="Éditions">
              <Item href="/collections/editions-speciales">Éditions spéciales</Item>
              <Item href="/collections/retros">Tirages limités</Item>
            </Column>
            <Feature teamSlug="ac-milan" />
          </>
        )}

        {menu === "survetements" && (
          <>
            <Column title="Catégories">
              <Item href="/collections/survetements">Survêtements</Item>
              <Item href="/collections/vestes">Vestes</Item>
              <Item href="/collections/vestes">Pulls & sweats</Item>
            </Column>
            <Column title="Clubs">
              {clubs.slice(0, 8).map((c) => (
                <Item key={c.slug} href={`/collections/survetements?club=${c.slug}`}>
                  {c.name}
                </Item>
              ))}
            </Column>
            <Column title="Usage">
              <Item href="/collections/survetements">Entraînement</Item>
              <Item href="/collections/vestes">Avant-match</Item>
              <Item href="/collections/vestes">Lifestyle</Item>
            </Column>
            <Column title="Tailles">
              {["S", "M", "L", "XL", "XXL"].map((s) => (
                <Item key={s} href={`/collections/survetements?taille=${s}`}>
                  {s}
                </Item>
              ))}
            </Column>
            <Feature teamSlug="paris-saint-germain" />
          </>
        )}
      </div>
    </motion.div>
  );
}
