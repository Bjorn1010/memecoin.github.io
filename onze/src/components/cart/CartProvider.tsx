"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { CartLine, Product } from "@/lib/types";

const STORAGE_KEY = "onze.cart.v1";

/* Reading localStorage during render would desync server and client HTML, so
 * the cart starts empty and hydrates in an effect. The brief flash of an empty
 * badge is the correct trade for never shipping a hydration mismatch. */
function loadCart(): CartLine[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    /* Stored data is user-controlled and may predate a schema change, so every
       line is validated rather than trusted. */
    return parsed.filter(
      (l): l is CartLine =>
        !!l &&
        typeof l === "object" &&
        typeof (l as CartLine).productId === "string" &&
        typeof (l as CartLine).size === "string" &&
        typeof (l as CartLine).price === "number" &&
        Number.isFinite((l as CartLine).price) &&
        typeof (l as CartLine).quantity === "number" &&
        (l as CartLine).quantity > 0,
    );
  } catch {
    /* Private mode, disabled storage, corrupt JSON — an empty cart beats a crash. */
    return [];
  }
}

/* Client-side cart. Deliberately a plain context rather than a store library —
 * the state is small, and this keeps the client bundle honest. Swap the
 * internals for a commerce SDK without touching consumers. */

interface CartContext {
  lines: CartLine[];
  isOpen: boolean;
  count: number;
  subtotal: number;
  /** Set when a line is added, so the drawer can animate the arriving item. */
  lastAdded: string | null;
  add: (product: Product, size: string, quantity?: number) => void;
  remove: (productId: string, size: string) => void;
  setQuantity: (productId: string, size: string, quantity: number) => void;
  open: () => void;
  close: () => void;
  clear: () => void;
}

const Ctx = createContext<CartContext | null>(null);

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [lastAdded, setLastAdded] = useState<string | null>(null);
  const hydrated = useRef(false);

  /* Restore on mount. */
  useEffect(() => {
    const stored = loadCart();
    if (stored.length) setLines(stored);
    hydrated.current = true;
  }, []);

  /* Persist on change — but not before the restore has run, or the first
     render would write an empty array over a real saved cart. */
  useEffect(() => {
    if (!hydrated.current) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(lines));
    } catch {
      /* Storage full or blocked. The in-memory cart still works for this
         session, which is better than breaking checkout over a quota error. */
    }
  }, [lines]);

  const add = useCallback((product: Product, size: string, quantity = 1) => {
    setLines((prev) => {
      const existing = prev.find((l) => l.productId === product.id && l.size === size);
      if (existing) {
        return prev.map((l) =>
          l === existing ? { ...l, quantity: l.quantity + quantity } : l,
        );
      }
      return [
        ...prev,
        {
          productId: product.id,
          slug: product.slug,
          name: product.name,
          team: product.team,
          size,
          price: product.price,
          quantity,
          colorway: product.colorway,
        },
      ];
    });
    setLastAdded(`${product.id}-${size}`);
    setIsOpen(true);
  }, []);

  const remove = useCallback((productId: string, size: string) => {
    setLines((prev) => prev.filter((l) => !(l.productId === productId && l.size === size)));
  }, []);

  const setQuantity = useCallback((productId: string, size: string, quantity: number) => {
    setLines((prev) =>
      quantity <= 0
        ? prev.filter((l) => !(l.productId === productId && l.size === size))
        : prev.map((l) =>
            l.productId === productId && l.size === size ? { ...l, quantity } : l,
          ),
    );
  }, []);

  const value = useMemo<CartContext>(() => {
    const count = lines.reduce((n, l) => n + l.quantity, 0);
    const subtotal = lines.reduce((n, l) => n + l.price * l.quantity, 0);
    return {
      lines,
      isOpen,
      count,
      subtotal,
      lastAdded,
      add,
      remove,
      setQuantity,
      open: () => setIsOpen(true),
      close: () => setIsOpen(false),
      clear: () => setLines([]),
    };
  }, [lines, isOpen, lastAdded, add, remove, setQuantity]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useCart() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useCart doit être utilisé dans un CartProvider");
  return ctx;
}
