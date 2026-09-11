import { applyReplacements } from "./docx.js";

const GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions";

async function askJson(prompt) {
  const apiKey = process.env.GROQ_API_KEY;
  if (!apiKey) {
    throw new Error(
      "GROQ_API_KEY manquante. Crée une clé gratuite sur https://console.groq.com/keys et ajoute-la dans server/.env"
    );
  }

  const res = await fetch(GROQ_API_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: "openai/gpt-oss-120b",
      messages: [{ role: "user", content: prompt }],
      response_format: { type: "json_object" },
      temperature: 0.7,
    }),
  });

  if (!res.ok) {
    const errText = await res.text().catch(() => "");
    throw new Error(`Erreur API Groq (${res.status}) : ${errText.slice(0, 300)}`);
  }

  const data = await res.json();
  const text = data.choices?.[0]?.message?.content;
  if (!text) {
    throw new Error("Réponse IA vide ou invalide.");
  }
  return JSON.parse(text);
}

/**
 * Génère une lettre de motivation adaptée à 100% à l'entreprise, une suggestion
 * de modification du CV (rare), et un petit message d'accompagnement.
 */
export async function generateApplication({
  fullName,
  cvText,
  baseCoverLetter,
  companyName,
  companyAddress,
  companyDescription,
  fetchedContext,
  source,
}) {
  const placeholders = [
    ...new Set(
      [...(baseCoverLetter || "").matchAll(/\[[^\]\n]{2,80}\]/g)].map((m) => m[0])
    ),
  ];
  const hasPlaceholders = placeholders.length > 0;

  const prompt = `
Tu es un expert en recrutement francophone qui aide un candidat à personnaliser sa candidature.

Voici le CV du candidat (texte brut) :
"""
${cvText || "(non fourni)"}
"""

Voici la lettre de motivation "de base" du candidat, qui sert de référence :
"""
${baseCoverLetter || "(non fournie)"}
"""

Voici les informations sur l'entreprise ciblée :
- Nom : ${companyName}
- Adresse : ${companyAddress || "(inconnue)"}
- Description fournie par le candidat : ${companyDescription || "(aucune)"}
- Où l'offre/l'entreprise a été trouvée : ${source || "(non précisé)"}
- Contenu récupéré automatiquement depuis le lien fourni (peut être vide) :
"""
${fetchedContext ? fetchedContext.slice(0, 6000) : "(aucun)"}
"""

Tâches :
1. ${
    hasPlaceholders
      ? `La lettre de base est un MODÈLE FIGÉ : elle ne doit JAMAIS être réécrite, reformulée ou
   réorganisée. Elle contient exactement ces emplacements entre crochets à remplir :
   ${placeholders.map((p) => `"${p}"`).join(", ")}
   Pour CHAQUE emplacement listé ci-dessus, trouve une valeur de remplacement réelle, spécifique et
   pertinente pour cette entreprise précise (nom, adresse si connue, secteur, raison de l'intérêt,
   technologies, etc. — en t'appuyant sur la description et le contenu récupéré ci-dessus). La
   valeur de remplacement ne doit contenir ni le crochet ouvrant "[" ni le crochet fermant "]", et
   doit s'insérer naturellement dans la phrase existante à la place de l'emplacement (même
   ponctuation, même grammaire). Si une information est vraiment introuvable pour un emplacement
   donné (ex: adresse inconnue), renvoie une chaîne vide pour cet emplacement plutôt que d'inventer.
   Ne produis PAS le texte complet de la lettre : uniquement le dictionnaire de remplacement
   demandé dans "champs" ci-dessous.
   Contraintes très importantes sur le CONTENU et le TON de chaque valeur :
   - La lettre finale doit tenir sur UNE SEULE PAGE A4. La mise en page ne bouge pas, donc reste
     COURT : les emplacements insérés dans une phrase (comme le secteur, la raison de l'intérêt,
     un projet) = quelques mots seulement, jamais une phrase complète. Les emplacements qui
     forment un paragraphe entier à eux seuls (ex: "[À adapter pour chaque entreprise]",
     "[À adapter si nécessaire]") = 1 à 2 phrases courtes maximum, pas plus.
   - Écris comme un vrai apprenti de 16-18 ans le ferait, avec ses mots à lui : simple, direct,
     naturel, un peu maladroit si besoin — surtout PAS un ton marketing/corporate ni des
     formulations qui sonnent "généré par une IA" (pas de tournures pompeuses, pas de mots
     savants ou de jargon d'entreprise style "solutions innovantes", "environnement dynamique",
     "gestion de la sauvegarde des données", etc.). Reste crédible et modeste : ne mentionne que
     des compétences ou intérêts réalistes pour un apprenti débutant, cohérents avec le CV et le
     reste de la lettre — n'invente pas de sujet technique avancé qui ne s'y trouve pas déjà.`
      : `Produis la LETTRE DE MOTIVATION complète, en français, pour cette entreprise, dans le champ
   "cover_letter". Garde au maximum le texte, la structure et le style de la lettre de base (ne
   réécris pas ce qui fonctionne déjà) et adapte seulement les passages qui font référence à une
   entreprise précise (nom, secteur, raison de l'intérêt) pour qu'ils correspondent à 100% à cette
   entreprise. Améliore uniquement les passages réellement faibles (ton, clarté, accroche,
   conclusion) — pas besoin de tout récrire si la lettre de base est déjà bonne. Dans tous les cas :
   garde les informations personnelles réelles du candidat (ne jamais inventer de diplôme,
   expérience ou compétence absente du CV ou de la lettre de base). Longueur finale : 250 à 400
   mots.`
  }
2. Décide si le CV a besoin d'être modifié pour ce poste précis. C'est RARE : ne le fais QUE si
   c'est vraiment utile (ex: réordonner 2 expériences, mettre en avant une compétence déjà
   présente dans le CV, reformuler un intitulé pour mieux correspondre à l'offre). Ne JAMAIS
   inventer de diplôme, expérience ou compétence absente du CV fourni.
   - Si un changement est justifié : renvoie dans "cv_modifie" le TEXTE COMPLET du CV modifié
     (toutes les sections, pas seulement la partie changée, pour pouvoir régénérer le document
     en entier), et dans "cv_changement_resume" une phrase expliquant ce qui a changé et pourquoi.
   - Si rien à changer (cas le plus fréquent) : renvoie une chaîne vide ("") pour ces deux champs.
3. Rédige un petit message court (3-4 phrases maximum, en français) qui accompagne l'envoi des
   documents suite à un appel téléphonique que le candidat vient de passer à l'entreprise. Le message
   doit : mentionner que le candidat vient d'appeler, dire qu'il joint ci-dessous son CV, sa lettre de
   motivation, et ses bulletins scolaires des 3 dernières années, et rester simple et direct (ce n'est
   pas un email formel, juste un mot d'accompagnement). Signe avec le prénom du candidat si connu.
4. Cherche l'adresse postale complète de l'entreprise (rue, code postal, ville) dans le contenu
   récupéré depuis le lien fourni ci-dessus. Si tu la trouves clairement, renvoie-la dans
   "adresse_entreprise". Ne l'invente JAMAIS : si elle n'apparaît pas clairement dans le contenu
   fourni, renvoie une chaîne vide.

Réponds UNIQUEMENT avec un objet JSON valide, sans texte autour, au format exact :
{${
    hasPlaceholders
      ? `
  "champs": { ${placeholders.map((p) => `"${p}": "valeur de remplacement"`).join(", ")} },`
      : `
  "cover_letter": "texte complet de la lettre",`
  }
  "cv_modifie": "texte complet du CV modifié, ou chaîne vide si aucun changement",
  "cv_changement_resume": "explication courte du changement, ou chaîne vide",
  "message_text": "le petit message d'accompagnement (signé ${fullName || "(prénom du candidat)"})",
  "adresse_entreprise": "adresse postale trouvée, ou chaîne vide si introuvable"
}
`.trim();

  const data = await askJson(prompt);

  let coverLetterText;
  let coverLetterReplacements = null;
  if (hasPlaceholders) {
    coverLetterReplacements = {};
    for (const p of placeholders) {
      coverLetterReplacements[p] = (data.champs && data.champs[p]) || "";
    }

    // L'IA renvoie parfois l'adresse trouvée uniquement dans "adresse_entreprise" sans
    // remplir l'emplacement correspondant dans "champs" : on complète nous-mêmes plutôt
    // que de laisser un emplacement d'adresse vide dans la lettre.
    const knownAddress = (companyAddress || data.adresse_entreprise || "").trim();
    if (knownAddress) {
      const streetKey = placeholders.find(
        (p) => /adresse/i.test(p) && !/npa|ville/i.test(p)
      );
      const cityKey = placeholders.find((p) => /npa|ville|code postal/i.test(p));
      const parts = knownAddress.split(",").map((s) => s.trim());
      if (streetKey && !coverLetterReplacements[streetKey]) {
        coverLetterReplacements[streetKey] = parts.length > 1 ? parts.slice(0, -1).join(", ") : knownAddress;
      }
      if (cityKey && !coverLetterReplacements[cityKey] && parts.length > 1) {
        coverLetterReplacements[cityKey] = parts[parts.length - 1];
      }
    }

    coverLetterText = applyReplacements(baseCoverLetter, coverLetterReplacements);
  } else {
    coverLetterText = data.cover_letter || "";
  }

  return {
    coverLetter: coverLetterText,
    coverLetterReplacements,
    cvModifiedText: data.cv_modifie || "",
    cvChangeSummary: data.cv_changement_resume || "",
    messageText: data.message_text || "",
    foundAddress: data.adresse_entreprise || "",
  };
}
