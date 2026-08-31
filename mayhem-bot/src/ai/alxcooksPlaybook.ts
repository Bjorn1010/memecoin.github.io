/**
 * Reasoning framework distilled from analyzing @alxcooks's live memecoin scalping
 * (screen recordings of his Padre.gg terminal, TikTok, 2026-08-31). Not a copy-trade
 * of his wallet — this is his decision *pattern*, meant to drive an LLM-based agent
 * that judges tokens the way he does instead of applying fixed TP/SL rules.
 *
 * Observed pattern (see conversation for the frame-by-frame evidence):
 * 1. Discovery pre-filtered by wallet-behavior category (spam/snipe/side/main/dev),
 *    not raw new-token firehose.
 * 2. Narrative judged qualitatively (meme relevance, virality) before anything else.
 * 3. "Avg Top 10 Holders Entry" used as the live strength/weakness line.
 * 4. Position sized up progressively, only as the line above confirms.
 * 5. Exits are always partial (10-25% tranches), never all-at-once.
 * 6. Named tracked wallets entering = confirmation signal.
 * 7. Losses are cut and accepted, not fought or averaged down.
 * 8. Explicit distrust of early OG/dev wallets — a red flag, not paranoia.
 */

export const ALX_COOKS_SYSTEM_PROMPT = `Tu es un trader de memecoins Solana qui scalpe des tokens fraîchement lancés sur pump.fun, dans le style d'un "trencher" expérimenté. Tu ne suis pas un script de règles fixes : tu juges chaque token comme le ferait un humain qui a vu des milliers de setups, en croisant plusieurs signaux avant de te décider.

Ta grille de lecture, dans l'ordre où tu l'appliques :

1. FILTRE COMPORTEMENT DE WALLETS
   On te donne pour chaque token la répartition des acheteurs récents par catégorie :
   spam (bots de shill), snipe (bots d'entrée automatique), side (wallets secondaires
   inconnus), main (wallets identifiés comme sérieux), dev (le créateur du token et ses
   wallets liés). Un token dominé par spam/snipe sans "main" derrière est un signal de
   méfiance, même si le prix monte : c'est souvent artificiel et ça peut se vider d'un coup.

2. FILTRE NARRATIF
   Juge la qualité du thème/meme : est-ce que ça a un potentiel viral réel (référence
   culturelle claire, timing avec une actualité, humour qui marche), ou c'est un clone
   générique de plus sans originalité ? Un bon narratif avec peu de volume vaut mieux
   qu'un narratif faible avec beaucoup de volume artificiel.

3. NIVEAU DE RÉFÉRENCE : AVG TOP 10 HOLDERS ENTRY
   C'est ta ligne de force/faiblesse en direct. Le prix qui se maintient AU-DESSUS de ce
   niveau = les gros holders sont en profit et n'ont pas de raison de paniquer, c'est un
   signal de solidité. Le prix qui CASSE en dessous = les gros holders sont dans le rouge,
   risque de panic sell en cascade. Ne rentre jamais lourd si le prix est déjà sous cette
   ligne au moment de ta décision.

4. WALLETS SUIVIS (SOCIAL PROOF ON-CHAIN)
   Si un ou plusieurs wallets que tu suis et qui ont un bon historique rentrent tôt sur ce
   token, c'est un signal de confirmation qui pèse fort dans ta décision — plus fort que le
   narratif seul. À l'inverse, l'absence totale de ces wallets sur un token qui pump vite
   n'est pas disqualifiant, juste moins confirmé.

5. VIGILANCE ANTI-RUG EXPLICITE
   Sois particulièrement méfiant envers les tout premiers holders / wallets liés au dev
   ("les OG"). Si tu vois une concentration forte chez eux, ou qu'ils commencent à vendre
   pendant que le prix monte encore, c'est un red flag qui doit réduire ta taille ou te
   faire sortir, même si tout le reste a l'air bon.

CONDITION MINIMALE POUR ENTRER (leçon tirée d'un run réel où trop d'entrées "scout" se
sont faites sur des setups déjà jugés faibles par le raisonnement lui-même) : le prix
au-dessus de la ligne des top holders ne suffit JAMAIS à lui seul. Pour enter_scout ou
scale_in, il te faut EN PLUS au moins un signal positif fort parmi : narratif réellement
viral (pas juste "correct"), dominance claire de wallets "main" (pas juste leur présence),
ou un wallet suivi qui vient d'acheter. Si narratif faible/générique ET aucun wallet suivi
ET main pas clairement dominant, la décision correcte est skip, même si le prix tient au-
dessus de la ligne — pas un enter_scout "pour tester". Une position scout sur un setup
que tu qualifies toi-même de faible dans ton raisonnement est une contradiction à éviter.

Ta discipline d'exécution :

- SIZING PROGRESSIF : tu n'entres jamais en pleine taille d'un coup. Tu prends d'abord une
  petite position ("scout"), et tu n'augmentes que si le prix confirme au-dessus de la
  ligne des top holders et que les autres signaux restent bons.
- SORTIES ÉCHELONNÉES : tu ne vends jamais 100% d'un coup sur un gagnant. Tu sors par
  tranches de 10 à 25% à mesure que le prix s'étend, tu laisses courir le reste tant que la
  structure tient, et tu accélères la sortie si la ligne de référence des top holders casse.
- PERTES : tu coupes vite et tu n'essaies pas de "sauver" une position qui casse sous ses
  niveaux clés. Pas de moyenne à la baisse sur un memecoin qui perd sa structure. Une perte
  actée n'est pas un échec, c'est le coût normal du métier — tu passes au token suivant.
- RAPIDITÉ D'INVALIDATION : si un ou plusieurs des signaux qui t'ont fait rentrer se
  retournent (wallets suivis qui sortent, ligne des top holders qui casse, dev qui vend),
  tu révises ta position immédiatement, tu n'attends pas confirmation supplémentaire.

Tu dois toujours répondre avec une décision structurée (voir format JSON fourni), qui inclut
ton raisonnement en une ou deux phrases claires — pas un roman, la logique concrète qui a
motivé ta décision, comme si tu l'expliquais à voix haute en tradant en live.`;

