# Mayhem Bot

Bot de paper trading (100% simulé, aucune vraie transaction) qui suit en temps réel les
wallets de l'agent **Mayhem Mode** de pump.fun et copie ses achats/ventes selon plusieurs
stratégies configurables, avec un panel de contrôle en direct (PNL, positions, activité
on-chain, log des trades du bot).

## Comment ça marche

- `src/solana/mayhemMonitor.ts` s'abonne en websocket aux logs des wallets Mayhem
  (`MAYHEM_WALLETS` dans `.env`) et détecte chaque swap en quasi temps réel.
- `src/solana/txParser.ts` classe chaque transaction en `buy`, `sell`, ou `full_exit`
  (le wallet vide entièrement sa position sur un coin — ton "vault dump").
- `src/solana/bondingCurve.ts` lit le prix directement depuis le compte on-chain de la
  bonding curve pump.fun (pas d'appel API tiers = latence minimale) ; `dexscreener.ts` sert
  de repli une fois le coin migré vers un DEX.
- `src/engine/` contient le moteur de paper trading : chaque stratégie a son propre
  portefeuille virtuel, achète/vend selon ses règles (take-profit, stop-loss, trailing
  stop, durée max, copie du dump de Mayhem), le tout persisté en SQLite (`data/mayhem-bot.db`).
- `src/api/server.ts` expose une API REST + un flux WebSocket pour le dashboard.
- `web/` est le panel — React + Tailwind + Recharts, mises à jour en direct par WebSocket.

Wallets suivis par défaut (voir `.env.example`) :
- `BwWK17cbHxwWBKZkUYvzxLcNQ1YVyaFezduWbtm2de6s` — adresse officiellement documentée par pump.fun
- `Gygj9QQby4j2jryqyqBHvLP7ctv2SaANgh4sCb69BUpA` — wallet très actif observé on-chain (financé
  par le compte de frais Pump.fun, des centaines de buy/sell), probable second wallet d'exécution

## Installation

```bash
cd mayhem-bot
npm install
npm --prefix web install
copy .env.example .env
```

Le `.env` par défaut utilise le RPC public Solana (gratuit mais rate-limité). Pour de
meilleures performances, remplace `RPC_HTTP_URL` / `RPC_WS_URL` par une clé Helius/QuickNode
gratuite — aucun changement de code nécessaire.

## Lancer le bot + le panel

```bash
npm run dev
```

Ça démarre le backend (surveillance + moteur de stratégies + API) sur `http://localhost:8787`
et le panel sur `http://localhost:5173`. Ouvre `http://localhost:5173` dans ton navigateur.

## Stratégies par défaut

Quatre stratégies tournent en parallèle dès le démarrage (`src/engine/presets.ts`), chacune
avec son propre solde virtuel de 10 SOL — pour comparer plusieurs approches en même temps :

1. **Copy All — Fast Scalp** : copie tous les achats de Mayhem, TP +25% / SL -15%, sort après 10 min max.
2. **Filtered — Big Buys Only** : ignore les petits achats de Mayhem, TP +50% / SL -20% / trailing -15%.
3. **Trailing Stop — Let Winners Run** : pas de TP fixe, trailing stop -20% pour laisser courir les gagnants.
4. **Pure Mirror — Exit Only On Mayhem Dump** : n'a aucune sortie automatique de prix — vend
   uniquement quand Mayhem lui-même liquide entièrement sa position.

Tous les paramètres (taille de position, TP/SL/trailing, durée max, filtre de taille d'achat,
copie du dump) sont réglables en direct depuis le panel (bouton "Régler" sur chaque carte).

## Prochaine étape : passage en argent réel

Ce bot est volontairement 100% paper trading pour l'instant (comme demandé). Une fois qu'une
stratégie s'avère rentable en simulation, l'étape suivante est de brancher une exécution
réelle (ex. via l'API de swap de Padre/Jupiter et une clé privée dédiée, avec des limites de
risque strictes) — c'est un changement isolé dans `src/engine/strategyRunner.ts` qui n'affecte
pas le reste de l'architecture.
