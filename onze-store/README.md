# Onze — boutique de maillots de football

Boutique en ligne de maillots personnalisables, exploitée en Suisse
(Rilind Asllani et Pedro Miguel Pires Gomes, Yverdon-les-Bains). Site
statique (GitHub Pages) : expérience 3D au scroll sur l'accueil, boutique,
fiches produit configurables, panier et tunnel de commande.

La structure et la choréographie d'animation (Three.js, GSAP, Lenis)
proviennent à l'origine d'un site Webflow ; tout le contenu, les médias, la
typographie et la direction artistique sont propres à Onze. Aucun média,
son, modèle 3D, slogan ni police de la source d'origine n'est conservé.

## Pages

- `index.html` — accueil : carrousel 3D des 6 maillots, bouton « Commander »
  qui suit le maillot affiché
- `boutique.html` — la gamme, filtrable par catégorie
- `maillot-<id>.html` — une fiche produit par maillot (générées, voir plus bas) :
  aperçu 3D (rendu 2D si la 3D est indisponible), taille, flocage en direct.
  `produit.html?id=…` est le modèle, non indexé
- `a-propos.html` — présentation, comment commander, FAQ, contact
- `panier.html` — panier, progression vers la livraison offerte, suggestions
- `commande.html` — coordonnées, acceptation des CGV, envoi de la commande
- `cgv.html`, `cgu.html`, `mentions-legales.html`,
  `politique-de-confidentialite.html` — pages légales (droit suisse)

## Comment une commande arrive

Il n'y a pas de serveur ni de paiement en ligne. À la fin du tunnel, le site
rédige un récapitulatif (référence `ONZ-AAMMJJ-XXXXXX`, articles, total,
adresse) que le client envoie en un geste :

- par **WhatsApp** au 076 770 31 78 (lien `wa.me` pré-rempli), ou
- par **e-mail** à miguel.pires780@gmail.com (lien `mailto:` pré-rempli).

Le vendeur confirme la commande par écrit et envoie les instructions de
paiement ; le colis part à réception du paiement (voir CGV, articles 4 et 5).

## Configuration

Prix, frais de port, seuil de livraison offerte et coordonnées de contact
sont centralisés dans `assets/js/onze-catalogue.js` (`PRODUCTS`, `SHIPPING`,
`CONTACT`). Si un montant change, mettre aussi à jour les textes des CGV
(article 3) et le bandeau « Livraison offerte dès 120 CHF ».

## Lancer en local

```bash
cd onze-store
python3 -m http.server 8000
# puis ouvrir http://localhost:8000/index.html
```

## Générer les pages produit, le sitemap et les images

Après toute modification de `produit.html` ou du catalogue :

```bash
node onze-store/tools/build-product-pages.mjs
```

Cela réécrit les six `maillot-*.html` (titre, description, image de partage et
adresse canonique propres à chaque produit) et `sitemap.xml`. Les images
`assets/img/products/<id>-front|back.webp` sont des rendus de
`drawJerseyFlat` : à refaire si le dessin d'un maillot change.

À noter : `robots.txt` doit être à la racine du domaine ; sur
`github.io/memecoin.github.io/` ce n'est pas possible, il faudra un domaine
propre. Le sitemap peut en attendant être déclaré dans Google Search Console.

## Dépendances

Aucune ressource externe : GSAP, ScrollTrigger, SplitText, jQuery, le runtime
Webflow et Three.js (`assets/vendor/three/`) sont hébergés dans
`assets/vendor/`.

## Prochaines étapes possibles

- Paiement en ligne (Stripe, TWINT) : nécessite un backend léger
  (Cloudflare Workers / Vercel / Netlify Functions) pour créer la session
  de paiement sans jamais exposer la clé secrète côté client.
- Vraies photos produit en complément du rendu 3D.
