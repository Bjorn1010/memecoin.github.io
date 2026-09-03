import { Button } from "@/components/ui/Button";

export default function NotFound() {
  return (
    <div className="pitch-lines relative flex min-h-[80svh] flex-col items-center justify-center px-5 text-center">
      <div aria-hidden className="floodlight pointer-events-none absolute inset-0" />
      {/* 404 as a squad number on the back of a shirt. */}
      <p className="scoreboard relative text-[clamp(6rem,22vw,16rem)] leading-none text-ink/8">
        404
      </p>
      <h1 className="relative -mt-6 font-display text-title text-ink">Hors-jeu</h1>
      <p className="relative mt-4 max-w-sm text-sm leading-relaxed text-steel-400">
        Cette page n&apos;existe pas ou a été retirée du catalogue.
      </p>
      <div className="relative mt-8 flex flex-wrap justify-center gap-3">
        <Button href="/maillots">Explorer les maillots</Button>
        <Button href="/" variant="outline">
          Retour à l&apos;accueil
        </Button>
      </div>
    </div>
  );
}
