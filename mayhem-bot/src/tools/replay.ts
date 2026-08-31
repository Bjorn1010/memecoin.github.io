import { DatabaseSync } from "node:sqlite";
import { simulateBuy, simulateSell } from "../engine/amm.js";
import { PLATFORM_FEE_PCT } from "../solana/constants.js";

/**
 * Évaluateur hors-ligne de politiques de sortie.
 *
 * Pourquoi il existe : une fenêtre de trading live produit ~200 allers-retours en 50 minutes,
 * et l'intervalle de confiance à 90% sur ce n fait 6 à 22 points de large — assez pour que
 * toutes les variantes testées jusqu'ici se recoupent, donc pour qu'aucune comparaison ne
 * conclue. Le goulot n'est pas la finesse de la stratégie, c'est le débit d'évaluation.
 * Ce script rejoue les événements on-chain déjà en base : ~4400 entrées éligibles, en quelques
 * secondes, autant de fois qu'on veut.
 *
 * LIMITE À CONNAÎTRE, elle est structurelle : le chemin de prix est échantillonné uniquement
 * aux transactions de Mayhem sur ce mint (médiane ~103 observations après l'entrée), alors que
 * le bot live reçoit toutes les mises à jour de la courbe. Les sorties se déclenchent donc plus
 * tard ici qu'en réel, et les niveaux réalisés sont pessimistes. Ce biais s'applique à
 * l'identique à toutes les politiques comparées, donc il fausse les niveaux absolus mais pas
 * le classement — c'est un comparateur, pas un prédicteur de PnL.
 *
 * BIAIS D'OPTIMISME, mesuré : le replay rend +0.5% à +3.0% là où les mêmes politiques rendent
 * -5% à -10% en live. L'écart n'est pas du bruit, il est structurel et va toujours dans ce sens.
 * En live, 66% à 73% des sorties partent en `stop_loss` à un hold médian d'UNE seconde, sur des
 * creux intra-seconde ; le chemin échantillonné ici ne les voit pas, donc il ne les déclenche
 * pas. **Un chiffre positif sorti de ce script ne veut pas dire « rentable ».** L'outil classe
 * des politiques sur des effets lents ; il ne prédit pas le PnL live et ne remplace pas une
 * fenêtre réelle.
 *
 * Le remplissage réutilise `simulateBuy`/`simulateSell` et `PLATFORM_FEE_PCT` du moteur réel :
 * réimplémenter la comptabilité ici reviendrait à comparer deux modèles différents.
 *
 * Usage : npx tsx src/tools/replay.ts [chemin/vers/db]
 */

interface Policy {
  name: string;
  stopLossPct: number | null;
  stopLossGraceSeconds: number | null;
  trailingStopPct: number | null;
  trailingArmPct: number | null;
  maxHoldSeconds: number | null;
  sellOnMayhemFullExit: boolean;
}

const POSITION_SOL = 0.15;
const PRIORITY_FEE = 0.000025;
const MIN_POOL_SOL = 40;

interface Ev {
  mint: string;
  kind: string;
  priceSol: number;
  solRes: number | null;
  tokRes: number | null;
  at: number;
  balAfter: number;
}

interface Trip {
  ret: number;
  cost: number;
  proceeds: number;
  reason: string;
  holdS: number;
}

