import type { Metadata } from "next";
import { Heart } from "lucide-react";
import { Button } from "@/components/ui/Button";

export const metadata: Metadata = {
  title: "Ma wishlist",
  robots: { index: false, follow: false },
};

/* Wishlist state currently lives per-card and is not persisted. This page is
 * the honest empty state for that: it says so rather than pretending to be a
 * feature that works. Wire it to the same store as the cart when accounts land. */
export default function WishlistPage() {
  return (
    <div className="mx-auto flex min-h-[70svh] max-w-lg flex-col items-center justify-center px-5 text-center">
      <Heart size={40} strokeWidth={1.25} className="text-steel-600" />
      <h1 className="mt-6 font-display text-title text-ink">Wishlist vide</h1>
      <p className="mt-3 text-sm leading-relaxed text-steel-400">
        Touchez le cœur sur un maillot pour le retrouver ici.
      </p>
      <Button href="/maillots" className="mt-8">
        Explorer les maillots
      </Button>
    </div>
  );
}
