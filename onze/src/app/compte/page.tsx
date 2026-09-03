import type { Metadata } from "next";
import Link from "next/link";
import { Button } from "@/components/ui/Button";

export const metadata: Metadata = {
  title: "Mon compte",
  robots: { index: false, follow: false },
};

/* No auth backend yet. Rather than a fake dashboard, this is a real sign-in
 * form that does not submit anywhere — clearly labelled as such below. */
export default function ComptePage() {
  return (
    <div className="mx-auto max-w-sm px-5 pt-40 pb-24">
      <h1 className="font-display text-title text-white">Connexion</h1>
      <p className="mt-3 text-sm leading-relaxed text-steel-400">
        Suivez vos commandes et retrouvez votre wishlist.
      </p>

      <form className="mt-8 space-y-4">
        <label className="block">
          <span className="label-mono mb-2 block text-steel-500">E-mail</span>
          <input
            type="email"
            autoComplete="email"
            placeholder="vous@exemple.ch"
            className="h-12 w-full rounded-sm border border-white/12 bg-surface px-3 text-sm text-white outline-none transition-colors placeholder:text-steel-700 focus:border-volt"
          />
        </label>
        <label className="block">
          <span className="label-mono mb-2 block text-steel-500">Mot de passe</span>
          <input
            type="password"
            autoComplete="current-password"
            className="h-12 w-full rounded-sm border border-white/12 bg-surface px-3 text-sm text-white outline-none transition-colors focus:border-volt"
          />
        </label>
        <Button size="lg" className="w-full" type="submit">
          Se connecter
        </Button>
      </form>

      <p className="mt-6 text-center text-xs text-steel-600">
        Pas encore de compte ?{" "}
        <Link href="/compte" className="underline hover:text-steel-300">
          Créer un compte
        </Link>
      </p>

      <p className="mt-10 rounded-md border border-white/8 bg-surface p-4 text-xs leading-relaxed text-steel-500">
        Démonstration : aucune authentification n&apos;est branchée, ce formulaire
        n&apos;envoie rien.
      </p>
    </div>
  );
}
