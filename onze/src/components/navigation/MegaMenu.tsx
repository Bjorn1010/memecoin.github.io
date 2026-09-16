"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { ArrowUpRight } from "lucide-react";
import { clubs, countries, leagues } from "@/lib/data/teams";
import { collections } from "@/lib/data/collections";
import { Jersey } from "@/components/ui/Jersey";
import { transition } from "@/lib/motion";

export type MenuKey = "maillots" | "clubs" | "selections" | "vintage";

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
        className="block truncate py-0.5 text-[0.9rem] text-steel-300 transition-colors hover:text-volt"
      >
        {children}
      </Link>
    </li>
  );
}

/* A featured kit anchors each panel visually — without it the mega menu is
   just a wall of links, which is the exact Shopify look we're avoiding. */
function Feature({ teamSlug, href, label }: { teamSlug: string; href: string; label: string }) {
  const team = [...clubs, ...countries].find((t) => t.slug === teamSlug) ?? clubs[0];
  return (
    <Link
      href={href}
      className="group relative flex min-h-[240px] flex-col justify-between overflow-hidden rounded-md border border-line bg-surface p-5"
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-50 transition-opacity duration-[--duration-slow] group-hover:opacity-90"
        style={{
          background: `radial-gradient(70% 60% at 50% 100%, ${team.colorway.primary}66, transparent 70%)`,
        }}
      />
      <p className="label-mono relative z-10 text-steel-400">{label}</p>
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
      className="absolute inset-x-0 top-full hidden border-b border-line bg-void/95 backdrop-blur-2xl lg:block"
      onMouseLeave={onClose}
    >
      <div className="mx-auto grid max-w-[1600px] grid-cols-[repeat(4,minmax(0,1fr))_320px] gap-10 px-10 py-10">
        {menu === "maillots" && (
          <>
            <Column title="Par type">
              <Item href="/maillots?kit=domicile">Domicile</Item>
              <Item href="/maillots?kit=exterieur">Extérieur</Item>
              <Item href="/maillots?kit=third">Third</Item>
              <Item href="/maillots?kit=gardien">Gardien</Item>
            </Column>
            <Column title="Collections">
              {collections.slice(0, 6).map((c) => (
                <Item key={c.slug} href={`/collections/${c.slug}`}>
                  {c.title}
                </Item>
              ))}
            </Column>
            <Column title="Ligues">
              {leagues.slice(0, 5).map((l) => (
                <Item key={l} href={`/maillots?league=${encodeURIComponent(l)}`}>
                  {l}
                </Item>
              ))}
            </Column>
            <Column title="Prix">
              <Item href="/promotions">En promotion</Item>
              <Item href="/maillots?sort=prix-asc">Les moins chers</Item>
              <Item href="/maillots?enStock=1">En stock</Item>
            </Column>
            <Feature teamSlug="real-madrid" href="/maillots" label="À la une" />
          </>
        )}

        {menu === "clubs" && (
          <>
            {leagues.slice(0, 4).map((league) => (
              <Column key={league} title={league}>
                {clubs
                  .filter((c) => c.league === league)
                  .slice(0, 7)
                  .map((c) => (
                    <Item key={c.slug} href={`/clubs/${c.slug}`}>
                      {c.name}
                    </Item>
                  ))}
              </Column>
            ))}
            <Feature teamSlug="arsenal" href="/clubs" label="Tous les clubs" />
          </>
        )}

        {menu === "selections" && (
          <>
            <div className="col-span-4 grid grid-cols-4 gap-x-10 gap-y-1.5">
              {countries.map((c) => (
                <Link
                  key={c.slug}
                  href={`/selections/${c.slug}`}
                  className="truncate py-0.5 text-[0.9rem] text-steel-300 transition-colors hover:text-volt"
                >
                  {c.name}
                </Link>
              ))}
            </div>
            <Feature
              teamSlug={countries[0]?.slug ?? "bresil"}
              href="/selections"
              label="Sélections"
            />
          </>
        )}

        {menu === "vintage" && (
          <>
            <Column title="Saisons">
              {["98/99", "02/03", "06/07", "10/11"].map((s) => (
                <Item key={s} href={`/collections/retros?saison=${s}`}>
                  {s}
                </Item>
              ))}
            </Column>
            <Column title="Clubs légendaires">
              {clubs.slice(0, 7).map((c) => (
                <Item key={c.slug} href={`/collections/retros?club=${c.slug}`}>
                  {c.name}
                </Item>
              ))}
            </Column>
            <Column title="Éditions">
              <Item href="/collections/editions-speciales">Éditions spéciales</Item>
              <Item href="/collections/retros">Tirages limités</Item>
              <Item href="/collections/retros?enStock=1">Encore disponibles</Item>
            </Column>
            <Column title="L'archive">
              <Item href="/collections/retros">Tout le vintage</Item>
              <Item href="/collections/retros?sort=nouveautes">Derniers ajouts</Item>
            </Column>
            <Feature teamSlug="ac-milan" href="/collections/retros" label="Archives" />
          </>
        )}
      </div>
    </motion.div>
  );
}
