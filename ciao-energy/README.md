# Ciao Energy — recréation statique

Recréation fidèle du site [ciaoenergy.com](https://ciaoenergy.com) (site Webflow),
faite en récupérant le HTML publié, le CSS compilé et tous les assets (images,
polices, vidéos de fond par saveur) puis en les rendant 100% locaux/statiques.

## Fidélité

- Le CSS compilé Webflow (`assets/css/ciao-energy.css`) est celui du site réel,
  seuls les `url()` vers les polices/SVG ont été réécrits en chemins locaux.
- Tous les visuels (logo, textures par saveur, vidéos de fond `.mp4`/`.webm`,
  favicons, image OG) sont hébergés en local dans `assets/`.
- Les scripts d'interaction (Webflow, GSAP, jQuery) restent chargés depuis les
  CDN d'origine : ce sont les mêmes bundles que ceux utilisés en production,
  donc les animations (loader, scroll, sélecteur de saveur) se comportent à
  l'identique dans un navigateur normal.
- Vérification : capture d'écran de `cgu.html` en local vs. `ciaoenergy.com/cgu`
  → hash MD5 identique (rendu pixel pour pixel).
- Le script d'analytics (Umami) du site d'origine a été retiré pour ne pas
  envoyer de données de navigation sous un autre domaine.

## Pages

- `index.html` — page d'accueil
- `cgu.html` — conditions générales d'utilisation
- `mentions-legales.html` — mentions légales
- `politique-de-confidentialite.html` — politique de confidentialité

## Lancer en local

```bash
cd ciao-energy
python3 -m http.server 8000
# puis ouvrir http://localhost:8000/index.html
```

## Limites connues

- Le formulaire d'inscription à la newsletter (widget Brevo/Sendinblue) pointe
  toujours vers le service réel de Ciao Energy : ne pas l'utiliser pour des
  tests, une vraie soumission irait dans leur liste de diffusion.
- L'animation d'intro (loader vidéo) nécessite un navigateur avec décodage
  vidéo matériel/logiciel complet (H.264/VP9) — normal sur desktop et mobile.
