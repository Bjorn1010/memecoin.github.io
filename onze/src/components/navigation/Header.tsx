"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { AnimatePresence, motion, useMotionValueEvent, useScroll } from "motion/react";
import { Heart, Menu, Search, ShoppingBag, User } from "lucide-react";
import { cn } from "@/lib/utils";
import { spring } from "@/lib/motion";
import { useCart } from "@/components/cart/CartProvider";
import { MegaMenu, type MenuKey } from "@/components/navigation/MegaMenu";
import { MobileNav } from "@/components/navigation/MobileNav";
import { CartDrawer } from "@/components/cart/CartDrawer";
import { SearchOverlay } from "@/components/navigation/SearchOverlay";
import { ScrollProgress } from "@/components/motion/ScrollProgress";

/* Six destinations, in the order a supporter thinks: the shirt, then whose
 * shirt, then the two things that are their own reason to visit (the archive
 * and what just landed), then price. `key` marks the entries deep enough to
 * deserve a mega panel — the rest are a single link, and opening a panel over
 * them would be furniture for its own sake. */
const NAV: { key: MenuKey | null; label: string; href: string }[] = [
  { key: "maillots", label: "Maillots", href: "/maillots" },
  { key: "clubs", label: "Clubs", href: "/clubs" },
  { key: "selections", label: "Sélections", href: "/selections" },
  { key: "vintage", label: "Vintage", href: "/collections/retros" },
  { key: null, label: "Nouveautés", href: "/collections/nouveautes" },
  { key: null, label: "Promos", href: "/promotions" },
];

const TICKER = [
  "Expédition 48 h depuis la Suisse",
  "Flocage nom et numéro inclus",
  "Paiement sécurisé",
  "Retours 30 jours",
];

