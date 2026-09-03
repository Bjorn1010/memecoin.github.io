# ONZE

Boutique de maillots de football premium. Next.js 16 / React 19 / TypeScript /
Tailwind v4 / Motion / React Three Fiber.

```bash
npm install
npm run dev     # http://localhost:3000
npm run build
```

## Direction artistique

Nike × Apple × Champions League. Noir profond, gris métalliques froids, et
**un seul accent volt** (`#ccff00`) réservé aux CTA et aux états actifs — la
retenue est ce qui le rend premium. Typographie : Archivo (display, tracking
serré) + Inter (UI), auto-hébergées via `next/font`.

Tous les tokens vivent dans `src/app/globals.css` sous `@theme` (Tailwind v4,
config CSS-first — il n'y a pas de `tailwind.config.js`).

## Le parti pris sur les visuels produits

**Aucune image sous licence n'est utilisée.** Les maillots sont *dessinés*, pas
photographiés :

- `components/ui/Jersey.tsx` — rendu SVG procédural à partir d'une `Colorway`
- `components/3d/jerseyTexture.ts` — le même tracé peint sur un canvas, découpé
  en alpha sur la silhouette du vêtement, servi comme texture Three.js

Conséquences : zéro octet de texture sur le réseau, aucun logo ni marque de club
reproduit, et un catalogue qui se restyle instantanément. Les noms de clubs sont
cités à titre descriptif ; les écussons sont remplacés par des monogrammes
typographiques.

Pour passer à de la vraie photographie, remplacez `Jersey.tsx` — rien d'autre
dans le code ne sait comment un maillot est dessiné.

## Système de motion

Trois paliers, définis une fois dans `src/lib/motion.ts` et en CSS :

| Palier | Durée | Usage |
|---|---|---|
| micro | 140–220 ms | hover, press, toggle |
| standard | 320–420 ms | cartes, drawers, menus, filtres |
| premium | 720–1100 ms | hero, révélations cinématiques |

Les éléments pilotés au pointeur utilisent des ressorts, pas des tweens — un
tween sur un élément qui suit le curseur donne toujours une sensation de lag.

`prefers-reduced-motion` est respecté partout : `Reveal` rend l'élément
directement présent, le hero bascule sur le maillot SVG, et le CSS écrase toutes
les durées.

## Performance

- Three.js (~150 ko gz) est en `dynamic(..., { ssr: false })` — jamais dans le
  bundle initial.
- La scène 3D n'est montée que si : pas de reduced-motion, pointeur fin,
  viewport ≥ 768 px, ≥ 4 cœurs — et 600 ms après le premier paint, pour ne pas
  concurrencer le LCP. Sinon, le maillot SVG (qui n'est pas un fallback dégradé,
  c'est le même dessin).
- `dpr` plafonné à 1.5, pas de `<Environment>` drei (chaque preset télécharge un
  HDR depuis un CDN au runtime).
- Homepage prérendue en statique.

## Architecture

```
src/
  app/            routes (App Router) + globals.css (design system)
  components/
    ui/           Jersey, Button, Badge, Price
    navigation/   Header, MegaMenu, MobileNav, SearchOverlay, Footer
    products/     ProductCard, ProductGrid, QuickView
    sections/     Hero, SectionHeader, TeamRail
    cart/         CartProvider, CartDrawer
    3d/           JerseyScene, jerseyTexture
    motion/       Reveal
  lib/
    motion.ts     tokens + variants
    types.ts      Product, Team, Colorway, CartLine
    data/         teams, products (dérivés), collections
```

Le catalogue est **dérivé** de la table des équipes via un hash déterministe
(`lib/data/products.ts`) : même sortie serveur et client, pas de dérive
d'hydratation, et ajouter une équipe génère ses kits. À remplacer par une API
commerce — tout le reste consomme le type `Product`, pas ce fichier.

## État d'avancement

Fait : design system, système de motion, header + mega-menu + nav mobile,
recherche, homepage, catalogue avec facettes et compteurs, fiche produit avec
viewer 3D 360° et flocage live, collections, panier, checkout, pages aide et
légales, sitemap, robots, JSON-LD produit. 158 pages prérendues.

Limites connues :

- Les survêtements et vestes sont rendus par le composant `Jersey`, donc ils
  ressemblent à des maillots. Il faut une silhouette dédiée par type de
  vêtement.
- La wishlist est locale à chaque carte et n'est pas persistée.
- `/compte` est un formulaire sans backend, signalé comme tel sur la page.
- Le panier vit en mémoire : un rechargement le vide. À brancher sur
  `localStorage` ou une session serveur.
- Pas encore d'audit Lighthouse chiffré.
