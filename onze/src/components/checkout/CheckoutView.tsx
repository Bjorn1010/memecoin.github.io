"use client";

import Link from "next/link";
import { useState } from "react";
import { Lock, ShieldCheck, Truck } from "lucide-react";
import { useCart } from "@/components/cart/CartProvider";
import { Jersey } from "@/components/ui/Jersey";
import { Button } from "@/components/ui/Button";
import { formatPrice } from "@/lib/utils";
import { cn } from "@/lib/utils";

/* Checkout is deliberately the calmest surface on the site. No reveals, no
 * parallax, no hover theatre — every animation here is a chance to look
 * untrustworthy at the exact moment trust matters most. The only motion is
 * the total updating. */

const SHIPPING = [
  { id: "standard", label: "Standard", detail: "2 à 4 jours ouvrables", price: 0 },
  { id: "express", label: "Express", detail: "24 h ouvrées", price: 12 },
] as const;

function Field({
  label,
  id,
  type = "text",
  autoComplete,
  required = true,
  className,
  placeholder,
}: {
  label: string;
  id: string;
  type?: string;
  autoComplete?: string;
  required?: boolean;
  className?: string;
  placeholder?: string;
}) {
  return (
    <label className={cn("block", className)}>
      <span className="label-mono mb-2 block text-steel-500">{label}</span>
      <input
        id={id}
        name={id}
        type={type}
        autoComplete={autoComplete}
        required={required}
        placeholder={placeholder}
        className="h-12 w-full rounded-sm border border-white/12 bg-surface px-3 text-sm text-white outline-none transition-colors placeholder:text-steel-700 focus:border-volt"
      />
    </label>
  );
}

