import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { HeroEditorial } from "@/components/sections/HeroEditorial";
import { CategoryGrid } from "@/components/sections/CategoryGrid";
import { EditorialBand } from "@/components/sections/EditorialBand";
import { JustDropped } from "@/components/sections/JustDropped";
import { TrustRow } from "@/components/sections/TrustRow";
import { Community } from "@/components/sections/Community";
import { Newsletter } from "@/components/sections/Newsletter";
import { TeamCard } from "@/components/sections/TeamRail";
import { PinnedStory } from "@/components/sections/PinnedStory";
import { ClubRail } from "@/components/sections/ClubRail";
import { WordReveal } from "@/components/motion/WordReveal";
import { ProductGrid } from "@/components/products/ProductGrid";
import { allTeams, clubs, countries } from "@/lib/data/teams";
import {
  bestSellers,
  countForCategory,
  countForTeam,
  newArrivals,
  products,
} from "@/lib/data/products";

/* A section wrapper, so the vertical rhythm is declared once instead of being
   re-guessed on every band. */
function Section({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`mx-auto max-w-[1600px] px-5 py-20 lg:px-10 lg:py-28 ${className}`}>
      {children}
    </section>
  );
}

function Head({
  eyebrow,
  title,
  href,
  cta,
}: {
  eyebrow: string;
  title: string;
  href?: string;
  cta?: string;
}) {
  return (
    <div className="mb-10 flex flex-wrap items-end justify-between gap-4 border-b border-line pb-6">
      <div>
        <p className="eyebrow label-mono mb-4">{eyebrow}</p>
        <WordReveal text={title} className="font-display text-display text-ink" />
      </div>
      {href && cta && (
        <Link
          href={href}
          className="group inline-flex items-center gap-2 font-display text-sm uppercase tracking-wide text-steel-200 transition-colors hover:text-volt"
        >
          {cta}
          <ArrowRight size={15} strokeWidth={2.5} className="transition-transform group-hover:translate-x-1" />
        </Link>
      )}
    </div>
  );
}

