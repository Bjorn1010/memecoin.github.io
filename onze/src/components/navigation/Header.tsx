"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { AnimatePresence, motion, useMotionValueEvent, useScroll } from "motion/react";
import { Heart, Menu, Search, ShoppingBag, User, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { transition, spring } from "@/lib/motion";
import { useCart } from "@/components/cart/CartProvider";
import { MegaMenu, type MenuKey } from "@/components/navigation/MegaMenu";
import { MobileNav } from "@/components/navigation/MobileNav";
import { CartDrawer } from "@/components/cart/CartDrawer";
import { SearchOverlay } from "@/components/navigation/SearchOverlay";

const NAV: { key: MenuKey; label: string; href: string }[] = [
  { key: "maillots", label: "Maillots", href: "/maillots" },
  { key: "kits", label: "Kits enfants", href: "/collections/kits-enfants" },
  { key: "collections", label: "Collections", href: "/collections" },
  { key: "retros", label: "Rétros", href: "/collections/retros" },
  { key: "survetements", label: "Survêtements", href: "/collections/survetements" },
];

export function Header() {
  const [compact, setCompact] = useState(false);
  const [openMenu, setOpenMenu] = useState<MenuKey | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const { count, open: openCart } = useCart();
  const pathname = usePathname();
  const { scrollY } = useScroll();

  /* The inverted state is only correct where a turf hero actually sits behind
     the header — the homepage. Every other route starts on white, so the header
     keeps its light treatment there even at scroll 0, or it would render white
     text on a white page. */
  const onTurf = pathname === "/" && !compact;

  /* Threshold well below one viewport so the header settles almost immediately,
     and hysteresis so it cannot flicker when a user hovers the boundary. */
  useMotionValueEvent(scrollY, "change", (y) => {
    setCompact((prev) => (prev ? y > 40 : y > 88));
  });

  return (
    <>
      <header
        className={cn(
          "fixed inset-x-0 top-0 z-50 transition-[height,background-color,border-color]",
          "duration-[--duration-standard] ease-[--ease-out-expo]",
          onTurf
            ? "h-24 border-b border-transparent bg-gradient-to-b from-pitch-deep/70 via-pitch-deep/30 to-transparent"
            : compact
              ? "h-16 border-b border-ink/10 bg-paper/90 backdrop-blur-xl"
              : "h-24 border-b border-ink/10 bg-paper/90 backdrop-blur-xl",
        )}
        onMouseLeave={() => setOpenMenu(null)}
      >
        <div className="mx-auto flex h-full max-w-[1600px] items-center gap-6 px-5 lg:px-10">
          {/* Mobile menu trigger */}
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            aria-label="Ouvrir le menu"
            className={cn(
              "-ml-2 grid h-10 w-10 place-items-center rounded-sm transition-colors lg:hidden",
              onTurf ? "text-paper" : "text-steel-200 hover:text-ink",
            )}
          >
            <Menu size={22} strokeWidth={1.75} />
          </button>

          <Link
            href="/"
            className={cn(
              "font-display text-2xl leading-none tracking-[-0.04em]",
              onTurf ? "text-paper" : "text-ink",
            )}
            aria-label="ONZE, accueil"
          >
            ONZE<span className={onTurf ? "text-cup" : "text-pitch"}>.</span>
          </Link>

          {/* Desktop navigation. Hovering a trigger opens its mega panel; the
              panel and the header share one mouse-leave so travel between them
              never closes it. */}
          <nav className="ml-4 hidden items-center gap-1 lg:flex">
            {NAV.map((item) => (
              <Link
                key={item.key}
                href={item.href}
                onMouseEnter={() => setOpenMenu(item.key)}
                onFocus={() => setOpenMenu(item.key)}
                className={cn(
                  "label-mono relative rounded-sm px-3 py-2 transition-colors",
                  onTurf
                    ? "text-paper/85 hover:text-paper"
                    : openMenu === item.key
                      ? "text-ink"
                      : "text-steel-300 hover:text-ink",
                )}
              >
                {item.label}
                {openMenu === item.key && (
                  <motion.span
                    layoutId="nav-underline"
                    className={cn("absolute inset-x-3 -bottom-0.5 h-0.5", onTurf ? "bg-cup" : "bg-pitch")}
                    transition={spring.pointer}
                  />
                )}
              </Link>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-1">
            <button
              type="button"
              onClick={() => setSearchOpen(true)}
              aria-label="Rechercher"
              className={cn("grid h-10 w-10 place-items-center rounded-sm transition-colors", onTurf ? "text-paper hover:text-cup" : "text-steel-200 hover:text-ink")}
            >
              <Search size={20} strokeWidth={1.75} />
            </button>
            <Link
              href="/compte"
              aria-label="Mon compte"
              className={cn("hidden h-10 w-10 place-items-center rounded-sm transition-colors sm:grid", onTurf ? "text-paper hover:text-cup" : "text-steel-200 hover:text-ink")}
            >
              <User size={20} strokeWidth={1.75} />
            </Link>
            <Link
              href="/wishlist"
              aria-label="Ma wishlist"
              className={cn("hidden h-10 w-10 place-items-center rounded-sm transition-colors sm:grid", onTurf ? "text-paper hover:text-cup" : "text-steel-200 hover:text-ink")}
            >
              <Heart size={20} strokeWidth={1.75} />
            </Link>
            <button
              type="button"
              onClick={openCart}
              aria-label={`Panier, ${count} article${count > 1 ? "s" : ""}`}
              className={cn("relative grid h-10 w-10 place-items-center rounded-sm transition-colors", onTurf ? "text-paper hover:text-cup" : "text-steel-200 hover:text-ink")}
            >
              <ShoppingBag size={20} strokeWidth={1.75} />
              <AnimatePresence>
                {count > 0 && (
                  <motion.span
                    key={count}
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    exit={{ scale: 0 }}
                    transition={spring.pop}
                    className={cn("tabular absolute right-0.5 top-0.5 grid h-[18px] min-w-[18px] place-items-center rounded-full px-1 text-[10px] font-bold", onTurf ? "bg-cup text-ink" : "bg-pitch text-paper")}
                  >
                    {count}
                  </motion.span>
                )}
              </AnimatePresence>
            </button>
          </div>
        </div>

        <AnimatePresence>
          {openMenu && <MegaMenu menu={openMenu} onClose={() => setOpenMenu(null)} />}
        </AnimatePresence>
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
   re-declaring the offset. */
export function HeaderSpacer() {
  return <div aria-hidden className="h-24" />;
}