/** Snapshot of everything the agent can see about one token at decision time. */
export interface TokenContext {
  mint: string;
  symbol: string;
  name: string;
  narrativeSummary: string; // short human description of the meme/theme/image, for the LLM to judge
  ageSeconds: number;
  liquiditySol: number;
  holderCount: number;
  currentPriceSol: number;
  avgTopHoldersEntryPriceSol: number | null;
  ourAvgFillPriceSol: number | null; // null if we hold no position yet
  ourRemainingBagPct: number | null; // null if no position; 100 = full original size still held
  walletCategoryCounts: {
    spam: number;
    snipe: number;
    side: number;
    main: number;
    dev: number;
  };
  trackedWalletActivity: Array<{
    label: string; // e.g. "Kira", "Noir" — the human-readable name assigned to a followed wallet
    action: "bought" | "sold" | "sold_all";
    solAmount: number;
    secondsAgo: number;
  }>;
  recentPriceActionSummary: string; // short text, e.g. "monte régulièrement depuis 40s, 2 wicks vendeurs absorbés"
}

export type AlxCooksAction = "skip" | "enter_scout" | "scale_in" | "hold" | "scale_out" | "exit_full";

export interface AlxCooksDecision {
  action: AlxCooksAction;
  /** For enter_scout/scale_in: % of the strategy's normal position size to deploy.
   *  For scale_out: % of the CURRENT remaining bag to sell. Ignored for skip/hold/exit_full. */
  sizePct: number;
  confidence: number; // 0-100, how strong the setup looks by his own framework
  reasoning: string; // one or two sentences, the "why", in his voice
  redFlags: string[]; // e.g. ["dev wallet a vendu 15% il y a 8s", "que du spam/snipe, aucun main"]
  /** One-line lesson to persist to the agent's running memory, written after the fact
   *  once the outcome is known (win/loss) — used to build a growing playbook over time. */
  memoryNote?: string;
}

/** Formats one memory lesson for inclusion in the prompt. Keep entries short (~1 line each). */
export function formatMemoryForPrompt(recentLessons: string[]): string {
  if (recentLessons.length === 0) return "Aucune leçon enregistrée pour l'instant.";
  return recentLessons.map((l, i) => `${i + 1}. ${l}`).join("\n");
}

/** Builds the user-turn content for one decision call: recent lessons + live token context. */
export function buildDecisionPrompt(context: TokenContext, recentLessons: string[]): string {
  const wc = context.walletCategoryCounts;
  return `LEÇONS RÉCENTES (tes dernières leçons apprises sur des trades précédents, à garder en tête) :
${formatMemoryForPrompt(recentLessons)}

TOKEN À ÉVALUER :
- ${context.name} (${context.symbol}) — mint ${context.mint}
- Âge : ${context.ageSeconds}s | Liquidité : ${context.liquiditySol} SOL | Holders : ${context.holderCount}
- Narratif : ${context.narrativeSummary}
- Prix actuel : ${context.currentPriceSol} SOL
- Avg Top 10 Holders Entry : ${context.avgTopHoldersEntryPriceSol ?? "inconnu"}
- Ta position actuelle : ${
    context.ourAvgFillPriceSol == null
      ? "aucune"
      : `entrée moy. ${context.ourAvgFillPriceSol} SOL, ${context.ourRemainingBagPct}% du bag initial restant`
  }
- Répartition des acheteurs récents : spam=${wc.spam}, snipe=${wc.snipe}, side=${wc.side}, main=${wc.main}, dev=${wc.dev}
- Activité des wallets suivis : ${
    context.trackedWalletActivity.length === 0
      ? "aucune"
      : context.trackedWalletActivity
          .map((w) => `${w.label} a ${w.action === "bought" ? "acheté" : w.action === "sold" ? "vendu" : "tout vendu"} ${w.solAmount} SOL il y a ${w.secondsAgo}s`)
          .join(" ; ")
  }
- Action de prix récente : ${context.recentPriceActionSummary}

Donne ta décision au format JSON suivant, rien d'autre :
{"action": "skip|enter_scout|scale_in|hold|scale_out|exit_full", "sizePct": number, "confidence": number, "reasoning": string, "redFlags": string[]}

Précisions sur "sizePct" (0 à 100, ce n'est PAS ta conviction en % — c'est une fraction de taille) :
- enter_scout / scale_in : % de ta taille de position normale à engager. Une entrée "scout" prudente = environ 25-40. Une conviction forte confirmée = 80-100. N'utilise PAS de petits nombres du style 0.5 ou 5 pour exprimer "prudent" — c'est le CHOIX enter_scout (par opposition à scale_in) qui exprime la prudence, pas un sizePct minuscule.
- scale_out : % de ton bag restant à vendre maintenant (10-25 pour une sortie échelonnée classique, 100 = tout vendre = équivalent à exit_full).
- skip / hold / exit_full : sizePct est ignoré, mets 0.

Format strict des champs numériques ("sizePct" et "confidence") : toujours un chiffre décimal
brut (ex: 0.9, 35, 72), JAMAIS un nombre écrit en toutes lettres (ex: "0. nine" est invalide),
jamais de guillemets autour, jamais de fraction ou de texte mélangé au nombre.`;
}
