import type { Metadata, Viewport } from "next";
import { Oswald, Geist } from "next/font/google";
import "./globals.css";
import { Header } from "@/components/navigation/Header";
import { Footer } from "@/components/navigation/Footer";
import { CartProvider } from "@/components/cart/CartProvider";
import { CursorLabel } from "@/components/motion/CursorLabel";
import { Boot } from "@/components/motion/Boot";
import { SmoothScroll } from "@/components/motion/SmoothScroll";

/* Self-hosted by next/font — no render-blocking request to Google, and no
 * layout shift because the metrics are known at build time. */
/* Oswald is the identity: a condensed grotesque set at a restrained medium
 * weight, always uppercase in use. Display-only — never set a paragraph in it. */
const oswald = Oswald({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-oswald",
  display: "swap",
});

const geist = Geist({
  subsets: ["latin"],
  variable: "--font-geist",
  display: "swap",
});

/* Kept in sync with next.config.ts's basePath — see the comment there for why
   the path includes the repo name. */
const SITE = "https://bjorn1010.github.io/memecoin.github.io/onze";

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
    <html lang="fr" data-scroll-behavior="smooth" className={`${oswald.variable} ${geist.variable}`}>
      <head>
        {/* Scroll reveals set their start state inline, which means a visitor
            without JavaScript — and any crawler that does not run it — would
            get a page of invisible headings. This makes the final state the
            no-JS state. */}
        <noscript>
          <style>{`[style*="opacity:0"],[style*="opacity: 0"]{opacity:1!important;transform:none!important}`}</style>
        </noscript>
      </head>
      <body>
        <a
          href="#contenu"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:bg-ink focus:px-4 focus:py-2 focus:font-display focus:text-sm focus:uppercase focus:text-void"
        >
          Aller au contenu
        </a>
        <Boot />
        <SmoothScroll>
          <CartProvider>
            <Header />
            <main id="contenu">{children}</main>
            <Footer />
            <CursorLabel />
          </CartProvider>
        </SmoothScroll>
      </body>
    </html>
  );
}
