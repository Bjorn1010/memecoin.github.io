import { applyReplacements } from "./docx.js";

const GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions";

// Le modèle génère parfois un JSON mal formé (coupé, guillemet mal échappé...) —
// c'est un aléa connu des LLM, surtout avec un prompt long. On retente
// automatiquement quelques fois avant de faire remonter une erreur à l'utilisateur.
const MAX_AI_ATTEMPTS = 3;

async function askJson(prompt) {
  const apiKey = process.env.GROQ_API_KEY;
  if (!apiKey) {
    throw new Error(
      "GROQ_API_KEY manquante. Crée une clé gratuite sur https://console.groq.com/keys et ajoute-la dans server/.env"
    );
  }

  let lastError;
  for (let attempt = 1; attempt <= MAX_AI_ATTEMPTS; attempt++) {
    try {
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
          temperature: 0.5,
          max_tokens: 8192,
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
    } catch (err) {
      lastError = err;
    }
  }
  throw new Error(
    `${lastError.message} (échec après ${MAX_AI_ATTEMPTS} tentatives — réessaie, c'est généralement temporaire)`
  );
}

// Limites de longueur (en caractères) pour garantir que la lettre tienne sur une
// seule page quoi que renvoie l'IA — filet de sécurité déterministe en plus des
// consignes données dans le prompt.
const INLINE_PLACEHOLDER_MAX = 38;
const STANDALONE_PLACEHOLDER_MAX = 80;

// Indications précises par emplacement connu de la lettre de référence : le rôle
// grammatical exact attendu (groupe nominal, phrase avec verbe conjugué, etc.) —
// un simple "reste court" ne suffit pas, l'IA produisait des fragments faux
// grammaticalement (ex: "parce que aider les cabinets dentaires" au lieu d'une
// vraie proposition). Clé = texte exact du placeholder dans le fichier de
// référence de l'utilisateur.
const PLACEHOLDER_HINTS = {
  "[Nom de l'entreprise]": "le nom exact de l'entreprise, rien d'autre.",
  "[Adresse]": "la rue et le numéro du siège (ex: \"Rue du Lac 4\"), chaîne vide si inconnu.",
  "[NPA, Ville]": "le code postal et la ville (ex: \"1400 Yverdon-les-Bains\"), chaîne vide si inconnu.",
  "[À adapter pour chaque entreprise]":
    "UNE PHRASE COMPLÈTE avec sujet et verbe conjugué (ex: \"J'ai vu votre offre et le poste correspond à ce que je cherche.\") — c'est un paragraphe entier à lui seul, elle doit se suffire.",
  "[secteur / domaine de l'entreprise]":
    "un GROUPE NOMINAL avec son article (ex: \"l'informatique dentaire\") — s'insère après \"au secteur de\", donc jamais une phrase, juste le groupe nominal complet.",
  "[ce qui t'intéresse dans ce domaine]":
    "UNE PROPOSITION AVEC SUJET + VERBE CONJUGUÉ (ex: \"j'aime comprendre comment les systèmes fonctionnent\") — s'insère après \"notamment parce que\", donc INTERDICTION d'un verbe à l'infinitif seul (\"parce que aider...\" est FAUX en français, il faut \"parce que ça aide...\" ou \"parce que j'aime aider...\").",
  "[projet / activité / type de travail / technologies / raison personnelle]":
    "un GROUPE NOMINAL ou un verbe à l'INFINITIF (ex: \"la maintenance des postes de travail\" ou \"installer et configurer du matériel\") — s'insère après \"pour\", jamais un verbe conjugué.",
  "[À adapter si nécessaire]":
    "UNE PHRASE COMPLÈTE avec sujet et verbe conjugué, courte, qui referme le paragraphe précédent.",
  "[domaine / technologie / type d'infrastructure]":
    "un GROUPE NOMINAL COMPLET AVEC SON ARTICLE (ex: \"l'infrastructure informatique dentaire\") — s'insère après \"lié à\", ne JAMAIS oublier l'article (\"lié à infrastructure\" est FAUX, il faut \"lié à l'infrastructure\").",
  "[élément spécifique à l'entreprise]":
    "un GROUPE NOMINAL complet avec son article (ex: \"votre système de facturation\") — s'insère après \"découvrir\".",
};

function placeholderHint(placeholder) {
  return (
    PLACEHOLDER_HINTS[placeholder] ||
    "une valeur courte, grammaticalement correcte et complète dans le contexte de la phrase où elle s'insère (bon article, bon accord, bon mode verbal)."
  );
}

