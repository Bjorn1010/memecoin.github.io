# Synthèse de la nuit — 3 cycles de recherche

**En une phrase : aucune stratégie n'a atteint PAPER TEST. Le meilleur résultat honnête est un
portefeuille diversifié qui reste positif sur des données jamais vues, mais avec un edge trop faible
pour être statistiquement certain et pour « faire scale ».**

## Ce qui a été testé

- **24 stratégies retail** (tendance, retour à la moyenne, breakout, momentum, volatilité,
  price action, volume, paires) × **7 classes d'actifs** (Forex, indices, futures, actions,
  crypto, métaux, matières premières), données journalières, coûts réalistes, exécution à
  l'ouverture suivante.
- **1 301 essais** enregistrés dans `reports/research.db`, y compris tous les rejets.
- Cycle 1 : [`cycle_001/`](cycle_001/README.md) · cycle 2 : [`cycle_002/`](cycle_002/README.md) ·
  cycle 3 : [`cycle_003/`](cycle_003/README.md)

## Résultats

| | verdict |
|---|---|
| Stratégies seules | 125 rejetées, 42 PROMISING. Meilleurs Sharpe walk-forward : +0,5 à +0,7 (actions, futures, indices). Aucune ne bat ce que le meilleur de 1 131 essais produirait par chance. |
| Forex | 21 stratégies sur 22 rejetées après coûts. |
| Crypto | Résultats Yahoo **invalidés** (données fausses, voir plus bas). Sur Binance, historique trop court avant 2020 pour le protocole. |
| Panier retour à la moyenne actions (cycle 2) | PROMISING, robustesse insuffisante (62 %). |
| Tendance multi-classes (cycle 2) | PROMISING, Sharpe walk-forward +0,36. |
| **Portefeuille de laboratoire, 40 flux (cycle 3)** | **Positif sur données jamais vues : Sharpe +0,32 (2020-22) et +0,20 (2023→), contre +0,82 en recherche. PSR 0,75 < 0,95 → PROMISING.** |

Ce que dit le cycle 3 : le portefeuille n'était pas que du bruit, puisqu'il reste positif hors
échantillon. Mais environ 70 % de l'edge de recherche était de la sélection. Un Sharpe de 0,2 à 0,3,
c'est une volatilité de 10 % pour 2 à 3 % de rendement espéré par an, avec des années perdantes
fréquentes. Ce n'est pas une machine à scaler.

**Prop firms :** les tables de réussite de challenge dans les rapports sont calculées sur la période
de recherche (Sharpe +0,82). Elles sont donc **trop optimistes d'un facteur 3 environ**. Avec l'edge
réellement observé hors échantillon, passer un challenge relève surtout de la chance.

## Pièges trouvés et corrigés (la partie la plus utile de la nuit)

1. **Barres FX Yahoo datées un jour trop tôt** en heure d'été (≈ 700 barres « le dimanche » par paire).
2. **Ouverture périmée des indices cash** : l'ouverture égale la clôture de la veille dans 66 à 92 %
   des séances avant 2010. Remplacés par des ETF.
3. **Biais d'anticipation dans mon propre simulateur** : sauter les barres qui touchent les deux
   ordres stop. Sharpe +2,4 → −1,4 sur les futures ES une fois corrigé.
4. **Hauts/bas de Yahoo crypto non négociables** : cassure crypto à Sharpe +3,7 qui a **passé
   toutes les portes statistiques, test et holdout compris**. Rejouée heure par heure sur Binance :
   environ 0. Invalidée. Les tests statistiques ne protègent pas d'un problème de données.
5. **Bug de l'ancien chargeur Binance** : tout ce qui suit le 1er janvier 2025 était perdu en silence
   (passage aux microsecondes). Corrigé, ce qui touche aussi le bot existant.
6. CUSUM de détection de décroissance mal réglé (65 % de fausses alertes), trade sans stop pendant
   le warm-up de l'ATR, holdout vide compté comme un échec : corrigés, avec un test pour chacun.

## Écarts au protocole (déclarés dans `configs/research_protocol.yaml`)

- Le cycle 3 a remplacé la porte du Sharpe déflaté par un jugement sur données jamais vues. Décidé
  **après** avoir vu que cette porte rejetait tout : la dispersion des essais, gonflée par des
  artefacts, la rendait infranchissable. Même avec cette barre abaissée, rien ne passe.
- Les hypothèses combinées des cycles 2 et 3 ont été choisies au vu du cycle 1 : c'est une
  sélection, déclarée comme telle.

## Pourquoi je m'arrête ici plutôt que de continuer à chercher

Les périodes 2020-2026 sont maintenant consultées pour ces stratégies. Chaque nouveau cycle
construit avec ce que j'ai vu cette nuit serait de la recherche jusqu'à ce que ça marche, la
définition même du data-snooping. Le protocole est fait pour empêcher exactement ça.

## Ce qui pourrait réellement faire avancer

1. **Paper trading du portefeuille de laboratoire** (`lab_portfolio_c1`) : c'est le seul candidat
   qui a survécu à des données jamais vues. Le relevé papier est le seul juge restant.
2. **Données que la recherche n'a pas encore** : intraday profond (Binance 1m, FX Dukascopy) pour
   les stratégies de session et d'opening range, différées faute de données ; taux d'intérêt pour
   le carry FX ; spreads réels des prop firms.
3. **Règles réelles de tes prop firms** (copiées de leurs documents, avec la date), pour remplacer
   les gabarits et refaire la simulation de challenge avec l'edge hors échantillon (+0,2 à +0,3),
   pas celui de recherche.
