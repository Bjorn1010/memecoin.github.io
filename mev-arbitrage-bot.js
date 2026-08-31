#!/usr/bin/env node
/**
 * Bot d'arbitrage MEV — Solana
 * ============================
 *
 * Surveille deux pools AMM (courbe à produit constant x*y=k, le même modèle que
 * Raydium/Orca "legacy" ou la bonding curve pump.fun) qui cotent la même paire de
 * jetons, et détecte les écarts de prix exploitables entre les deux : acheter sur
 * le pool le moins cher, revendre sur le pool le plus cher, empocher la différence
 * une fois les frais de pool et le gas estimé déduits.
 *
 * Par défaut le bot tourne en PAPER TRADING (aucune transaction réelle, tout est
 * simulé et juste loggé). Pour passer en argent réel il faut explicitement activer
 * LIVE_TRADING=true + CONFIRM_LIVE_TRADING="oui" et fournir une clé privée — voir
 * la fonction `executerEnDirect` plus bas, volontairement non câblée par défaut.
 *
 * Installation :
 *   npm init -y
 *   npm install @solana/web3.js dotenv
 *   node mev-arbitrage-bot.js
 *
 * Configuration : variables d'environnement (ou un fichier .env à côté du script) —
 * voir le bloc CONFIG ci-dessous pour la liste complète et leurs valeurs par défaut.
 *
 * ⚠️ Ce script ne fait que de l'arbitrage pur (acheter bas / revendre haut entre deux
 * pools publics). Il ne fait ni sandwich ni front-running d'une transaction précise
 * d'un autre utilisateur — ce sont des pratiques différentes, plus agressives, que ce
 * script n'implémente pas.
 * ⚠️ L'exécution "live" ci-dessous fait DEUX swaps séquentiels (pas atomique via
 * flashloan) : entre les deux, le prix peut bouger ou le deuxième swap peut échouer.
 * Ne risque que ce que tu es prêt à perdre, et teste longtemps en paper trading avant.
 */

import "dotenv/config";
import fs from "node:fs";
import { Connection, PublicKey } from "@solana/web3.js";

// ─────────────────────────────────────────────────────────────────────────────
// CONFIG
// ─────────────────────────────────────────────────────────────────────────────

const CONFIG = {
  rpcUrl: process.env.RPC_HTTP_URL ?? "https://api.mainnet-beta.solana.com",
  intervalMs: Number(process.env.POLL_INTERVAL_MS ?? 2000),

  // Frais du pool en points de base (30 = 0.30%, standard Raydium/Orca legacy).
  fraisPoolBps: Number(process.env.POOL_FEE_BPS ?? 30),

  // Profit minimum (net des frais de pool, avant gas) pour logguer une opportunité.
  profitMinSol: Number(process.env.MIN_PROFIT_SOL ?? 0.002),
  // Coût gas/priority-fee estimé pour les 2 swaps, déduit du profit avant décision finale.
  gasEstimeSol: Number(process.env.EST_GAS_COST_SOL ?? 0.001),
  // Taille max d'un trade, quoi que dise le calcul de taille optimale (garde-fou).
  tailleMaxSol: Number(process.env.MAX_TRADE_SIZE_SOL ?? 1),

  // Paper trading par défaut. Ne PAS activer sans avoir lu les avertissements du header.
  liveTrading: process.env.LIVE_TRADING === "true",
  confirmationLive: process.env.CONFIRM_LIVE_TRADING ?? "",

  fichierLog: "./trades.jsonl",

  // Les deux pools à surveiller : deux vaults SPL (comptes de tokens) par pool, qui
  // représentent les réserves x/y de la courbe x*y=k. Remplace ces adresses par les
  // vrais comptes de la paire que tu veux arbitrer (ex : SOL/USDC sur Raydium vs
  // Orca) — trouvables via l'explorateur Solscan, l'API Raydium ou Orca. Les valeurs
  // ci-dessous sont des PLACEHOLDERS et ne fonctionneront pas telles quelles.
  pools: [
    {
      nom: "Pool A (ex: Raydium SOL/USDC)",
      vaultBase: "REMPLACE_PAR_LE_VAULT_SOL_DU_POOL_A",
      vaultQuote: "REMPLACE_PAR_LE_VAULT_USDC_DU_POOL_A",
      decimalsBase: 9,
      decimalsQuote: 6,
    },
    {
      nom: "Pool B (ex: Orca SOL/USDC)",
      vaultBase: "REMPLACE_PAR_LE_VAULT_SOL_DU_POOL_B",
      vaultQuote: "REMPLACE_PAR_LE_VAULT_USDC_DU_POOL_B",
      decimalsBase: 9,
      decimalsQuote: 6,
    },
  ],
};

const connection = new Connection(CONFIG.rpcUrl, "confirmed");

// ─────────────────────────────────────────────────────────────────────────────
// MATH AMM — courbe à produit constant x*y=k
// ─────────────────────────────────────────────────────────────────────────────

/** Montant de sortie pour `montantIn` envoyé dans un pool (reserveIn, reserveOut), frais inclus. */
function swapOut(montantIn, reserveIn, reserveOut, fraisBps) {
  if (montantIn <= 0 || reserveIn <= 0 || reserveOut <= 0) return 0;
  const montantInNet = montantIn * (1 - fraisBps / 10_000);
  const k = reserveIn * reserveOut;
  return reserveOut - k / (reserveIn + montantInNet);
}

/**
 * Profit (en jeton "base", ex SOL) d'un cycle : acheter le jeton "quote" sur poolAchat
 * avec `montantIn` base, puis revendre tout le quote obtenu sur poolVente contre du base.
 */
