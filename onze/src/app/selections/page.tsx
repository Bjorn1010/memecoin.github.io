import type { Metadata } from "next";
import { TeamCard } from "@/components/sections/TeamRail";
import { confederations, countries } from "@/lib/data/teams";
import { countForTeam } from "@/lib/data/products";

export const metadata: Metadata = {
  title: "Sélections nationales",
  description:
    "Maillots des sélections nationales : Europe, Amérique, Afrique, Asie. Domicile et extérieur, flocage inclus, expédition 48 h.",
  alternates: { canonical: "/selections" },
  openGraph: {
    title: "Sélections nationales — ONZE",
    description: "Maillots des sélections nationales, continent par continent.",
  },
};

export default function SelectionsPage() {
  /* By confederation: a national shirt is read through its continent long
     before it is read through its federation's name. */
  const byConfederation = confederations
    .map((conf) => ({ conf, teams: countries.filter((c) => c.confederation === conf) }))
    .filter((g) => g.teams.length > 0);

  return (
    <div className="mx-auto max-w-[1600px] px-5 pb-24 pt-36 lg:px-10 lg:pt-44">
      <header className="mb-14 border-b border-line pb-10">
        <p className="eyebrow label-mono mb-5">National teams</p>
        <h1 className="font-display text-hero text-ink">
          Le maillot
          <br />
          d&apos;un pays.
        </h1>
        <p className="mt-6 max-w-xl text-sm leading-relaxed text-steel-300">
          {countries.length} sélections au catalogue. Celui qu&apos;on ne porte qu&apos;un été sur
          deux, et qu&apos;on garde pour toujours.
        </p>
      </header>

      <div className="space-y-16">
        {byConfederation.map(({ conf, teams }) => (
          <section key={conf}>
            <div className="mb-6 flex items-baseline justify-between gap-4 border-b border-line pb-3">
              <h2 className="font-display text-title text-ink">{conf}</h2>
              <p className="label-mono text-steel-500">{teams.length} sélections</p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {teams.map((team, i) => (
                <TeamCard
                  key={team.slug}
                  team={team}
                  index={i}
                  count={countForTeam(team.slug)}
                  href={`/selections/${team.slug}`}
                />
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
