import { Jersey } from "@/components/ui/Jersey";
import type { Team } from "@/lib/types";

/* The masthead for a club or country page. The team's own colours drive the
 * field behind it, so thirty-seven pages share one component without any of
 * them looking like a template — Arsenal arrives red, Brazil arrives yellow. */
export function TeamHero({
  team,
  count,
  kicker,
}: {
  team: Team;
  count: number;
  kicker: string;
}) {
  return (
    <header className="relative overflow-hidden border-b border-line bg-base">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-60"
        style={{
          background: `radial-gradient(60% 80% at 82% 120%, ${team.colorway.primary}66, transparent 70%),
                       radial-gradient(40% 60% at 10% -10%, ${team.colorway.secondary}33, transparent 72%)`,
        }}
      />
      <span
        aria-hidden
        className="pointer-events-none absolute -right-6 top-1/2 -translate-y-1/2 font-display text-[26vw] leading-none text-ink/[0.04] lg:text-[16vw]"
      >
        {team.monogram}
      </span>

      <div className="relative mx-auto grid max-w-[1600px] items-center gap-8 px-5 pb-14 pt-36 lg:grid-cols-[1.4fr_0.6fr] lg:px-10 lg:pb-20 lg:pt-44">
        <div className="min-w-0">
          <p className="eyebrow label-mono mb-5">{kicker}</p>
          <h1 className="font-display text-hero text-ink">{team.name}</h1>
          <dl className="mt-8 flex flex-wrap gap-x-10 gap-y-4 border-t border-line pt-6">
            <div>
              <dt className="label-mono text-steel-500">Références</dt>
              <dd className="scoreboard mt-1 text-2xl text-ink">{count}</dd>
            </div>
            <div>
              <dt className="label-mono text-steel-500">Championnat</dt>
              <dd className="mt-1 text-sm text-steel-200">{team.league}</dd>
            </div>
            <div>
              <dt className="label-mono text-steel-500">Fondé en</dt>
              <dd className="scoreboard mt-1 text-2xl text-ink">{team.founded}</dd>
            </div>
          </dl>
        </div>

        <div className="pointer-events-none mx-auto w-full max-w-[220px] lg:max-w-[280px]">
          <Jersey colorway={team.colorway} monogram={team.monogram} number="10" />
        </div>
      </div>
    </header>
  );
}