// L'IA ignore parfois les consignes de grammaire (ex: répond par un infinitif
// seul après "parce que", ou omet l'article après "lié à"). Plutôt que de
// compter uniquement sur le prompt, on corrige ces erreurs connues au niveau
// du code — un filet de sécurité déterministe, comme pour la longueur.
const DETERMINER_OR_PRONOUN_RE =
  /^(le|la|l['’]|les|un|une|des|du|de la|de l['’]|votre|vos|mon|ma|mes|ce|cette|ces|cet|je|j['’]|ça|cela|c['’]|il|elle|on|nous|vous)\b/i;
const VOWEL_SOUND_RE = /^[aeiouhâàéèêëîïôöûü]/i;
const BARE_INFINITIVE_RE = /^[a-zàâäéèêëîïôöùûü]+(er|ir|re)$/i;

function fixGrammar(placeholder, value) {
  const v = (value || "").trim();
  if (!v) return v;

  // Groupe nominal attendu avec son article (ex: après "au secteur de", "lié à") :
  // ajoute l'article élidé "l'" si la valeur commence par une voyelle et n'a pas
  // déjà de déterminant (pas de règle fiable pour choisir "le"/"la" sans dico).
  if (
    (placeholder === "[secteur / domaine de l'entreprise]" ||
      placeholder === "[domaine / technologie / type d'infrastructure]") &&
    !DETERMINER_OR_PRONOUN_RE.test(v) &&
    VOWEL_SOUND_RE.test(v)
  ) {
    return `l'${v}`;
  }

  // Proposition attendue avec sujet + verbe conjugué (après "parce que") : si
  // l'IA a répondu par un verbe à l'infinitif seul ("aider les dentistes..."),
  // ça n'a aucun sens grammaticalement — on le transforme en phrase correcte.
  if (placeholder === "[ce qui t'intéresse dans ce domaine]" && !DETERMINER_OR_PRONOUN_RE.test(v)) {
    const firstWord = v.split(" ")[0] || "";
    if (BARE_INFINITIVE_RE.test(firstWord)) {
      return `j'aime ${v}`;
    }
  }

  return v;
}

// Mots qui ne peuvent jamais terminer une phrase en français (prépositions,
// déterminants, conjonctions...) : couper pile après l'un d'eux laisse une
// phrase bancale du genre "...correspond à mes." ou "...dentaires à.".
const DANGLING_END_WORDS = new Set([
  "à", "de", "du", "des", "au", "aux", "en", "sur", "dans", "pour", "avec", "sans", "chez",
  "par", "vers", "sous", "entre", "contre", "après", "avant", "depuis", "pendant", "selon",
  "et", "ou", "mais", "donc", "car", "ni", "or", "que", "qui", "comme", "si", "parce",
  "notamment", "le", "la", "les", "un", "une", "mon", "ma", "mes", "ton", "ta", "tes",
  "son", "sa", "ses", "notre", "nos", "votre", "vos", "leur", "leurs", "ce", "cet", "cette", "ces",
  "l'", "c'", "j'", "n'", "s'", "d'", "qu'",
]);

/** Retire les mots de fin qui ne peuvent grammaticalement pas conclure une phrase. */
function trimDanglingWords(text) {
  const words = text.trim().split(/\s+/);
  while (words.length > 1) {
    const last = words[words.length - 1].toLowerCase().replace(/[.,;:!?…]+$/, "");
    if (DANGLING_END_WORDS.has(last)) {
      words.pop();
    } else {
      break;
    }
  }
  return words.join(" ");
}

/** Coupe une valeur trop longue à la dernière limite de mot plutôt qu'en plein milieu,
 * puis retire tout mot de fin qui laisserait une phrase grammaticalement bancale. */
function truncateAtWord(value, maxLen) {
  const text = (value || "").trim();
  if (text.length <= maxLen) return trimDanglingWords(text);
  const cut = text.slice(0, maxLen);
  const lastSpace = cut.lastIndexOf(" ");
  const trimmed = lastSpace > maxLen * 0.5 ? cut.slice(0, lastSpace) : cut;
  return trimDanglingWords(trimmed.trim().replace(/[,;:\-–—]+$/, ""));
}

/**
 * Vérifie qu'un texte de longueur donnée se termine par une ponctuation de fin
 * de phrase (utile pour les emplacements qui forment un paragraphe entier).
 */
