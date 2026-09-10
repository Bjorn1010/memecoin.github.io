# Assistant Candidatures

Application web (PC + mobile, via le navigateur) qui prépare tes candidatures :

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

- `server/` : API Node.js/Express + base de données SQLite (fichier local). Gère le profil
  (CV, lettre, bulletins) et la génération IA par entreprise (Groq).
- `web/` : interface React + Tailwind, responsive (PC et mobile).

En production, le serveur sert directement le frontend buildé : une seule application à
déployer.

## Configuration nécessaire

- **Clé IA gratuite** : crée un compte sur https://console.groq.com (aucune carte bancaire
  requise), puis génère une clé sur https://console.groq.com/keys et mets-la dans
  `GROQ_API_KEY`.
- **Mot de passe de l'application** : comme le logiciel est hébergé en ligne et contient des
  informations personnelles (CV, bulletins scolaires), une page de connexion protège tout par un
  mot de passe unique que tu choisis (`APP_PASSWORD`).

## Lancer en local

```bash
cd server && npm install && cp .env.example .env
# édite .env : APP_PASSWORD, SESSION_SECRET, GROQ_API_KEY
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
3. Renseigne les variables d'environnement demandées : `APP_PASSWORD`, `GROQ_API_KEY` (le
   `SESSION_SECRET` est généré automatiquement).
4. Render build l'image Docker et déploie. Une fois terminé, tu obtiens une URL du type
   `https://assistant-candidatures.onrender.com`, accessible depuis ton PC et ton téléphone.

⚠️ Le plan gratuit de Render met le service en veille après un moment d'inactivité : la première
requête après une pause peut prendre ~30 secondes à répondre, c'est normal.

⚠️ Le plan gratuit de Render ne permet pas de disque persistant : la base de données (profil,
entreprises, lettres générées) est donc **réinitialisée à chaque redéploiement** (par exemple si
tu modifies le code) — mais pas lors d'une simple mise en veille/réveil. Pour un usage plus
durable, passe au plan payant le moins cher de Render (~7 $/mois) et ajoute un bloc `disk` dans
`render.yaml`, ou héberge sur un service avec stockage persistant inclus (un petit VPS, par
exemple).

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
- Une seule "identité" (profil) par installation : pensé pour un usage personnel, pas
  multi-utilisateurs.