export function CheckoutView() {
  const { lines, subtotal, count } = useCart();
  const [shipping, setShipping] = useState<(typeof SHIPPING)[number]["id"]>("standard");

  const shippingCost = subtotal >= 120 ? 0 : SHIPPING.find((s) => s.id === shipping)!.price;
  const vat = subtotal * 0.081; // TVA CH 8.1 %, included in displayed prices
  const total = subtotal + shippingCost;

  if (count === 0) {
    return (
      <div className="mx-auto max-w-lg px-5 pt-40 text-center">
        <h1 className="font-display text-title text-white">Panier vide</h1>
        <p className="mt-3 text-sm text-steel-400">
          Ajoutez un maillot avant de passer au paiement.
        </p>
        <Button href="/maillots" className="mt-8">
          Explorer les maillots
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1200px] px-5 pt-28 lg:px-10">
      <header className="mb-10">
        <Link href="/" className="font-display text-2xl text-white">
          ONZE<span className="text-volt">.</span>
        </Link>
        <h1 className="mt-6 font-display text-title text-white">Paiement</h1>
        <p className="label-mono mt-3 flex items-center gap-2 text-steel-500">
          <Lock size={13} />
          Connexion chiffrée
        </p>
      </header>

      <div className="grid gap-12 lg:grid-cols-[1.3fr_1fr]">
        {/* ------------------------------------------------ FORM */}
        <form
          className="space-y-10"
          onSubmit={(e) => {
            e.preventDefault();
          }}
        >
          <section aria-labelledby="contact">
            <h2 id="contact" className="mb-5 font-display text-lg uppercase text-white">
              1 · Contact
            </h2>
            <Field label="E-mail" id="email" type="email" autoComplete="email" placeholder="vous@exemple.ch" />
          </section>

          <section aria-labelledby="livraison">
            <h2 id="livraison" className="mb-5 font-display text-lg uppercase text-white">
              2 · Adresse de livraison
            </h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Prénom" id="prenom" autoComplete="given-name" />
              <Field label="Nom" id="nom" autoComplete="family-name" />
              <Field label="Adresse" id="adresse" autoComplete="street-address" className="sm:col-span-2" />
              <Field label="Code postal" id="cp" autoComplete="postal-code" />
              <Field label="Ville" id="ville" autoComplete="address-level2" />
              <Field label="Pays" id="pays" autoComplete="country-name" className="sm:col-span-2" />
            </div>
          </section>

          <section aria-labelledby="mode">
            <h2 id="mode" className="mb-5 font-display text-lg uppercase text-white">
              3 · Mode de livraison
            </h2>
            <div className="space-y-3">
              {SHIPPING.map((s) => {
                const free = subtotal >= 120 && s.id === "standard";
                return (
                  <label
                    key={s.id}
                    className={cn(
                      "flex cursor-pointer items-center gap-4 rounded-md border p-4 transition-colors",
                      shipping === s.id
                        ? "border-volt bg-volt/5"
                        : "border-white/12 hover:border-white/30",
                    )}
                  >
                    <input
                      type="radio"
                      name="shipping"
                      value={s.id}
                      checked={shipping === s.id}
                      onChange={() => setShipping(s.id)}
                      className="sr-only"
                    />
                    <span
                      aria-hidden
                      className={cn(
                        "grid h-4 w-4 shrink-0 place-items-center rounded-full border",
                        shipping === s.id ? "border-volt" : "border-white/30",
                      )}
                    >
                      {shipping === s.id && <span className="h-2 w-2 rounded-full bg-volt" />}
                    </span>
                    <span className="flex-1">
                      <span className="block text-sm text-white">{s.label}</span>
                      <span className="block text-xs text-steel-500">{s.detail}</span>
                    </span>
                    <span className="tabular text-sm text-white">
                      {free || s.price === 0 ? "Offerte" : formatPrice(s.price)}
                    </span>
                  </label>
                );
              })}
            </div>
          </section>

          <section aria-labelledby="paiement">
            <h2 id="paiement" className="mb-5 font-display text-lg uppercase text-white">
              4 · Paiement
            </h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                label="Numéro de carte"
                id="carte"
                autoComplete="cc-number"
                placeholder="0000 0000 0000 0000"
                className="sm:col-span-2"
              />
              <Field label="Expiration" id="exp" autoComplete="cc-exp" placeholder="MM/AA" />
              <Field label="CVC" id="cvc" autoComplete="cc-csc" placeholder="123" />
            </div>
            <p className="label-mono mt-4 flex items-center gap-2 text-steel-600">
              <ShieldCheck size={14} />
              Vos données de carte ne transitent pas par nos serveurs
            </p>
          </section>

          <Button size="lg" className="w-full" type="submit">
            Payer {formatPrice(total)}
          </Button>

          <p className="text-center text-xs leading-relaxed text-steel-600">
            En validant, vous acceptez nos{" "}
            <Link href="/legal/cgv" className="underline hover:text-steel-300">
              conditions générales
            </Link>
            .
          </p>
        </form>

        {/* ------------------------------------------------ SUMMARY */}
        <aside className="lg:sticky lg:top-28 lg:self-start">
          <div className="rounded-xl border border-white/10 bg-surface p-6">
            <h2 className="label-mono mb-5 text-white">
              Récapitulatif · {count} article{count > 1 ? "s" : ""}
            </h2>

            <ul className="space-y-4 border-b border-white/8 pb-5">
              {lines.map((line) => (
                <li key={`${line.productId}-${line.size}`} className="flex gap-3">
                  <div className="relative h-16 w-14 shrink-0">
                    <Jersey colorway={line.colorway} detailed={false} />
                    <span className="tabular absolute -right-1.5 -top-1.5 grid h-5 min-w-5 place-items-center rounded-full bg-steel-700 px-1 text-[10px] text-white">
                      {line.quantity}
                    </span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm text-white">{line.name}</p>
                    <p className="label-mono mt-0.5 text-steel-600">Taille {line.size}</p>
                  </div>
                  <span className="tabular shrink-0 text-sm text-steel-200">
                    {formatPrice(line.price * line.quantity)}
                  </span>
                </li>
              ))}
            </ul>

            <dl className="space-y-2.5 border-b border-white/8 py-5 text-sm">
              <div className="flex justify-between">
                <dt className="text-steel-400">Sous-total</dt>
                <dd className="tabular text-white">{formatPrice(subtotal)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-steel-400">Livraison</dt>
                <dd className="tabular text-white">
                  {shippingCost === 0 ? "Offerte" : formatPrice(shippingCost)}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-steel-500">dont TVA 8.1 %</dt>
                <dd className="tabular text-steel-500">{formatPrice(vat)}</dd>
              </div>
            </dl>

            <div className="flex items-baseline justify-between pt-5">
              <span className="label-mono text-steel-400">Total</span>
              <span className="scoreboard text-3xl text-white">{formatPrice(total)}</span>
            </div>

            <p className="mt-5 flex items-start gap-2 text-xs leading-relaxed text-steel-500">
              <Truck size={14} className="mt-0.5 shrink-0 text-volt" />
              Flocage nom et numéro inclus. Expédition sous 48 h ouvrables depuis la Suisse.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