function runPolicy(p: Policy, byMint: Map<string, Ev[]>): { trips: Trip[]; forced: number } {
  const trips: Trip[] = [];
  let forced = 0;
  for (const evs of byMint.values()) {
    for (let i = 0; i < evs.length; i++) {
      const e = evs[i];
      if (e.kind !== "buy") continue;
      if (e.solRes == null || e.tokRes == null || e.solRes < MIN_POOL_SOL) continue;

      const feeIn = POSITION_SOL * PLATFORM_FEE_PCT;
      const notional = POSITION_SOL - feeIn;
      const buy = simulateBuy(notional, e.solRes, e.tokRes);
      if (!(buy.avgPriceSol > 0)) continue;
      const tokens = notional / buy.avgPriceSol;
      const cost = POSITION_SOL + PRIORITY_FEE;

      let peak = buy.avgPriceSol;
      let exit: { price: number; res: Ev; reason: string } | null = null;

      for (let j = i + 1; j < evs.length; j++) {
        const q = evs[j];
        if (!(q.priceSol > 0)) continue;
        const heldS = (q.at - e.at) / 1000;
        peak = Math.max(peak, q.priceSol);
        const change = (q.priceSol - buy.avgPriceSol) / buy.avgPriceSol;
        const ddFromPeak = (q.priceSol - peak) / peak;
        const peakGain = (peak - buy.avgPriceSol) / buy.avgPriceSol;
        const stopArmed =
          p.stopLossGraceSeconds == null || heldS >= p.stopLossGraceSeconds;

        let reason: string | null = null;
        if (stopArmed && p.stopLossPct != null && change <= -p.stopLossPct) reason = "stop_loss";
        else if (
          p.trailingStopPct != null &&
          ddFromPeak <= -p.trailingStopPct &&
          peakGain >= (p.trailingArmPct ?? 0)
        )
          reason = "trailing_stop";
        // `full_exit` est un KIND d'evenement a part entiere en base (6267 occurrences), pas
        // un `sell` a solde nul : le solde residuel n'est jamais exactement zero (minimum
        // observe 0.648 token de poussiere), c'est txParser qui applique le seuil DUST_UI_AMOUNT
        // au moment de l'ecriture. Tester `kind === "sell" && balAfter <= 0` ne se declenchait
        // donc jamais, et les deux politiques qui ne different que par ce drapeau rendaient des
        // resultats rigoureusement identiques — le symptome qui a permis de trouver le bug.
        else if (p.sellOnMayhemFullExit && q.kind === "full_exit") reason = "mayhem_full_exit";
        else if (p.maxHoldSeconds != null && heldS >= p.maxHoldSeconds) reason = "max_hold_time";

        if (reason) {
          exit = { price: q.priceSol, res: q, reason };
          break;
        }
      }
      // BIAIS DE SURVIE — le piege central de ce replay. Une position qui n'atteint aucun
      // seuil avant la fin du chemin disponible n'est PAS neutre : un token mort cesse
      // d'etre trade par Mayhem, donc il n'a plus d'observations, donc il ne peut plus
      // declencher de sortie. Les jeter revient a jeter les pires perdants. Sans ce
      // correctif la politique "sans stop" affichait +46.29% en abandonnant 47% de ses
      // positions en cours de route. On les clot donc de force a la derniere observation,
      // exactement comme le fait maxHoldSeconds en live.
      if (!exit) {
        forced++;
        for (let j = evs.length - 1; j > i; j--) {
          if (evs[j].priceSol > 0) {
            exit = { price: evs[j].priceSol, res: evs[j], reason: "fin_de_donnees" };
            break;
          }
        }
      }
      if (!exit) continue;

      let fill =
        exit.res.solRes != null && exit.res.tokRes != null
          ? simulateSell(tokens, exit.res.solRes, exit.res.tokRes)
          : { avgPriceSol: exit.price, slippagePct: 0 };
      if (!(fill.avgPriceSol > 0) && exit.price > 0)
        fill = { avgPriceSol: exit.price, slippagePct: 0 };
      if (!(fill.avgPriceSol > 0)) continue;

      const gross = tokens * fill.avgPriceSol;
      const proceeds = gross - gross * PLATFORM_FEE_PCT - PRIORITY_FEE;
      trips.push({
        ret: (proceeds / cost - 1) * 100,
        cost,
        proceeds,
        reason: exit.reason,
        holdS: (exit.res.at - e.at) / 1000,
      });
    }
  }
  return { trips, forced };
}

function median(xs: number[]): number {
  const s = [...xs].sort((a, b) => a - b);
  return s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2;
}

/** IC 90% par bootstrap sur le rendement pondéré — c'est lui qui dit si un écart veut dire
 * quelque chose. Sans cet intervalle, deux politiques séparées de 3 points paraissent
 * différentes alors qu'elles ne le sont pas. */
