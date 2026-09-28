# Onze — boutique de maillots (démo)

Site de démonstration pour une marque fictive de maillots de football,
**Onze**. Construit en partant d'un mirroir statique de
[ciaoenergy.com](https://ciaoenergy.com) (structure, CSS, choréographie
d'animation Three.js/GSAP/Lenis) puis entièrement rebrandé : la canette 3D
est remplacée par un maillot 3D procédural, et tout le contenu (textes,
couleurs, logo, FAQ, mentions légales) a été réécrit pour Onze.

## Ce qui a changé par rapport au mirroir Ciao Energy d'origine

- **Scène 3D** : le modèle de canette (`can.glb`) est remplacé par une
  géométrie de maillot construite procéduralement dans Three.js
  (`ExtrudeGeometry` + `UVGenerator` maison), texturée par un canvas généré
  à la volée (couleurs, numéro, nom du maillot). Le reste du moteur 3D
  (caméra, carrousel au scroll, éclairage, HDRI, composeur/bloom) n'a pas
  été touché — seule la partie « quel objet afficher » a changé.
- **Contenu** : les 6 saveurs Ciao Energy sont devenues 6 maillots
  (Domicile Noir, Extérieur Blanc, Third Doré, Gardien Vert, Training Gris,
  Édition Limitée), les 4 arguments nutritionnels sont devenus 4 arguments
  textile (tissu technique, flocage thermocollé, coupe athlétique, couleurs
  qui tiennent), la FAQ a été réécrite en conséquence.
- **Marque** : logo, favicons, image OG et écran de chargement redessinés
  pour « ONZE » (SVG texte + canvas générés, pas d'assets Ciao Energy
  visibles).
- **Formulaire newsletter neutralisé** : le vrai backend Brevo et la vraie
  clé reCAPTCHA de Ciao Energy ont été retirés. Le formulaire est une
  simulation purement statique (affiche le message de succès existant sans
  rien transmettre nulle part).
- **Pages légales** : les informations d'entreprise de Ciao Energy ont été
  retirées et remplacées par les informations réelles de l'exploitant du
  site (mentions légales, CGV, CGU, politique de confidentialité — droit
  suisse). Le code postal et la localité de l'adresse restent à compléter
  (voir `[code postal et localité à compléter]` dans les 3 fichiers).

## Pages

- `index.html` — page d'accueil
- `cgu.html` — conditions générales d'utilisation
- `cgv.html` — conditions générales de vente
- `mentions-legales.html` — mentions légales
- `politique-de-confidentialite.html` — politique de confidentialité

## Lancer en local

```bash
cd onze-store
python3 -m http.server 8000
# puis ouvrir http://localhost:8000/index.html
```

## Limites connues

- Le formulaire newsletter ne fait rien de réel (aucun envoi, aucun
  stockage) : c'est une démonstration d'interface uniquement.
- Le tunnel de commande (`panier.html` → `commande.html`) n'est pas encore
  relié à un moyen de paiement réel : aucune commande ne peut être payée en
  ligne pour l'instant (voir la section Paiement des CGV). Il faudra un
  backend léger (Cloudflare Workers / Vercel / Netlify Functions) pour créer
  une session Stripe côté serveur sans jamais exposer la clé secrète
  côté client.
- Le code postal et la localité de l'adresse de l'exploitant sont à
  compléter dans `mentions-legales.html`, `cgu.html`, `cgv.html` et
  `politique-de-confidentialite.html` (recherchez
  `[code postal et localité à compléter]`).
- L'animation d'intro (vidéo de fond en boucle) nécessite un navigateur
  avec décodage vidéo matériel/logiciel complet (H.264/VP9) — normal sur
  desktop et mobile.
