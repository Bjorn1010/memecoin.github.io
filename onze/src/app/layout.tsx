import type { Metadata, Viewport } from "next";
import { Archivo, Inter } from "next/font/google";
import "./globals.css";
import { Header } from "@/components/navigation/Header";
import { Footer } from "@/components/navigation/Footer";
import { CartProvider } from "@/components/cart/CartProvider";

/* Self-hosted by next/font — no render-blocking request to Google, and no
 * layout shift because the metrics are known at build time. */
const archivo = Archivo({
  subsets: ["latin"],
  weight: ["600", "700", "800", "900"],
  variable: "--font-archivo",
  display: "swap",
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const SITE = "https://onze.example";

export const metadata: Metadata = {
  metadataBase: new URL(SITE),
  title: {
    default: "ONZE — Maillots de football premium",
    /* Page titles read "Real Madrid Domicile 26/27 — ONZE". */
    template: "%s — ONZE",
  },
  description:
    "Maillots de football, kits enfants, rétros et éditions spéciales. Flocage inclus, expédition depuis la Suisse.",
  keywords: [
    "maillot de football",
    "maillot foot",
    "kit enfant",
    "maillot rétro",
    "édition spéciale",
    "survêtement football",
  ],
  openGraph: {
    type: "website",
    locale: "fr_CH",
    siteName: "ONZE",
    title: "ONZE — Maillots de football premium",
    description:
      "Maillots de football, kits enfants, rétros et éditions spéciales. Flocage inclus.",
  },
  twitter: {
    card: "summary_large_image",
    title: "ONZE — Maillots de football premium",
    description: "Maillots de football, kits enfants, rétros et éditions spéciales.",
  },
  robots: { index: true, follow: true },
  alternates: { canonical: "/" },
};

export const viewport: Viewport = {
  themeColor: "#050506",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    /* `data-scroll-behavior="smooth"` is required in Next 16 for the router to
       honour the CSS smooth scroll on navigation. */
    <html lang="fr" data-scroll-behavior="smooth" className={`${archivo.variable} ${inter.variable}`}>
      <body>
        <a
          href="#contenu"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-sm focus:bg-pitch focus:px-4 focus:py-2 focus:font-display focus:text-sm focus:uppercase focus:text-paper"
        >
          Aller au contenu
        </a>
        <CartProvider>
          <Header />
          <main id="contenu">{children}</main>
          <Footer />
        </CartProvider>
      </body>
    </html>
  );
}
