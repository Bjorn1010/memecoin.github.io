# CandidAI

Application web multi-utilisateurs (PC + mobile, via le navigateur) qui prépare tes
candidatures : chacun crée son compte (email + mot de passe), et voici comment ça marche une
fois connecté :

1. Tu renseignes une fois ton **CV** (.docx), ta **lettre de motivation de référence**, et tes
   **bulletins scolaires des 3 dernières années**.
2. Pour chaque entreprise, tu donnes son **nom**, un **lien** (offre d'emploi / site carrière)
   et/ou une **description**, et **où tu l'as trouvée**.
3. L'IA (gratuite, via Groq) :
   - récupère automatiquement le contenu de la page si tu as donné un lien,
   - réécrit ta lettre de motivation pour qu'elle corresponde à 100% à cette entreprise (et
     l'améliore si elle est faible),
   - propose (rarement) des ajustements de CV — jamais appliqués automatiquement, c'est toi qui
     décides,
   - rédige un petit message d'accompagnement (style : "je viens de vous appeler, vous trouverez
     ci-dessous mon CV, ma lettre de motivation et mes bulletins scolaires...").
4. Tu relis/modifies si besoin, puis tu **télécharges** le CV, la lettre adaptée et les bulletins
   depuis la page de l'entreprise, et tu les envoies toi-même (email, SMS, en main propre…) avec
   le message généré.

Le logiciel ne t'évite pas l'envoi lui-même (volontairement, pour rester simple et fiable) : il
prépare tout — texte et fichiers — pour que ça prenne 30 secondes au lieu de tout refaire à la
main à chaque entreprise.

## Architecture

- `server/` : API Node.js/Express + base de données SQLite compatible Turso (persistante,
  hébergée). Gère les comptes (email/mot de passe hashé), le profil de chacun (CV, lettre,
  bulletins) et la génération IA par entreprise (Groq) — les données de chaque utilisateur sont
  isolées des autres.
- `web/` : interface React + Tailwind, responsive (PC et mobile) — page d'accueil, tarifs,
  inscription/connexion publiques, puis tableau de bord une fois connecté.

En production, le serveur sert directement le frontend buildé : une seule application à
déployer.

## Configuration nécessaire

- **Clé IA gratuite** : crée un compte sur https://console.groq.com (aucune carte bancaire
  requise), puis génère une clé sur https://console.groq.com/keys et mets-la dans
  `GROQ_API_KEY`.
- **Comptes utilisateurs** : chaque personne crée son propre compte (email + mot de passe,
  haché avec bcrypt) depuis la page d'inscription — pas de configuration nécessaire de ton côté.
  La session reste active 90 jours, pas besoin de se reconnecter à chaque visite.
- **Base de données Turso (gratuite, persistante)** : sans ça, tes données (profil, CV, lettres,
  entreprises) seraient effacées à chaque redéploiement sur le plan gratuit de Render.
  1. Crée un compte gratuit sur https://turso.tech (aucune carte bancaire requise).
  2. Crée une base de données (bouton "Create Database" dans le dashboard, n'importe quel nom,
     n'importe quelle région).
  3. Dans la page de la base, récupère l'**URL** (commence par `libsql://…`) et crée un **token**
     ("Create Token") — copie les deux.
  4. Mets l'URL dans `TURSO_DATABASE_URL` et le token dans `TURSO_AUTH_TOKEN`.

## Lancer en local

```bash
cd server && npm install && cp .env.example .env
# édite .env : SESSION_SECRET, GROQ_API_KEY
# (TURSO_DATABASE_URL/TURSO_AUTH_TOKEN sont optionnels en local : sans eux, un
# fichier SQLite local est utilisé automatiquement — voir server/data/app.db)
npm run dev        # démarre l'API sur http://localhost:8787

# dans un autre terminal
cd web && npm install
npm run dev         # démarre l'interface sur http://localhost:5173
```

Ouvre http://localhost:5173 (le frontend redirige les appels API vers le port 8787).

## Déployer en ligne gratuitement (Render.com)

1. Crée un compte gratuit sur https://render.com (aucune carte bancaire nécessaire pour le plan
   gratuit).
2. "New +" → "Blueprint", pointe vers ce dépôt. Render détecte `render.yaml` (dans
   `job-app-assistant/`) et propose de créer le service automatiquement.
3. Renseigne les variables d'environnement demandées : `GROQ_API_KEY`, `TURSO_DATABASE_URL` et
   `TURSO_AUTH_TOKEN` (voir "Configuration nécessaire" ci-dessus ; le `SESSION_SECRET` est généré
   automatiquement).
4. Render build l'image Docker et déploie. Une fois terminé, tu obtiens une URL du type
   `https://assistant-candidatures.onrender.com`, accessible depuis ton PC et ton téléphone.

⚠️ Le plan gratuit de Render met le service en veille après un moment d'inactivité : la première
requête après une pause peut prendre ~30 secondes à répondre, c'est normal.

Grâce à Turso, tes données (profil, CV, lettres, entreprises) sont conservées même quand le code
est mis à jour et redéployé — contrairement à un stockage sur disque local, qui serait effacé à
chaque redéploiement sur le plan gratuit de Render.

Tu peux aussi déployer l'image Docker (`Dockerfile` à la racine du dossier `job-app-assistant/`)
sur n'importe quel autre hébergeur (Railway, Fly.io, un VPS…).

## Limites connues

- Le CV n'est jamais modifié automatiquement : l'IA ne fait que proposer des pistes texte, à
  appliquer toi-même dans ton fichier .docx si tu les juges pertinentes, puis à réimporter dans
  la page Profil.
- La lettre de motivation générée est fournie en téléchargement sous forme de nouveau fichier
  .docx avec une mise en page simple et propre (pas une copie pixel-perfect d'une mise en page
  existante).
- Pas d'envoi automatique d'email : tu télécharges les documents et envoies toi-même. C'est un
  choix volontaire pour éviter la complexité et les pannes liées à l'envoi SMTP.
- Pas de vérification d'email ni de récupération de mot de passe oublié : l'inscription connecte
  directement (pensé pour un lancement rapide, pas pour de la production à grande échelle).
- La page Tarifs est indicative : seule l'offre Gratuite est réellement active, il n'y a pas
  d'intégration de paiement.
