# Ciao Energy — recréation statique

Recréation fidèle du site [ciaoenergy.com](https://ciaoenergy.com) (site Webflow
avec une scène 3D WebGL custom), faite en récupérant le HTML publié, le CSS
compilé et tous les assets (images, polices, vidéos de fond, modèles 3D,
sons) puis en les rendant 100% locaux/statiques.

## Fidélité

- Le CSS compilé Webflow (`assets/css/ciao-energy.css`) est celui du site réel,
  seuls les `url()` vers les polices/SVG ont été réécrits en chemins locaux.
- Tous les visuels (logo, textures par saveur, vidéos de fond `.mp4`/`.webm`,
  favicons, image OG) sont hébergés en local dans `assets/`.
- La canette 3D qui suit le scroll est une vraie scène Three.js/WebGL (pas une
  vidéo) : les modèles `.glb` (canette + socle), la texture d'environnement
  `.hdr` et les sons d'interface (`.mp3`) du site réel sont aussi rapatriés en
  local, dans `assets/webgl/` et `assets/audio/`. Le script custom qui pilote
  la caméra/le carrousel au scroll (Three.js + GSAP ScrollTrigger + Lenis)
  n'a pas été touché, seules les URLs d'assets ont été réécrites.
- Les librairies (Three.js, GSAP, jQuery, Webflow, Lenis, reCAPTCHA) restent
  chargées depuis leurs CDN d'origine : ce sont les mêmes bundles que ceux
  utilisés en production, donc toutes les animations (loader, scroll,
  carrousel de canettes, sélecteur de saveur) se comportent à l'identique
  dans un navigateur normal.
- Vérifications faites :
  - Capture d'écran de `cgu.html` en local vs. `ciaoenergy.com/cgu` → hash
    MD5 identique (rendu pixel pour pixel).
  - Rendu de la scène 3D piloté via Chrome DevTools Protocol (chargement réel,
    puis scroll simulé) : la canette et le carrousel apparaissent et bougent
    exactement comme sur le site réel testé dans les mêmes conditions.
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