function profitCycle(montantIn, poolAchat, poolVente, fraisBps) {
  const quoteObtenu = swapOut(montantIn, poolAchat.reserveBase, poolAchat.reserveQuote, fraisBps);
  const baseRecu = swapOut(quoteObtenu, poolVente.reserveQuote, poolVente.reserveBase, fraisBps);
  return baseRecu - montantIn;
}

/**
 * Cherche la taille d'entrée qui maximise le profit du cycle par recherche ternaire.
 * La fonction profit(montantIn) est concave (un seul maximum) pour une courbe x*y=k,
 * donc la recherche ternaire converge de façon fiable vers l'optimum.
 */
function trouverTailleOptimale(poolAchat, poolVente, fraisBps, maxIn) {
  let lo = 0;
  let hi = maxIn;
  for (let i = 0; i < 100; i++) {
    const m1 = lo + (hi - lo) / 3;
    const m2 = hi - (hi - lo) / 3;
    if (profitCycle(m1, poolAchat, poolVente, fraisBps) < profitCycle(m2, poolAchat, poolVente, fraisBps)) {
      lo = m1;
    } else {
      hi = m2;
    }
  }
  const montant = (lo + hi) / 2;
  return { montant, profit: profitCycle(montant, poolAchat, poolVente, fraisBps) };
}

// ─────────────────────────────────────────────────────────────────────────────
// LECTURE DES POOLS ON-CHAIN
// ─────────────────────────────────────────────────────────────────────────────

/** Lit les réserves réelles d'un pool en interrogeant les soldes de ses deux vaults SPL. */
async function lireReserves(pool) {
  const [solBase, solQuote] = await Promise.all([
    connection.getTokenAccountBalance(new PublicKey(pool.vaultBase)),
    connection.getTokenAccountBalance(new PublicKey(pool.vaultQuote)),
  ]);
  return {
    ...pool,
    reserveBase: Number(solBase.value.amount) / 10 ** pool.decimalsBase,
    reserveQuote: Number(solQuote.value.amount) / 10 ** pool.decimalsQuote,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// EXÉCUTION
// ─────────────────────────────────────────────────────────────────────────────

function loggerTrade(opportunite) {
  const ligne = JSON.stringify({ horodatage: new Date().toISOString(), ...opportunite });
  fs.appendFileSync(CONFIG.fichierLog, ligne + "\n");
}

/** Mode par défaut : ne fait rien de réel, log juste ce que le bot aurait tenté. */
function executerEnPaperTrading(opportunite) {
  console.log(
    `[PAPER] ${opportunite.achatSur} → ${opportunite.venteSur} | ` +
      `taille=${opportunite.taille.toFixed(4)} | profit net estimé=${opportunite.profitNet.toFixed(6)}`,
  );
  loggerTrade({ mode: "paper", ...opportunite });
}

/**
 * Squelette d'exécution réelle — volontairement non implémenté en détail.
 * Pour l'activer il faudrait : charger une paire de clés depuis PRIVATE_KEY,
 * construire/signer les 2 transactions de swap (via l'API Jupiter ou le SDK du DEX
 * concerné), les envoyer, et vérifier la confirmation de chaque étape avant de
 * lancer la suivante. Reste bloqué tant que LIVE_TRADING n'est pas explicitement activé.
 */
async function executerEnDirect(opportunite) {
  if (!CONFIG.liveTrading || CONFIG.confirmationLive !== "oui") {
    console.log("[LIVE] Ignoré : LIVE_TRADING=true et CONFIRM_LIVE_TRADING=\"oui\" sont requis tous les deux.");
    return;
  }
  throw new Error(
    "Exécution live non implémentée : branche ici tes swaps signés (ex. API Jupiter) " +
      "après avoir testé la détection en paper trading.",
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// BOUCLE PRINCIPALE
// ─────────────────────────────────────────────────────────────────────────────

async function scanUneFois() {
  const [poolA, poolB] = await Promise.all(CONFIG.pools.map(lireReserves));

  const maxIn = Math.min(poolA.reserveBase, poolB.reserveBase, CONFIG.tailleMaxSol);

  // On teste les deux sens : acheter sur A/vendre sur B, puis l'inverse.
  const candidats = [
    { achatSur: poolA.nom, venteSur: poolB.nom, ...trouverTailleOptimale(poolA, poolB, CONFIG.fraisPoolBps, maxIn) },
    { achatSur: poolB.nom, venteSur: poolA.nom, ...trouverTailleOptimale(poolB, poolA, CONFIG.fraisPoolBps, maxIn) },
  ];

  const meilleur = candidats.sort((a, b) => b.profit - a.profit)[0];
  const profitNet = meilleur.profit - CONFIG.gasEstimeSol;

  if (meilleur.profit >= CONFIG.profitMinSol && profitNet > 0) {
    const opportunite = { ...meilleur, taille: meilleur.montant, profitNet };
    if (CONFIG.liveTrading) {
      await executerEnDirect(opportunite);
    } else {
      executerEnPaperTrading(opportunite);
    }
  } else {
    console.log(
      `[SCAN] pas d'opportunité rentable (meilleur profit brut=${meilleur.profit.toFixed(6)} SOL)`,
    );
  }
}

async function main() {
  console.log("Bot d'arbitrage MEV démarré.");
  console.log(`Mode : ${CONFIG.liveTrading ? "LIVE (argent réel)" : "PAPER TRADING (simulation)"}`);
  console.log(`Pools surveillés : ${CONFIG.pools.map((p) => p.nom).join(" | ")}`);

  setInterval(() => {
    scanUneFois().catch((err) => console.error("[ERREUR scan]", err.message));
  }, CONFIG.intervalMs);
}

main();