export function Header() {
  const [scrolled, setScrolled] = useState(false);
  const [openMenu, setOpenMenu] = useState<MenuKey | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const { count, open: openCart } = useCart();
  const pathname = usePathname();
  const { scrollY } = useScroll();

  /* Only the homepage puts full-bleed photography directly behind the header,
     so only there can the bar afford to be transparent at rest. */
  const overHero = pathname === "/" && !scrolled;

  /* Hysteresis: a single threshold flickers when a user parks the scroll on
     the boundary. */
  useMotionValueEvent(scrollY, "change", (y) => {
    setScrolled((prev) => (prev ? y > 40 : y > 88));
  });

  return (
    <>
      <header className="fixed inset-x-0 top-0 z-50" onMouseLeave={() => setOpenMenu(null)}>
        {/* Announcement ticker. It scrolls because four claims never fit on a
            phone, and dropping the fourth is worse than moving them. */}
        <div
          className={cn(
            "overflow-hidden border-b transition-colors duration-[--duration-standard]",
            overHero ? "border-transparent bg-void/30 backdrop-blur-sm" : "border-line/60 bg-void",
          )}
        >
          <div className="marquee-track py-2" aria-hidden>
            {[0, 1].map((copy) => (
              <div key={copy} className="flex shrink-0 items-center">
                {TICKER.map((item) => (
                  <span
                    key={item}
                    className="label-mono flex items-center whitespace-nowrap text-steel-400"
                  >
                    <span className="mx-5 inline-block h-1 w-1 rounded-full bg-volt" />
                    {item}
                  </span>
                ))}
              </div>
            ))}
          </div>
          {/* The same claims once, for a screen reader: the duplicated marquee
              copy above would otherwise be announced twice. */}
          <p className="sr-only">{TICKER.join(". ")}.</p>
        </div>

        <div
          className={cn(
            "border-b transition-[background-color,border-color] duration-[--duration-standard] ease-[--ease-out-expo]",
            overHero
              ? "border-transparent bg-gradient-to-b from-void/80 to-transparent"
              : scrolled
                ? "border-line/70 bg-void/85 backdrop-blur-xl"
                : "border-line/70 bg-void",
          )}
        >
          <div
            className={cn(
              "mx-auto flex max-w-[1600px] items-center gap-5 px-5 transition-[height] duration-[--duration-standard] lg:px-10",
              scrolled ? "h-16" : "h-20",
            )}
          >
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              aria-label="Ouvrir le menu"
              className="-ml-2 grid h-10 w-10 place-items-center rounded-sm text-ink transition-colors hover:text-volt lg:hidden"
            >
              <Menu size={22} strokeWidth={1.75} />
            </button>

            <Link
              href="/"
              className="font-display text-[1.7rem] leading-none text-ink"
              aria-label="ONZE, accueil"
            >
              ONZE<span className="text-volt">.</span>
            </Link>

            <nav className="ml-6 hidden items-center gap-0.5 lg:flex">
              {NAV.map((item) => {
                const active = pathname === item.href;
                return (
                  <Link
                    key={item.label}
                    href={item.href}
                    onMouseEnter={() => setOpenMenu(item.key)}
                    onFocus={() => setOpenMenu(item.key)}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "label-mono relative rounded-sm px-3 py-2 transition-colors",
                      /* item.key is null for the entries without a panel, and
                         openMenu is null whenever no panel is open — comparing
                         them directly lit those links up permanently. */
                      active || (item.key !== null && openMenu === item.key)
                        ? "text-ink"
                        : "text-steel-300 hover:text-ink",
                    )}
                  >
                    {item.label}
                    {openMenu === item.key && item.key && (
                      <motion.span
                        layoutId="nav-underline"
                        className="absolute inset-x-3 bottom-0 h-px bg-volt"
                        transition={spring.pointer}
                      />
                    )}
                  </Link>
                );
              })}
            </nav>

            <div className="ml-auto flex items-center gap-0.5">
              <button
                type="button"
                onClick={() => setSearchOpen(true)}
                aria-label="Rechercher"
                className="grid h-10 w-10 place-items-center rounded-sm text-steel-200 transition-colors hover:text-volt"
              >
                <Search size={19} strokeWidth={1.75} />
              </button>
              <Link
                href="/compte"
                aria-label="Mon compte"
                className="hidden h-10 w-10 place-items-center rounded-sm text-steel-200 transition-colors hover:text-volt sm:grid"
              >
                <User size={19} strokeWidth={1.75} />
              </Link>
              <Link
                href="/wishlist"
                aria-label="Ma wishlist"
                className="hidden h-10 w-10 place-items-center rounded-sm text-steel-200 transition-colors hover:text-volt sm:grid"
              >
                <Heart size={19} strokeWidth={1.75} />
              </Link>
              <button
                type="button"
                onClick={openCart}
                aria-label={`Panier, ${count} article${count > 1 ? "s" : ""}`}
                className="relative grid h-10 w-10 place-items-center rounded-sm text-steel-200 transition-colors hover:text-volt"
              >
                <ShoppingBag size={19} strokeWidth={1.75} />
                <AnimatePresence>
                  {count > 0 && (
                    <motion.span
                      key={count}
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      exit={{ scale: 0 }}
                      transition={spring.pop}
                      className="tabular absolute right-0 top-0.5 grid h-[18px] min-w-[18px] place-items-center rounded-full bg-volt px-1 text-[10px] font-bold text-on-volt"
                    >
                      {count}
                    </motion.span>
                  )}
                </AnimatePresence>
              </button>
            </div>
          </div>

          <ScrollProgress />

          <AnimatePresence>
            {openMenu && <MegaMenu menu={openMenu} onClose={() => setOpenMenu(null)} />}
          </AnimatePresence>
        </div>
      </header>

      <AnimatePresence>
        {mobileOpen && <MobileNav onClose={() => setMobileOpen(false)} />}
      </AnimatePresence>
      <AnimatePresence>
        {searchOpen && <SearchOverlay onClose={() => setSearchOpen(false)} />}
      </AnimatePresence>
      <CartDrawer />
    </>
  );
}

/* Shared spacer so pages start below the fixed header without every page
   re-declaring the offset — ticker plus bar. */
export function HeaderSpacer() {
  return <div aria-hidden className="h-[6.25rem]" />;
}
