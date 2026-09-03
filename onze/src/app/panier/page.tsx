import type { Metadata } from "next";
import { PanierView } from "@/components/cart/PanierView";

export const metadata: Metadata = {
  title: "Mon panier",
  robots: { index: false, follow: false },
};

export default function PanierPage() {
  return <PanierView />;
}
