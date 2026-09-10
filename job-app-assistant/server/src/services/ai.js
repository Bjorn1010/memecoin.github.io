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
3. Rédige un petit message court (3-4 phrases maximum, en français) qui accompagne l'envoi des
   documents suite à un appel téléphonique que le candidat vient de passer à l'entreprise. Le message
   doit : mentionner que le candidat vient d'appeler, dire qu'il joint ci-dessous son CV, sa lettre de
   motivation, et ses bulletins scolaires des 3 dernières années, et rester simple et direct (ce n'est
   pas un email formel, juste un mot d'accompagnement). Signe avec le prénom du candidat si connu.

Réponds UNIQUEMENT avec un objet JSON valide, sans texte autour, au format exact :
{
  "cover_letter": "texte complet de la lettre",
  "cv_suggestions": ["suggestion 1", "suggestion 2"],
  "message_text": "le petit message d'accompagnement (signé ${fullName || "(prénom du candidat)"})"
}
`.trim();

  const data = await askJson(prompt);
  return {
    coverLetter: data.cover_letter || "",
    cvSuggestions: Array.isArray(data.cv_suggestions) ? data.cv_suggestions : [],
    messageText: data.message_text || "",
  };
}