function ensureSentenceEnd(value) {
  if (!value) return value;
  return /[.!?…]$/.test(value) ? value : `${value}.`;
}

/**
 * Applique une limite stricte de longueur à chaque valeur de remplacement selon
 * qu'elle s'insère au milieu d'une phrase existante ou qu'elle forme, seule, un
 * paragraphe entier de la lettre de base (auquel cas on lui laisse plus de place
 * et on s'assure qu'elle se termine par une phrase complète).
 */
function capReplacementLengths(replacements, baseCoverLetter) {
  const lines = new Set((baseCoverLetter || "").split("\n").map((l) => l.trim()));
  const capped = {};
  for (const [placeholder, value] of Object.entries(replacements)) {
    const isStandalone = lines.has(placeholder);
    const maxLen = isStandalone ? STANDALONE_PLACEHOLDER_MAX : INLINE_PLACEHOLDER_MAX;
    const truncated = truncateAtWord(value, maxLen);
    capped[placeholder] = isStandalone ? ensureSentenceEnd(truncated) : truncated;
  }
  return capped;
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
   réorganisée. Voici exactement les emplacements entre crochets à remplir, chacun avec le rôle
   GRAMMATICAL PRÉCIS qu'il doit jouer dans la phrase où il se trouve (c'est très important : un
   emplacement inséré après "parce que" a besoin d'un sujet et d'un verbe conjugué, un emplacement
   inséré après "au secteur de" ou "lié à" a besoin d'un groupe nominal complet AVEC SON ARTICLE,
   etc. — ne mélange pas les rôles, sinon la phrase obtenue n'est plus du français correct) :
   ${placeholders.map((p) => `   - ${p} : ${placeholderHint(p)}`).join("\n")}
   Chaque valeur doit, une fois insérée à la place de son emplacement, former une phrase 100%
   correcte et naturelle en français — relis mentalement la phrase entière avec ta valeur insérée
   avant de répondre. La valeur ne doit contenir ni le crochet ouvrant "[" ni le crochet fermant
   "]". Si une information est vraiment introuvable pour un emplacement donné (ex: adresse
   inconnue), renvoie une chaîne vide pour cet emplacement plutôt que d'inventer.
   Ne produis PAS le texte complet de la lettre : uniquement le dictionnaire de remplacement
   demandé dans "champs" ci-dessous.
   Contraintes très importantes sur le CONTENU et le TON de chaque valeur :
   - La lettre finale doit tenir sur UNE SEULE PAGE A4, SANS EXCEPTION. La mise en page ne bouge
     pas, donc reste aussi concis que possible tout en restant grammaticalement correct et naturel
     (ce qui dépasse une longueur raisonnable sera de toute façon coupé automatiquement, donc mieux
     vaut une phrase courte et complète qu'une phrase longue qui sera tronquée en plein milieu) :
     - emplacement inséré au milieu d'une phrase (groupe nominal ou infinitif) : vise environ
       35 caractères, quelques mots, jamais plus d'une courte proposition ;
     - emplacement qui forme à lui seul un paragraphe entier : vise environ 75 caractères, une
       seule phrase courte mais grammaticalement complète.
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
   Rédige aussi, dans "sujet", un objet d'e-mail court et clair pour ce message (ex: "Candidature
   spontanée - [poste] - [prénom nom]"), sans le mot "Sujet" ni les deux-points dedans.
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
  "sujet": "objet court de l'e-mail, sans le mot Sujet ni les deux-points",
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
      coverLetterReplacements[p] = fixGrammar(p, (data.champs && data.champs[p]) || "");
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

    // Filet de sécurité : quoi que l'IA ait renvoyé, on garantit que la lettre
    // tienne sur une page en limitant strictement la longueur de chaque valeur.
    coverLetterReplacements = capReplacementLengths(coverLetterReplacements, baseCoverLetter);

    coverLetterText = applyReplacements(baseCoverLetter, coverLetterReplacements);
  } else {
    coverLetterText = data.cover_letter || "";
  }

  const subject = (data.sujet || `Candidature - ${companyName}`).trim();
  const messageText = data.message_text ? `Sujet : ${subject}\n\n${data.message_text}` : "";

  return {
    coverLetter: coverLetterText,
    coverLetterReplacements,
    cvModifiedText: data.cv_modifie || "",
    cvChangeSummary: data.cv_changement_resume || "",
    messageText,
    foundAddress: data.adresse_entreprise || "",
  };
}
