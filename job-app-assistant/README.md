# Assistant Candidatures

Application web (PC + mobile, via le navigateur) qui automatise tes candidatures :

1. Tu renseignes une fois ton **CV** (.docx) et ta **lettre de motivation de référence**.
2. Pour chaque entreprise, tu donnes son **nom**, un **lien** (offre d'emploi / site
   carrière) et/ou une **description**, et **où tu l'as trouvée**.
3. L'IA (gratuite, via Google Gemini) :
   - récupère automatiquement le contenu de la page si tu as donné un lien,
   - réécrit ta lettre de motivation pour qu'elle corresponde à 100% à cette
     entreprise (et l'améliore si elle est faible),
   - propose (rarement) des ajustements de CV — jamais appliqués automatiquement,
     c'est toi qui décides,
   - rédige un email d'accompagnement expliquant pourquoi tu postules et où tu as
     trouvé l'offre.
4. Tu relis/modifies si besoin, puis tu envoies l'email (CV + lettre en pièce jointe)
   en un clic — ou tu envoies **en masse** à toutes les entreprises prêtes d'un coup.

Tout est centralisé : plus besoin de retaper une lettre ou un email à la main pour
chaque entreprise.

## Architecture

- `server/` : API Node.js/Express + base de données SQLite (fichier local). Gère le
  profil, les entreprises, la génération IA (Gemini) et l'envoi d'email (SMTP).
- `web/` : interface React + Tailwind, responsive (PC et mobile).

En production, le serveur sert directement le frontend buildé : une seule
application à déployer.

## Configuration nécessaire

- **Clé IA gratuite** : crée une clé sur https://aistudio.google.com/apikey (compte
  Google, aucune carte bancaire requise) et mets-la dans `GEMINI_API_KEY`.
- **Envoi d'email (SMTP)** : pour Gmail, active la validation en 2 étapes puis crée
  un "mot de passe d'application" sur https://myaccount.google.com/apppasswords.
  Utilise-le comme mot de passe SMTP dans la page **Profil** de l'application (hôte
  `smtp.gmail.com`, port `587`). Tout autre fournisseur email (Outlook, OVH,
  Infomaniak…) fonctionne aussi tant que tu as ses réglages SMTP.
- **Mot de passe de l'application** : comme le logiciel est hébergé en ligne et
  contient des informations personnelles (CV, identifiants email), une page de
  connexion protège tout par un mot de passe unique que tu choisis (`APP_PASSWORD`).

## Lancer en local

```bash
cd server && npm install && cp .env.example .env
# édite .env : APP_PASSWORD, SESSION_SECRET, GEMINI_API_KEY
npm run dev        # démarre l'API sur http://localhost:8787

# dans un autre terminal
cd web && npm install
npm run dev         # démarre l'interface sur http://localhost:5173
```

Ouvre http://localhost:5173 (le frontend redirige les appels API vers le port 8787).

## Déployer en ligne gratuitement (Render.com)

1. Crée un compte gratuit sur https://render.com (aucune carte bancaire nécessaire
   pour le plan gratuit).
2. "New +" → "Blueprint", pointe vers ce dépôt (ou vers un fork si tu préfères
   séparer ce projet). Render détecte `render.yaml` et propose de créer le service
   automatiquement.
3. Renseigne les variables d'environnement demandées : `APP_PASSWORD`,
   `GEMINI_API_KEY` (le `SESSION_SECRET` est généré automatiquement).
4. Render build l'image Docker et déploie. Une fois terminé, tu obtiens une URL du
   type `https://assistant-candidatures.onrender.com`, accessible depuis ton PC et
   ton téléphone.

⚠️ Le plan gratuit de Render met le service en veille après un moment d'inactivité :
la première requête après une pause peut prendre ~30 secondes à répondre, c'est
normal.

Tu peux aussi déployer l'image Docker (`Dockerfile` à la racine) sur n'importe quel
autre hébergeur (Railway, Fly.io, un VPS…).

## Limites connues

- La génération et l'envoi "en masse" traitent les entreprises l'une après l'autre
  (pas en parallèle), pour rester dans les limites gratuites de l'API IA et éviter
  d'être marqué comme spam par les serveurs email.
- Le CV n'est jamais modifié automatiquement : l'IA ne fait que proposer des pistes
  texte, à appliquer toi-même dans ton fichier .docx si tu les juges pertinentes,
  puis à réimporter dans la page Profil.
- La lettre de motivation générée est envoyée sous forme de nouveau fichier .docx
  avec une mise en page simple et propre (pas une copie pixel-perfect d'une mise en
  page existante).
- Une seule "identité" (profil) par installation : pensé pour un usage personnel,
  pas multi-utilisateurs.
