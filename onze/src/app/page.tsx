import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { Hero } from "@/components/sections/Hero";
import { SectionHeader } from "@/components/sections/SectionHeader";
import { TeamCard } from "@/components/sections/TeamRail";
import { ProductGrid } from "@/components/products/ProductGrid";
import { Reveal } from "@/components/motion/Reveal";
import { clubs, countries } from "@/lib/data/teams";
import { collections } from "@/lib/data/collections";
import { countForTeam, newArrivals, onSale } from "@/lib/data/products";

/* Section rhythm is deliberate: hero → product → browse → product → browse.
 * Alternating "buy something" with "find your team" keeps the page from
 * becoming one long grid, and gives the eye somewhere to rest. */

const shell = "mx-auto max-w-[1600px] px-5 lg:px-10";

export default function HomePage() {
  const fresh = newArrivals(8);
  const deals = onSale(4);
  const featuredClubs = clubs.slice(0, 6);
  const featuredCountries = countries.slice(0, 5);

  return (
    <>
      <Hero />

      {/* NOUVEAUTÉS */}
      <section className={`${shell} py-24 lg:py-32`} aria-labelledby="nouveautes">
        <SectionHeader
          eyebrow="Saison 26/27"
          title={<span id="nouveautes">Nouveautés</span>}
          description="Les dernières sorties, ajoutées au fur et à mesure des lancements officiels."
          href="/collections/nouveautes"
        />
        <ProductGrid products={fresh} />
      </section>

      {/* SHOP BY CLUB */}
      <section className={`${shell} py-24 lg:py-32`} aria-labelledby="clubs">
        <SectionHeader
          eyebrow="Par club"
          title={<span id="clubs">Trouvez vos couleurs</span>}
          description="Premier League, Liga, Serie A, Bundesliga, Ligue 1 et les grandes écuries européennes."
          href="/maillots"
          linkLabel="Tous les clubs"
        />
        {/* First card spans two columns — an intentional break in the grid so
            the section has a focal point instead of six equal tiles. */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="sm:col-span-2 lg:row-span-2">
            <TeamCard
              team={featuredClubs[0]}
              count={countForTeam(featuredClubs[0].slug)}
              href={`/maillots?club=${featuredClubs[0].slug}`}
              size="lg"
            />
          </div>
          {featuredClubs.slice(1).map((club, i) => (
            <TeamCard
              key={club.slug}
              team={club}
              count={countForTeam(club.slug)}
              href={`/maillots?club=${club.slug}`}
              index={i + 1}
            />
          ))}
        </div>
      </section>

      {/* PROMOTIONS */}
      <section className="relative overflow-hidden border-y border-white/8 bg-base py-24 lg:py-32">
        <div aria-hidden className="mesh-volt pointer-events-none absolute inset-0 opacity-60" />
        <div className={`${shell} relative`}>
          <SectionHeader
            eyebrow="Offre en cours"
            title="Le troisième maillot à −60 %"
            description="Deux maillots achetés, le troisième à moins 60 %. Automatiquement appliqué au panier."
            href="/collections/nouveautes"
            linkLabel="En profiter"
          />
          <ProductGrid products={deals} />
        </div>
      </section>

      {/* SHOP BY COUNTRY */}
      <section className={`${shell} py-24 lg:py-32`} aria-labelledby="pays">
        <SectionHeader
          eyebrow="Par sélection"
          title={<span id="pays">Les nations</span>}
          description="Les maillots des sélections nationales, à l'approche de la Coupe du monde 2026."
          href="/maillots"
          linkLabel="Toutes les sélections"
        />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {featuredCountries.map((country, i) => (
            <TeamCard
              key={country.slug}
              team={country}
              count={countForTeam(country.slug)}
              href={`/maillots?pays=${country.slug}`}
              index={i}
            />
          ))}
        </div>
      </section>

      {/* COLLECTIONS */}
      <section className={`${shell} py-24 lg:py-32`} aria-labelledby="collections">
        <SectionHeader
          eyebrow="Le vestiaire"
          title={<span id="collections">Collections</span>}
          description="Sept territoires, chacun avec sa propre identité."
        />
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {collections.map((c, i) => (
            <Reveal key={c.slug} index={i} as="div">
              <Link
                href={`/collections/${c.slug}`}
                className="group relative flex min-h-[220px] flex-col justify-between overflow-hidden rounded-xl border border-white/8 bg-surface p-7 transition-colors hover:border-white/20"
              >
                <div
                  aria-hidden
                  className="pointer-events-none absolute inset-0 opacity-30 transition-all duration-[--duration-premium] ease-[--ease-out-expo] group-hover:scale-110 group-hover:opacity-60"
                  style={{
                    background: `radial-gradient(70% 60% at 20% 100%, ${c.accent}66, transparent 70%)`,
                  }}
                />
                <div className="relative flex items-start justify-between gap-4">
                  <h3 className="font-display text-2xl uppercase text-white">{c.title}</h3>
                  <ArrowUpRight
                    size={18}
                    className="mt-1 shrink-0 text-steel-500 transition-all group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-volt"
                  />
                </div>
                <div className="relative">
                  <p className="max-w-xs text-sm leading-relaxed text-steel-400">{c.tagline}</p>
                  <p className="label-mono mt-4 text-steel-600">{c.count} pièces</p>
                </div>
              </Link>
            </Reveal>
          ))}
        </div>
      </section>

      {/* SERVICE */}
      <section className={`${shell} pb-8`}>
        <div className="grid gap-px overflow-hidden rounded-xl border border-white/8 bg-white/8 sm:grid-cols-3">
          {[
            { t: "Flocage inclus", d: "Nom, numéro et écusson appliqués avant expédition." },
            { t: "Expédition 48 h", d: "Départ de Suisse, suivi fourni sur chaque commande." },
            { t: "Retours 30 jours", d: "Article non porté, étiquette d'origine attachée." },
          ].map((item, i) => (
            <Reveal key={item.t} index={i} as="div" className="bg-base p-7">
              <p className="font-display text-lg uppercase text-white">{item.t}</p>
              <p className="mt-2 text-sm leading-relaxed text-steel-400">{item.d}</p>
            </Reveal>
          ))}
        </div>
      </section>
    </>
  );
}
