"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { CartLine, Product } from "@/lib/types";

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
}

const Ctx = createContext<CartContext | null>(null);

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [lastAdded, setLastAdded] = useState<string | null>(null);

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
    };
  }, [lines, isOpen, lastAdded, add, remove, setQuantity]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useCart() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useCart doit être utilisé dans un CartProvider");
  return ctx;
}
