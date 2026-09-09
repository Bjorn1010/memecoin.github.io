const MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions";

async function askJson(prompt) {
  const apiKey = process.env.MISTRAL_API_KEY;
  if (!apiKey) {
    throw new Error(
      "MISTRAL_API_KEY manquante. Crée une clé gratuite sur https://console.mistral.ai/api-keys et ajoute-la dans server/.env"
    );
  }

  const res = await fetch(MISTRAL_API_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: "mistral-small-latest",
      messages: [{ role: "user", content: prompt }],
      response_format: { type: "json_object" },
      temperature: 0.7,
    }),
  });

  if (!res.ok) {
    const errText = await res.text().catch(() => "");
    throw new Error(`Erreur API Mistral (${res.status}) : ${errText.slice(0, 300)}`);
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
 * de modification du CV (rare), et un brouillon d'email.
 */
export async function generateApplication({
  fullName,
  cvText,
  baseCoverLetter,
  companyName,
  companyDescription,
  fetchedContext,
  source,
}) {
  const prompt = `
Tu es un expert en recrutement francophone qui aide un candidat à personnaliser sa candidature.

Voici le CV du candidat (texte brut) :
"""
${cvText || "(non fourni)"}
"""

Voici la lettre de motivation "de base" du candidat, qui sert de style/référence :
"""
${baseCoverLetter || "(non fournie)"}
"""

Voici les informations sur l'entreprise ciblée :
- Nom : ${companyName}
- Description fournie par le candidat : ${companyDescription || "(aucune)"}
- Où l'offre/l'entreprise a été trouvée : ${source || "(non précisé)"}
- Contenu récupéré automatiquement depuis le lien fourni (peut être vide) :
"""
${fetchedContext ? fetchedContext.slice(0, 6000) : "(aucun)"}
"""

Tâches :
1. Réécris une LETTRE DE MOTIVATION complète, en français, qui correspond à 100% à cette entreprise
   (mentionne des éléments précis de l'entreprise/offre quand c'est possible), donne envie de recruter
   le candidat, et améliore la lettre de base si elle est faible (ton, structure, clarté, accroche,
   conclusion). Garde le style et les informations personnelles réelles du candidat (ne pas inventer
   de diplômes/expériences qui ne sont pas dans le CV ou la lettre de base). Longueur : 250 à 400 mots.
2. Indique si le CV a besoin d'être modifié pour ce poste précis. C'est RARE : ne propose des
   changements QUE si c'est vraiment utile (ex: réordonner 2 expériences, mettre en avant une
   compétence déjà présente dans le CV). Ne jamais inventer de contenu absent du CV. Si rien à changer,
   renvoie une liste vide.
3. Rédige un email court et professionnel (objet + corps) pour accompagner la candidature, qui explique
   clairement pourquoi on postule et où l'offre/l'entreprise a été trouvée (utilise le champ "source").
   Le corps doit mentionner que le CV et la lettre de motivation sont en pièce jointe.

Réponds UNIQUEMENT avec un objet JSON valide, sans texte autour, au format exact :
{
  "cover_letter": "texte complet de la lettre",
  "cv_suggestions": ["suggestion 1", "suggestion 2"],
  "email_subject": "objet de l'email",
  "email_body": "corps de l'email (avec formules de politesse, signé ${fullName || "(nom du candidat)"})"
}
`.trim();

  const data = await askJson(prompt);
  return {
    coverLetter: data.cover_letter || "",
    cvSuggestions: Array.isArray(data.cv_suggestions) ? data.cv_suggestions : [],
    emailSubject: data.email_subject || `Candidature - ${companyName}`,
    emailBody: data.email_body || "",
  };
}
