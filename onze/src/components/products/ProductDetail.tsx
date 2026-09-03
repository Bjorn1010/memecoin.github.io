"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Box, Check, ChevronDown, Heart, Minus, Plus, RotateCcw, Ruler, Truck } from "lucide-react";
import type { Product } from "@/lib/types";
import { KitVisual } from "@/components/ui/KitVisual";
import { Badge } from "@/components/ui/Badge";
import { Price } from "@/components/ui/Price";
import { Button } from "@/components/ui/Button";
import { useCart } from "@/components/cart/CartProvider";
import { cn, formatPrice } from "@/lib/utils";
import { spring, transition } from "@/lib/motion";

const ProductScene = dynamic(() => import("@/components/3d/ProductScene"), { ssr: false });

const FLOCAGE_PRICE = 0; // included, per the storefront promise

export function ProductDetail({ product }: { product: Product }) {
  const { add } = useCart();
  const reduced = useReducedMotion();

  const [size, setSize] = useState<string | null>(null);
  const [sizeError, setSizeError] = useState(false);
  const [quantity, setQuantity] = useState(1);
  const [view, setView] = useState<"front" | "back">("front");
  const [use3D, setUse3D] = useState(false);
  const [wishlisted, setWishlisted] = useState(false);
  const [added, setAdded] = useState(false);

  /* Flocage — the reason people buy a shirt here rather than anywhere else. */
  const [playerName, setPlayerName] = useState("");
  const [playerNumber, setPlayerNumber] = useState("10");

  const buyRef = useRef<HTMLFieldSetElement>(null);
  const [showSticky, setShowSticky] = useState(false);

  const monogram = product.teamSlug.slice(0, 3).toUpperCase();
  const soldOut = product.stock === 0;
  const lowStock = product.stock > 0 && product.stock <= 5;

  /* Typing a name flips the preview to the back automatically — otherwise the
     user edits a field and nothing visibly happens. */
  useEffect(() => {
    if (playerName) setView("back");
  }, [playerName]);

  /* Sticky mobile CTA appears once the real buy button has scrolled away. */
  useEffect(() => {
    const el = buyRef.current;
    if (!el) return;
    const io = new IntersectionObserver(([entry]) => setShowSticky(!entry.isIntersecting), {
      rootMargin: "-80px 0px 0px 0px",
    });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  function handleAdd() {
    if (!size) {
      setSizeError(true);
      buyRef.current?.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "center" });
      return;
    }
    add(product, size, quantity);
    setAdded(true);
    window.setTimeout(() => setAdded(false), 1800);
  }

  return (
    <>
      <div className="mx-auto max-w-[1600px] px-5 pt-28 lg:px-10">
        {/* Breadcrumb */}
        <nav aria-label="Fil d'Ariane" className="label-mono mb-6 flex flex-wrap gap-2 text-steel-600">
          <Link href="/" className="hover:text-ink">Accueil</Link>
          <span aria-hidden>/</span>
          <Link href="/maillots" className="hover:text-ink">Maillots</Link>
          <span aria-hidden>/</span>
          <Link href={`/maillots?club=${product.teamSlug}`} className="hover:text-ink">
            {product.team}
          </Link>
        </nav>

        <div className="grid gap-10 lg:grid-cols-[1.15fr_1fr] lg:gap-16">
          {/* ------------------------------------------------ GALLERY */}
          <div className="lg:sticky lg:top-28 lg:self-start">
            <div
              className={cn(
                "grain relative aspect-square overflow-hidden rounded-xl border border-ink/8",
                "bg-gradient-to-b from-white to-pitch-tint",
              )}
            >
              <div
                aria-hidden
                className="absolute inset-0"
                style={{
                  background: `radial-gradient(60% 50% at 50% 100%, ${product.colorway.primary}44, transparent 70%)`,
                }}
              />

              {use3D ? (
                <div className="absolute inset-0">
                  <ProductScene
                    colorway={product.colorway}
                    monogram={monogram}
                    number={playerNumber || "10"}
                    playerName={playerName}
                  />
                </div>
              ) : (
                <AnimatePresence mode="wait">
                  <motion.div
                    key={view}
                    initial={{ opacity: 0, rotateY: reduced ? 0 : view === "back" ? 40 : -40 }}
                    animate={{ opacity: 1, rotateY: 0 }}
                    exit={{ opacity: 0, rotateY: reduced ? 0 : view === "back" ? -40 : 40 }}
                    transition={transition.slow}
                    className="absolute inset-0 p-10"
                    style={{ perspective: 1200 }}
                  >
                    <KitVisual
                      colorway={product.colorway}
                      photo={view === "front" ? product.photo : undefined}
                      alt={`${product.name}, vue ${view === "front" ? "de face" : "de dos"}`}
                      monogram={monogram}
                      number={playerNumber || "10"}
                      view={view}
                      playerName={playerName}
                      priority
                    />
                  </motion.div>
                </AnimatePresence>
              )}

              {/* View controls */}
              <div className="absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-1 rounded-full border border-ink/12 bg-ink/60 p-1 backdrop-blur-md">
                {(["front", "back"] as const).map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => {
                      setView(v);
                      setUse3D(false);
                    }}
                    aria-pressed={!use3D && view === v}
                    className={cn(
                      "label-mono rounded-full px-4 py-2 transition-colors",
                      !use3D && view === v ? "bg-white text-paper" : "text-steel-300 hover:text-ink",
                    )}
                  >
                    {v === "front" ? "Face" : "Dos"}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => setUse3D((v) => !v)}
                  aria-pressed={use3D}
                  className={cn(
                    "label-mono flex items-center gap-1.5 rounded-full px-4 py-2 transition-colors",
                    use3D ? "bg-pitch text-paper" : "text-steel-300 hover:text-ink",
                  )}
                >
                  <Box size={13} />
                  360°
                </button>
              </div>

              {use3D && (
                <p className="label-mono absolute left-1/2 top-4 -translate-x-1/2 rounded-full bg-ink/60 px-3 py-1.5 text-steel-400 backdrop-blur-md">
                  Glissez pour tourner · molette pour zoomer
                </p>
              )}
            </div>
          </div>

          {/* ------------------------------------------------ BUY COLUMN */}
          <div>
            <div className="mb-3 flex flex-wrap gap-2">
              {product.compareAt && <Badge tone="sale">Promo</Badge>}
              {product.isNew && <Badge tone="new">Nouveau</Badge>}
              {product.category === "editions-speciales" && <Badge tone="limited">Édition limitée</Badge>}
              {soldOut && <Badge tone="soldout">Épuisé</Badge>}
            </div>

            <p className="label-mono text-steel-500">
              {product.team} · {product.league} · {product.season}
            </p>
            <h1 className="mt-3 font-display text-title text-ink">{product.name}</h1>

            <div className="mt-5 flex flex-wrap items-center gap-4">
              <Price price={product.price} compareAt={product.compareAt} size="lg" />
              <span className="flex items-center gap-1.5 text-xs text-steel-400">
                <span aria-hidden className="text-pitch">★</span>
                <span className="tabular">{product.rating.toFixed(1)}</span>
                <span className="text-steel-600">({product.reviews} avis)</span>
              </span>
            </div>

            {/* ---------------------------------------- SIZE */}
            <fieldset ref={buyRef} className="mt-9">
              <div className="mb-3 flex items-center justify-between">
                <legend className="label-mono text-steel-400">
                  Taille
                  {sizeError && <span className="ml-2 text-sale">— obligatoire</span>}
                </legend>
                <button
                  type="button"
                  className="label-mono flex items-center gap-1.5 text-steel-500 transition-colors hover:text-ink"
                >
                  <Ruler size={13} />
                  Guide des tailles
                </button>
              </div>
              {/* Sizes as squad-number plates — picking a size should feel like
                  picking a shirt, not filling a form. */}
              <div className="flex flex-wrap gap-2">
                {product.sizes.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => {
                      setSize(s);
                      setSizeError(false);
                    }}
                    aria-pressed={size === s}
                    disabled={soldOut}
                    className={cn(
                      "number-plate h-14 min-w-14 rounded-md border px-4 text-lg transition-all",
                      size === s
                        ? "border-pitch bg-pitch text-paper"
                        : "border-ink/15 text-steel-200 hover:border-ink/45 hover:bg-ink/5",
                      sizeError && !size && "border-sale/60",
                      soldOut && "cursor-not-allowed opacity-40",
                    )}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </fieldset>

            {/* ---------------------------------------- FLOCAGE */}
            <div className="mt-9 rounded-xl border border-ink/10 bg-surface p-5">
              <div className="mb-4 flex items-center justify-between">
                <p className="label-mono text-ink">Flocage</p>
                <Badge tone="new">Inclus</Badge>
              </div>
              <div className="grid grid-cols-[1fr_88px] gap-3">
                <label className="block">
                  <span className="label-mono mb-2 block text-steel-500">Nom</span>
                  <input
                    value={playerName}
                    onChange={(e) => setPlayerName(e.target.value.replace(/[^a-zA-ZÀ-ÿ .-]/g, ""))}
                    maxLength={12}
                    placeholder="VOTRE NOM"
                    className="number-plate h-12 w-full rounded-sm border border-ink/12 bg-base px-3 uppercase tracking-wide text-ink outline-none transition-colors placeholder:text-steel-700 focus:border-pitch"
                  />
                </label>
                <label className="block">
                  <span className="label-mono mb-2 block text-steel-500">Numéro</span>
                  <input
                    value={playerNumber}
                    onChange={(e) => setPlayerNumber(e.target.value.replace(/\D/g, "").slice(0, 2))}
                    inputMode="numeric"
                    placeholder="10"
                    className="number-plate h-12 w-full rounded-sm border border-ink/12 bg-base px-3 text-center text-lg text-ink outline-none transition-colors placeholder:text-steel-700 focus:border-pitch"
                  />
                </label>
              </div>
              <p className="mt-3 text-xs leading-relaxed text-steel-500">
                Nom, numéro et écusson appliqués avant expédition.
                {FLOCAGE_PRICE === 0 && " Sans supplément."}
              </p>
            </div>

            {/* ---------------------------------------- QUANTITY + CTA */}
            <div className="mt-7 flex items-stretch gap-3">
              <div className="flex items-center rounded-sm border border-ink/15">
                <button
                  type="button"
                  onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                  aria-label="Réduire la quantité"
                  className="grid h-14 w-11 place-items-center text-steel-400 hover:text-ink"
                >
                  <Minus size={15} />
                </button>
                <span className="tabular w-8 text-center text-ink">{quantity}</span>
                <button
                  type="button"
                  onClick={() => setQuantity((q) => Math.min(10, q + 1))}
                  aria-label="Augmenter la quantité"
                  className="grid h-14 w-11 place-items-center text-steel-400 hover:text-ink"
                >
                  <Plus size={15} />
                </button>
              </div>

              <Button size="lg" className="flex-1" onClick={handleAdd} disabled={soldOut}>
                <AnimatePresence mode="wait" initial={false}>
                  {added ? (
                    <motion.span
                      key="ok"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -8 }}
                      transition={spring.pop}
                      className="flex items-center gap-2"
                    >
                      <Check size={16} strokeWidth={3} />
                      Ajouté
                    </motion.span>
                  ) : (
                    <motion.span key="add" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                      {soldOut ? "Épuisé" : "Ajouter au panier"}
                    </motion.span>
                  )}
                </AnimatePresence>
              </Button>

              <button
                type="button"
                onClick={() => setWishlisted((w) => !w)}
                aria-pressed={wishlisted}
                aria-label={wishlisted ? "Retirer de la wishlist" : "Ajouter à la wishlist"}
                className={cn(
                  "grid h-14 w-14 shrink-0 place-items-center rounded-sm border transition-colors",
                  wishlisted
                    ? "border-sale/40 bg-sale/15 text-sale"
                    : "border-ink/15 text-steel-300 hover:border-ink/40 hover:text-ink",
                )}
              >
                <Heart size={18} fill={wishlisted ? "currentColor" : "none"} />
              </button>
            </div>

            {/* Stock signal — urgency only when it is true. */}
            <p className="mt-4 flex items-center gap-2 text-sm">
              {soldOut ? (
                <span className="text-steel-500">Réapprovisionnement sous 2 à 3 semaines.</span>
              ) : lowStock ? (
                <>
                  <span aria-hidden className="inline-block h-1.5 w-1.5 rounded-full bg-warning" />
                  <span className="text-warning">Plus que {product.stock} en stock</span>
                </>
              ) : (
                <>
                  <span aria-hidden className="inline-block h-1.5 w-1.5 rounded-full bg-success" />
                  <span className="text-steel-300">En stock — expédié sous 48 h</span>
                </>
              )}
            </p>

            {/* Service strip */}
            <div className="mt-7 grid gap-px overflow-hidden rounded-lg border border-ink/8 bg-ink/8 sm:grid-cols-2">
              {[
                { icon: Truck, t: "Livraison 48 h", d: "Suivi inclus, départ de Suisse" },
                { icon: RotateCcw, t: "Retours 30 jours", d: "Article non porté" },
              ].map((s) => (
                <div key={s.t} className="flex items-start gap-3 bg-base p-4">
                  <s.icon size={17} className="mt-0.5 shrink-0 text-pitch" strokeWidth={1.75} />
                  <div>
                    <p className="text-sm text-ink">{s.t}</p>
                    <p className="mt-0.5 text-xs text-steel-500">{s.d}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Details */}
            <div className="mt-9">
              {[
                { t: "Description", c: product.description },
                {
                  t: "Détails & entretien",
                  c: "100 % polyester recyclé, maille piquée respirante. Lavage machine 30 °C sur l'envers. Ne pas repasser le flocage. Séchage à l'air libre.",
                },
                {
                  t: "Livraison & retours",
                  c: "Expédition sous 48 h ouvrables depuis la Suisse. Livraison 2 à 4 jours en Suisse, 4 à 8 jours en Europe. Retours acceptés 30 jours après réception, article non porté et étiquette attachée. Les articles floqués sur mesure ne sont pas repris.",
                },
              ].map((row) => (
                <Accordion key={row.t} title={row.t}>
                  {row.c}
                </Accordion>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Sticky mobile CTA */}
      <AnimatePresence>
        {showSticky && !soldOut && (
          <motion.div
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={spring.panel}
            className="fixed inset-x-0 bottom-0 z-40 flex items-center gap-3 border-t border-ink/10 bg-void/95 px-4 py-3 backdrop-blur-xl lg:hidden"
          >
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs text-steel-400">{product.team}</p>
              <p className="tabular text-sm font-semibold text-ink">
                {formatPrice(product.price * quantity)}
              </p>
            </div>
            <Button onClick={handleAdd} className="shrink-0">
              {size ? "Ajouter" : "Choisir la taille"}
            </Button>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

function Accordion({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-ink/8">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center justify-between py-4 text-left"
      >
        <span className="label-mono text-ink">{title}</span>
        <ChevronDown
          size={17}
          className={cn("text-steel-500 transition-transform duration-[--duration-standard]", open && "rotate-180")}
        />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={transition.standard}
            className="overflow-hidden"
          >
            <p className="pb-5 text-sm leading-relaxed text-steel-400">{children}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