export default function HomePage() {
  const fresh = newArrivals(5);
  const popular = bestSellers(8);
  const onSaleCount = products.filter((p) => p.compareAt).length;
  /* Resolved here rather than per-card: countForTeam scans the catalogue, and
     the rail renders every club. */
  const clubCounts = Object.fromEntries(clubs.map((c) => [c.slug, countForTeam(c.slug)]));

  const categories = [
    {
      href: "/clubs",
      title: "Clubs",
      blurb: "Les grandes écuries européennes, championnat par championnat.",
      image: "cat-clubs",
      count: clubs.length,
      wide: true,
    },
    {
      href: "/selections",
      title: "Sélections",
      blurb: "Le maillot qu'on ne porte qu'un été sur deux.",
      image: "cat-selections",
      count: countries.length,
    },
    {
      href: "/collections/retros",
      title: "Vintage",
      blurb: "Les saisons qu'on rejoue encore de mémoire.",
      image: "cat-vintage",
      count: countForCategory("retros"),
    },
    {
      href: "/collections/nouveautes",
      title: "Nouveautés",
      blurb: "Ce qui vient d'arriver, avant tout le monde.",
      image: "cat-new",
      count: products.filter((p) => p.isNew).length,
    },
    {
      href: "/collections/kits-enfants",
      title: "Kids",
      blurb: "Les mêmes maillots, taillés du 4 au 14 ans.",
      image: "cat-kids",
      count: countForCategory("kits-enfants"),
    },
    {
      href: "/promotions",
      title: "Promotions",
      blurb: "Fins de séries et dernières tailles.",
      image: "cat-sale",
      count: onSaleCount,
      /* Wide, so the second row resolves to four columns like the first
         instead of leaving a hole where a fourth card would be. */
      wide: true,
    },
  ];

  return (
    <>
      <HeroEditorial references={products.length} clubCount={allTeams.length} />

      <Section>
        <Head eyebrow="Shop by category" title="Par où vous entrez" />
        <CategoryGrid categories={categories} />
      </Section>

      <Section className="!pt-0">
        <Head
          eyebrow="Just dropped"
          title="Le dernier arrivage"
          href="/collections/nouveautes"
          cta="Tout voir"
        />
        <JustDropped products={fresh} />
      </Section>

      {/* The chapter that sells the differentiator — the name in the back —
          as a scroll-driven sequence rather than another band. */}
      <PinnedStory team={clubs[0]} />

      {/* The editorial heart of the page: why a shirt is worth caring about,
          told over the one photograph where the name and number are the
          subject rather than the product. */}
      <EditorialBand
        image="shirt-back"
        eyebrow="The shirt"
        title={
          <>
            Un maillot n&apos;est
            <br />
            jamais <span className="text-volt">qu&apos;un maillot</span>.
          </>
        }
        body="C'est une date, une ville, un soir de semaine sous les projecteurs. C'est le nom qu'on a choisi de porter dans le dos. Nous vendons des maillots ; ce que vous achetez est un souvenir qui n'a pas encore eu lieu."
        cta="Personnaliser le vôtre"
        href="/maillots"
        align="left"
        tall
      />

      <Section>
        <Head eyebrow="Best sellers" title="Les plus portés" href="/maillots" cta="Tout le catalogue" />
        <ProductGrid products={popular} priorityCount={4} />
      </Section>

      <Section className="!pt-0">
        <Head eyebrow="Explore clubs" title="Vos couleurs" href="/clubs" cta="Tous les clubs" />
      </Section>
      {/* Full-bleed: the rail is meant to run past both edges of the page. */}
      <div className="-mt-6 pb-20 lg:pb-28">
        <ClubRail teams={clubs} counts={clubCounts} />
      </div>

      <Section className="!pt-0">
        <Head
          eyebrow="National teams"
          title="Les sélections"
          href="/selections"
          cta="Toutes les sélections"
        />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {countries.slice(0, 4).map((team, i) => (
            <TeamCard
              key={team.slug}
              team={team}
              index={i}
              count={countForTeam(team.slug)}
              href={`/selections/${team.slug}`}
            />
          ))}
        </div>
      </Section>

      <EditorialBand
        image="archives"
        eyebrow="Football archives"
        title={
          <>
            Les saisons
            <br />
            qu&apos;on rejoue
            <br />
            de mémoire.
          </>
        }
        body="Rétros, rééditions et tirages courts. Les maillots des nuits européennes qu'on raconte encore, remis en circulation."
        cta="Entrer dans l'archive"
        href="/collections/retros"
        align="right"
      />

      <EditorialBand
        image="campaign-action"
        eyebrow="Saison 26/27"
        title={
          <>
            La nouvelle saison
            <br />
            est arrivée.
          </>
        }
        cta="Voir la collection"
        href="/collections/nouveautes"
        align="center"
      />

      <Section>
        <div className="mb-10 flex flex-wrap items-end justify-between gap-4 border-b border-line pb-6">
          <div>
            <p className="eyebrow label-mono mb-4">Last chance</p>
            <h2 className="font-display text-display text-ink">Dernières tailles</h2>
            <p className="mt-4 max-w-md text-sm leading-relaxed text-steel-300">
              {onSaleCount} références à prix réduit. Les prix barrés sont ceux pratiqués avant
              réduction.
            </p>
          </div>
          <Link
            href="/promotions"
            className="group inline-flex items-center gap-2 border border-ink/25 px-6 py-3.5 font-display text-sm uppercase tracking-wide text-ink transition-colors hover:border-ink hover:bg-ink hover:text-void"
          >
            Voir les promos
            <ArrowRight size={15} strokeWidth={2.5} className="transition-transform group-hover:translate-x-1" />
          </Link>
        </div>
        <ProductGrid products={products.filter((p) => p.compareAt).slice(0, 4)} />
      </Section>

      <Section className="!pt-0">
        <TrustRow />
      </Section>

      <Section className="!pt-0">
        <Community />
      </Section>

      <Newsletter />
    </>
  );
}
