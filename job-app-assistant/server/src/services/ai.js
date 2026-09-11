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
  const hasPlaceholders = /\[[^\]\n]{2,80}\]/.test(baseCoverLetter || "");

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
1. Produis la LETTRE DE MOTIVATION complète, en français, pour cette entreprise. Règle la plus
   importante : ${
     hasPlaceholders
       ? `la lettre de base contient des emplacements entre crochets, du type "[Nom de l'entreprise]"
   ou "[secteur / domaine de l'entreprise]" — ce sont les SEULES parties que tu dois modifier.
   Remplace CHAQUE emplacement entre crochets par du contenu réel, spécifique et pertinent pour
   cette entreprise précise (nom, adresse si connue, secteur, raison de l'intérêt, technologies,
   etc. — en t'appuyant sur la description et le contenu récupéré ci-dessus). Le résultat final ne
   doit JAMAIS contenir de crochets "[" ou "]" : si une information est vraiment introuvable
   (ex: adresse inconnue), retire la ligne ou la phrase concernée plutôt que de laisser un
   emplacement vide ou un crochet. TOUT LE RESTE du texte (tout ce qui n'est pas entre crochets)
   doit être recopié EXACTEMENT comme dans la lettre de base, mot pour mot, dans le même ordre :
   ne reformule rien, ne raccourcis rien, ne réorganise rien qui n'est pas un emplacement à remplir.`
       : `garde au maximum le texte, la structure et le style de la lettre de base (ne réécris pas ce
   qui fonctionne déjà) et adapte seulement les passages qui font référence à une entreprise
   précise (nom, secteur, raison de l'intérêt) pour qu'ils correspondent à 100% à cette entreprise.
   Améliore uniquement les passages réellement faibles (ton, clarté, accroche, conclusion) — pas
   besoin de tout récrire si la lettre de base est déjà bonne.`
   }
   Dans tous les cas : garde les informations personnelles réelles du candidat (ne jamais inventer
   de diplôme, expérience ou compétence absente du CV ou de la lettre de base). Longueur finale :
   250 à 400 mots.
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

Réponds UNIQUEMENT avec un objet JSON valide, sans texte autour, au format exact :
{
  "cover_letter": "texte complet de la lettre",
  "cv_modifie": "texte complet du CV modifié, ou chaîne vide si aucun changement",
  "cv_changement_resume": "explication courte du changement, ou chaîne vide",
  "message_text": "le petit message d'accompagnement (signé ${fullName || "(prénom du candidat)"})"
}
`.trim();

  const data = await askJson(prompt);
  return {
    coverLetter: data.cover_letter || "",
    cvModifiedText: data.cv_modifie || "",
    cvChangeSummary: data.cv_changement_resume || "",
    messageText: data.message_text || "",
  };
}