function bootstrapCI(trips: Trip[], draws = 2000): [number, number] {
  const rs: number[] = [];
  // mulberry32 : arithmetique 32 bits exacte via Math.imul. Un LCG naif ecrit en flottant
  // JS (seed * 1103515245) depasse 2^53 des le premier tour et perd ses bits de poids
  // faible : la suite cesse d'etre aleatoire et l'intervalle produit ne contenait meme pas
  // l'estimation ponctuelle. Symptome a retenir — un IC qui n'encadre pas son point est
  // toujours un bug de generateur, jamais un resultat.
  let seed = 12345 >>> 0;
  const rnd = () => {
    seed = (seed + 0x6d2b79f5) >>> 0;
    let t = seed;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  for (let d = 0; d < draws; d++) {
    let c = 0;
    let p = 0;
    for (let k = 0; k < trips.length; k++) {
      const t = trips[(rnd() * trips.length) | 0];
      c += t.cost;
      p += t.proceeds;
    }
    rs.push((p / c - 1) * 100);
  }
  rs.sort((a, b) => a - b);
  return [rs[(draws * 0.05) | 0], rs[(draws * 0.95) | 0]];
}

function main() {
  const dbPath = process.argv[2] ?? "data/mayhem-bot.db";
  const db = new DatabaseSync(dbPath, { readOnly: true });
  const rows = db
    .prepare(
      `select mint, kind, price_sol, sol_reserves_ui, token_reserves_ui,
              detected_at_ms, wallet_token_balance_after
         from mayhem_events where price_sol > 0 order by detected_at_ms asc`,
    )
    .all() as Record<string, number | string>[];

  const byMint = new Map<string, Ev[]>();
  for (const r of rows) {
    const e: Ev = {
      mint: r.mint as string,
      kind: r.kind as string,
      priceSol: r.price_sol as number,
      solRes: (r.sol_reserves_ui as number) ?? null,
      tokRes: (r.token_reserves_ui as number) ?? null,
      at: r.detected_at_ms as number,
      balAfter: r.wallet_token_balance_after as number,
    };
    const cur = byMint.get(e.mint);
    if (cur) cur.push(e);
    else byMint.set(e.mint, [e]);
  }
  console.log(`${rows.length} événements, ${byMint.size} mints\n`);

  const BASE = {
    trailingStopPct: 0.25,
    trailingArmPct: 0.5,
    maxHoldSeconds: 600,
    sellOnMayhemFullExit: true,
  };
  const policies: Policy[] = [
    { name: "reference (stop immediat)", stopLossPct: 0.12, stopLossGraceSeconds: null, ...BASE },
    { name: "grace 20s", stopLossPct: 0.12, stopLossGraceSeconds: 20, ...BASE },
    { name: "grace 60s", stopLossPct: 0.12, stopLossGraceSeconds: 60, ...BASE },
    { name: "grace 60s nofollow", stopLossPct: 0.12, stopLossGraceSeconds: 60, ...BASE, sellOnMayhemFullExit: false },
    { name: "sans stop", stopLossPct: null, stopLossGraceSeconds: null, ...BASE },
    { name: "trail arme a +20%", stopLossPct: 0.12, stopLossGraceSeconds: null, ...BASE, trailingArmPct: 0.2 },
    { name: "trail serre -15%", stopLossPct: 0.12, stopLossGraceSeconds: null, ...BASE, trailingStopPct: 0.15 },
  ];

  console.log(
    "politique".padEnd(26) +
      "n".padStart(6) +
      "rend.pond".padStart(11) +
      "IC 90%".padStart(22) +
      "mediane".padStart(10) +
      ">+100%".padStart(9) +
      "forcees".padStart(9),
  );
  for (const p of policies) {
    const { trips: t, forced } = runPolicy(p, byMint);
    if (t.length < 30) {
      console.log(p.name.padEnd(26) + String(t.length).padStart(6) + "   (trop peu)");
      continue;
    }
    const C = t.reduce((a, x) => a + x.cost, 0);
    const P = t.reduce((a, x) => a + x.proceeds, 0);
    const wr = (P / C - 1) * 100;
    const [lo, hi] = bootstrapCI(t);
    const tail = t.filter((x) => x.ret > 100).length;
    console.log(
      p.name.padEnd(26) +
        String(t.length).padStart(6) +
        `${wr.toFixed(2)}%`.padStart(11) +
        `[${lo.toFixed(1)} , ${hi.toFixed(1)}]`.padStart(22) +
        `${median(t.map((x) => x.ret)).toFixed(2)}%`.padStart(10) +
        `${((tail / t.length) * 100).toFixed(1)}%`.padStart(9) +
        `${((forced / t.length) * 100).toFixed(1)}%`.padStart(9),
    );
  }
}

main();
