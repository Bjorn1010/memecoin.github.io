"use client";

import Link from "next/link";
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
  const { scrollY } = useScroll();

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
          compact
            ? "h-16 border-b border-white/8 bg-void/80 backdrop-blur-xl"
            : "h-24 border-b border-transparent bg-gradient-to-b from-void/90 to-transparent",
        )}
        onMouseLeave={() => setOpenMenu(null)}
      >
        <div className="mx-auto flex h-full max-w-[1600px] items-center gap-6 px-5 lg:px-10">
          {/* Mobile menu trigger */}
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            aria-label="Ouvrir le menu"
            className="-ml-2 grid h-10 w-10 place-items-center rounded-sm text-steel-200 transition-colors hover:text-white lg:hidden"
          >
            <Menu size={22} strokeWidth={1.75} />
          </button>

          <Link
            href="/"
            className="font-display text-2xl leading-none tracking-[-0.04em] text-white"
            aria-label="ONZE, accueil"
          >
            ONZE<span className="text-volt">.</span>
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
                  openMenu === item.key ? "text-white" : "text-steel-300 hover:text-white",
                )}
              >
                {item.label}
                {openMenu === item.key && (
                  <motion.span
                    layoutId="nav-underline"
                    className="absolute inset-x-3 -bottom-0.5 h-px bg-volt"
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
              className="grid h-10 w-10 place-items-center rounded-sm text-steel-200 transition-colors hover:text-white"
            >
              <Search size={20} strokeWidth={1.75} />
            </button>
            <Link
              href="/compte"
              aria-label="Mon compte"
              className="hidden h-10 w-10 place-items-center rounded-sm text-steel-200 transition-colors hover:text-white sm:grid"
            >
              <User size={20} strokeWidth={1.75} />
            </Link>
            <Link
              href="/wishlist"
              aria-label="Ma wishlist"
              className="hidden h-10 w-10 place-items-center rounded-sm text-steel-200 transition-colors hover:text-white sm:grid"
            >
              <Heart size={20} strokeWidth={1.75} />
            </Link>
            <button
              type="button"
              onClick={openCart}
              aria-label={`Panier, ${count} article${count > 1 ? "s" : ""}`}
              className="relative grid h-10 w-10 place-items-center rounded-sm text-steel-200 transition-colors hover:text-white"
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
                    className="tabular absolute right-0.5 top-0.5 grid h-[18px] min-w-[18px] place-items-center rounded-full bg-volt px-1 text-[10px] font-bold text-void"
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
