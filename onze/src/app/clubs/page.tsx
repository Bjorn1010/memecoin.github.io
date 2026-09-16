import type { Metadata } from "next";
import { TeamCard } from "@/components/sections/TeamRail";
import { clubs, leagues } from "@/lib/data/teams";
import { countForTeam } from "@/lib/data/products";

export const metadata: Metadata = {
  title: "Clubs",
  description:
    "Tous les clubs disponibles chez ONZE, championnat par championnat. Premier League, Liga, Serie A, Bundesliga, Ligue 1 et grandes écuries européennes.",
  alternates: { canonical: "/clubs" },
  openGraph: {
    title: "Clubs — ONZE",
    description: "Tous les clubs disponibles, championnat par championnat.",
  },
};

export default function ClubsPage() {
  /* Grouped by league rather than listed A–Z: a supporter arrives knowing the
     competition before the club, and thirty-odd names in one flat grid is a
     directory, not a shop. */
  const byLeague = leagues
    .map((league) => ({ league, teams: clubs.filter((c) => c.league === league) }))
    .filter((g) => g.teams.length > 0);

  return (
    <div className="mx-auto max-w-[1600px] px-5 pb-24 pt-36 lg:px-10 lg:pt-44">
      <header className="mb-14 border-b border-line pb-10">
        <p className="eyebrow label-mono mb-5">Explore clubs</p>
        <h1 className="font-display text-hero text-ink">
          Vos couleurs,
          <br />
          par championnat.
        </h1>
        <p className="mt-6 max-w-xl text-sm leading-relaxed text-steel-300">
          {clubs.length} clubs au catalogue. Domicile, extérieur, third et archives — chaque club a
          sa page, chaque maillot son flocage inclus.
        </p>
      </header>

      <div className="space-y-16">
        {byLeague.map(({ league, teams }) => (
          <section key={league}>
            <div className="mb-6 flex items-baseline justify-between gap-4 border-b border-line pb-3">
              <h2 className="font-display text-title text-ink">{league}</h2>
              <p className="label-mono text-steel-500">{teams.length} clubs</p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {teams.map((team, i) => (
                <TeamCard
                  key={team.slug}
                  team={team}
                  index={i}
                  count={countForTeam(team.slug)}
                  href={`/clubs/${team.slug}`}
                />
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
