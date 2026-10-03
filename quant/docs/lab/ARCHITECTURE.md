# Laboratoire de recherche quant + moteur multi-prop-firms — architecture

Ce document est la **première mission** : il fixe l'architecture, le protocole et les
critères **avant** le moindre résultat. Il est versionné dans Git avant le premier
cycle de recherche, pour que l'historique prouve que les seuils n'ont pas été choisis
après avoir vu les chiffres.

Chaque section suit le même gabarit : **WHAT** (ce que c'est), **WHY** (pourquoi),
**HOW** (comment c'est construit), **RISK** (ce qui peut mal tourner),
**VALIDATION** (comment on vérifie que ça marche).

Le dépôt n'est pas parti de zéro. Le paquet `qt/` contient déjà 20 000 lignes
d'outillage testé (modèle de coûts, Sharpe déflaté, PBO, CV purgée, économétrie,
optimiseurs de portefeuille, paper trading). Le labo est construit **par-dessus**,
pas à côté : réécrire un Sharpe déflaté déjà testé contre sa formule analytique
serait une source de bugs, pas un progrès.

---

## 1. Architecture complète du système

**WHAT.** Sept couches, chacune ne parle qu'à ses voisines :

```
            ┌──────────────────── RESEARCH LAB (qt/lab) ─────────────────────┐
 données →  │ audit → hypothèses → baseline → walk-forward → robustesse →     │
            │ Monte Carlo → significativité → régimes → capacité → décision   │
            │                 ↓ tout est écrit dans la base de recherche      │
            └─────────────────────────────────┬──────────────────────────────┘
                                              │ seules les stratégies au statut
                                              │ PAPER TEST ou plus en sortent
                                    STRATEGY LIBRARY (qt/lab/strategies)
                                              │
                                    SIGNAL ENGINE   (direction + stop, aucune taille)
                                              │
                                    RISK ENGINE     (qt/risk : budget de risque global)
                                              │
                                    PORTFOLIO ENGINE (qt/lab/ensemble, qt/portfolio)
                                              │
                           PROP ADAPTER / TRANSLATOR (qt/prop)
                       ┌──────────────┼──────────────┐
                    PROP A          PROP B         PROP N   (un YAML chacun)
                       │              │              │
                    COMPTE(S)      COMPTE(S)      COMPTE(S)  (état, statut, isolation)
                       │              │              │
                EXECUTION ENGINE : OrderManager → BrokerInterface (qt/brokers, qt/oms)
                       │
                KILL SWITCH (indépendant du modèle)  +  MONITORING / DÉCROISSANCE
```

**WHY.** La séparation stricte est ce qui permet d'ajouter la prop N sans toucher au
signal, et de changer de signal sans toucher à l'exécution. Un signal qui connaît la
taille de compte d'une prop firm est un signal qui sera ré-optimisé pour cette prop
firm — c'est de l'overfitting sur un règlement intérieur.

**HOW.** Les interfaces entre couches sont des objets de données simples :

| frontière | objet | contenu |
|---|---|---|
| signal → risque | `Signal` | instrument, direction, prix de référence, distance de stop, conviction, horodatage, id de stratégie |
| risque → prop | `RiskBudget` | fraction de risque autorisée pour ce signal (avant contraintes de compte) |
| prop → exécution | `OrderIntent` | compte, instrument, quantité, type d'ordre, stop, `client_order_id` déterministe |
| exécution → compte | `Fill` / `AccountSnapshot` | ce que le courtier a réellement fait |

**RISK.** Le risque principal est la fuite d'une couche dans l'autre (une règle de
prop codée dans la stratégie « parce que c'est plus simple »). **VALIDATION.** Un
test vérifie que `qt/lab/strategies` n'importe rien de `qt/prop`, `qt/brokers` ou
`qt/oms` ; un autre traduit le même `Signal` sur trois props différentes et vérifie
que seule la taille change.

---

## 2. Structure des dossiers

**WHAT.** La structure demandée (`quant_engine/data, research, strategies, …`) est
réalisée ainsi — les noms diffèrent parce que les modules existaient déjà :

| demandé | réalisé | statut |
|---|---|---|
| `data/` | `qt/data/` (sources, lac Parquet) + `qt/lab/data_audit.py` | existant + nouveau |
| `research/` | `qt/lab/pipeline.py`, `qt/lab/hypotheses.py` | nouveau |
| `strategies/` | `qt/lab/strategies.py` (retail), `qt/strategies/` (existant) | nouveau |
| `features/` | `qt/features/` (255 features causales) | existant |
| `models/` | `qt/models/`, `qt/lab/meta.py` (simple vs ML) | existant + nouveau |
| `backtesting/` | `qt/lab/simulate.py` (trades, stops), `qt/backtest/` (poids) | nouveau + existant |
| `validation/` | `qt/validation/` + `qt/lab/significance.py` (Reality Check, SPA) | existant + nouveau |
| `robustness/` | `qt/lab/robustness.py` | nouveau |
| `monte_carlo/` | `qt/lab/montecarlo.py` | nouveau |
| `portfolio/` | `qt/portfolio/`, `qt/lab/ensemble.py` | existant + nouveau |
| `risk/` | `qt/risk/`, `qt/lab/sizing.py` | existant + nouveau |
| `execution/` + `brokers/` | `qt/brokers/` (interface, simulé), `qt/oms/` (ordres, réconciliation, kill switch) | nouveau |
| `prop_firms/` | `qt/prop/` (code) + `configs/prop_firms/*.yaml` (règles) | nouveau |
| `monitoring/` | `qt/monitoring/` (décroissance, instantané) | nouveau |
| `database/` | `qt/lab/database.py` + `configs/research_db.sql` | nouveau |
| `configs/` | `configs/` | nouveau |
| `tests/` | `tests/` | existant + nouveaux |
| `reports/` | `reports/cycle_NNN/` | nouveau |
| `main.py` | `qt` (CLI existante) + `scripts/research_cycle.py` | existant + nouveau |

**WHY.** Un seul paquet importable évite deux copies divergentes du même modèle de
coûts. **RISK.** La correspondance n'est pas évidente pour un nouveau lecteur — d'où ce
tableau. **VALIDATION.** `pytest` importe chaque module.

---

## 3. Modèle de données

**WHAT.** Une base relationnelle de recherche, append-only. SQLite par défaut
(zéro installation, testable en local) ; le DDL est du SQL standard, compatible
PostgreSQL (`configs/research_db.sql`).

```
cycles(cycle_id, started_at, protocol_hash, git_commit, notes)
datasets(dataset_id, symbol, asset_class, source, first_ts, last_ts, n_bars,
         content_hash, audit_json)
experiments(experiment_id, cycle_id, timestamp, strategy, family, market,
            timeframe, features, parameters, is_baseline, train_period,
            validation_period, test_period, cost_model, slippage_model,
            metrics_json, decision, reason, dataset_ids)
holdout_ledger(holdout_id, period, strategy, market, consulted_at,
               experiment_id, result_json)            -- UNIQUE(period, strategy, market)
decisions(decision_id, cycle_id, strategy, market, stage, decision, score_json,
          reason, decided_at)
paper_trades(...), live_trades(...)                   -- pour la détection de décroissance
```

**WHY.** Le Sharpe déflaté a besoin du **nombre total d'essais et de leur dispersion**.
Si un essai n'est pas enregistré, il n'existe pas pour la correction, et la
correction devient fausse dans le sens flatteur. Les rejets sont donc enregistrés
exactement comme les succès.

**HOW.** `ResearchDB.record_experiment()` est le seul chemin d'écriture ; il n'existe
aucune méthode `delete`. Le `holdout_ledger` a une contrainte d'unicité : une deuxième
consultation du même holdout pour la même stratégie lève une exception.

**RISK.** Contournement par un script qui évalue sans écrire en base. **VALIDATION.** Le
pipeline calcule le DSR **à partir de la base**, pas de ses variables locales : un
essai non enregistré ne peut pas améliorer un score, il ne peut que le rendre
introuvable.

---

## 4. Pipeline de recherche

**WHAT.**

```
AUDIT DONNÉES → HYPOTHÈSE (falsifiable) → BASELINE (paramètres canoniques, zéro optimisation)
→ GRILLE BORNÉE (≤ 9 configurations / stratégie, déclarées d'avance)
→ WALK-FORWARD (train 5 ans → validation 1 an, glissant) sur la période de recherche
→ PORTE « PROMISING »  → ROBUSTESSE → MONTE CARLO → RÉGIMES → CAPACITÉ
→ SIGNIFICATIVITÉ GLOBALE (DSR sur tous les essais, PBO, Reality Check / SPA)
→ TEST (2020-2022, une fois) → PORTE « PAPER TEST »
→ HOLDOUT FINAL (2023→, une seule fois, verrouillé) → rapport → PAPER TRADING
→ LIVE CANDIDATE uniquement après un relevé papier conforme
```

**WHY.** Chaque étape coûte plus cher que la précédente et élimine des candidats ;
l'ordre fait que le holdout n'est consulté que par une poignée de survivants.

**HOW.** **L'unité de décision est (stratégie × classe d'actifs)**, jamais
(stratégie × instrument). Une stratégie est évaluée sur un panier à risque égal de tous
les instruments de la classe. Choisir « RSI sur l'USDCAD » parce que c'est l'instrument
qui a marché, c'est sélectionner la meilleure courbe — explicitement interdit. Le
détail par instrument est rapporté, jamais utilisé pour décider.

**RISK.** Le panier dilue un edge réel limité à un instrument. C'est un coût assumé : un
edge qui n'existe que sur un instrument sur sept est, a priori, plus probablement du
bruit qu'une découverte. **VALIDATION.** Chaque étape écrit son verdict en base avec
une raison lisible.

---

## 5. Stratégies retail candidates

**WHAT.** 24 hypothèses de recherche, chacune écrite sous la forme
SIGNAL + CONDITION + HORIZON + CIBLE + RISQUE (`qt/lab/hypotheses.py`). Aucune n'est
présumée fonctionner.

| famille | stratégies (paramètres canoniques de la littérature retail) |
|---|---|
| Tendance | croisement SMA 50/200 · croisement EMA 12/26 · Donchian 20/10 (tortues) · momentum série temporelle 12 mois · ADX(14) > 25 |
| Retour à la moyenne | RSI(2) < 10 / > 90 · Bandes de Bollinger 20/2 · pullback sur plus bas 5 jours · IBS < 0,2 |
| Breakout | breakout de volatilité (Williams, ouverture + k × range) · NR7 · cassure du plus haut/bas de la veille |
| Momentum | ROC + accélération · momentum multi-horizons (tendance longue + pullback court) · momentum relatif cross-sectionnel |
| Volatilité | compression puis expansion (squeeze Bollinger) · breakout ATR |
| Price action | structure de marché (sommets/creux de swing confirmés) · balayage de liquidité (« turtle soup ») · rejet (mèche) sur plus bas 20 jours |
| Volume | pic de volume relatif + direction · divergence prix/volume |
| Statistique | paires cointégrées (couverture glissante, z-score) |
| Hybride | RSI(2) dans le sens de la tendance 200 jours |

**Différées, avec la raison enregistrée en base** (pas silencieusement omises) :
opening range breakout et breakout de session (exigent de l'intraday profond ; Yahoo
ne donne que 60 jours en 5 minutes), modèles factoriels (exigent des fondamentaux
point-in-time, non disponibles gratuitement).

**WHY.** Partir des stratégies que les traders particuliers utilisent réellement, c'est
tester l'affirmation commerciale (« ça marche ») plutôt qu'une invention de plus.

**RISK.** Plusieurs stratégies sont des variantes de la même idée (Donchian ≈ momentum
série temporelle) : leurs résultats sont corrélés, ce qui gonfle l'apparence de
« plusieurs confirmations ». **VALIDATION.** La matrice de corrélation des PnL est
calculée et rapportée ; le DSR utilise la dispersion réelle des Sharpe entre essais.

---

## 6. Méthodologie de validation

**WHAT.** Découpage temporel fixe, identique pour toutes les stratégies :

| bloc | période | usage |
|---|---|---|
| RECHERCHE | début des données → 31/12/2019 | walk-forward : train 5 ans glissants → validation 1 an |
| TEST | 01/01/2020 → 31/12/2022 | consulté une fois, par les survivants de la recherche |
| HOLDOUT FINAL | 01/01/2023 → aujourd'hui | consulté **une seule fois**, verrouillé en base |

La période de test contient le krach Covid et le choc de taux de 2022 ; le holdout,
un marché haussier tiré par quelques valeurs. Trois mondes différents.

**HOW.**
- Exécution : signal sur la clôture de t, exécuté à l'ouverture de t+1. Stops
  exécutés au prix du stop, ou à l'ouverture si le marché a gappé au-delà. Si stop et
  objectif sont touchés dans la même barre, **le stop est réputé touché en premier**.
- Coûts : par classe d'actifs (`configs/markets.yaml`), commission + demi-spread +
  slippage + coût de portage (swap, financement CFD, funding, emprunt).
- Walk-forward : sur chaque fenêtre, la configuration de la grille avec le meilleur
  Sharpe **en train** est appliquée à l'année de validation suivante. Le résultat OOS
  est la concaténation des années de validation. On mesure aussi la stabilité des
  paramètres choisis d'une fenêtre à l'autre.
- Métriques : rendement total, CAGR, volatilité, Sharpe, Sortino, Calmar, drawdown
  max et moyen, temps de récupération, taux de réussite, profit factor, espérance,
  trade moyen, turnover, exposition, skew, kurtosis, perte de queue, nombre de trades.

**RISK.** Daily uniquement dans ce premier cycle : les stratégies intraday sont
différées, pas évaluées à tort sur des barres journalières. **VALIDATION.** Tests de
non-anticipation : un signal parfait sur la barre courante ne doit rien rapporter ;
un oracle sur la barre suivante doit gagner énormément ; retarder un signal doit
détruire son edge.

---

## 7. Protocole anti-overfitting

**WHAT.** Les règles, toutes inscrites dans `configs/research_protocol.yaml` avant le
premier run :

1. **Budget d'essais** : ≤ 9 configurations par stratégie, grille déclarée dans
   l'hypothèse avant exécution ; total du cycle enregistré.
2. **Chaque essai compte**, y compris les rejetés, dans le DSR.
3. **DSR** calculé avec la dispersion réelle des Sharpe de tous les essais du cycle.
4. **PBO** (validation croisée combinatoire symétrique) sur la grille de chaque
   stratégie : la meilleure configuration in-sample reste-t-elle au-dessus de la
   médiane hors échantillon ?
5. **White Reality Check** et **Hansen SPA** (bootstrap stationnaire) sur l'ensemble des
   stratégies du cycle : « la meilleure stratégie bat-elle zéro au-delà de ce que la
   recherche de la meilleure sur N produirait par chance ? »
6. **CV purgée + embargo** pour toute couche ML (méta-labeling).
7. **Holdout unique**, verrouillé par contrainte d'unicité.
8. **Interdictions** (partie 36) : aucune sélection sur le seul Sharpe/CAGR/taux de
   réussite, aucune règle ajoutée après un mauvais OOS, aucun paramètre sans
   justification économique.

**WHY.** La question n'est pas « cette stratégie est-elle bonne ? » mais « quelle est
la probabilité que cet edge soit le produit de notre propre recherche ? ».

**RISK.** Le data-snooping **inter-cycles** : le cycle 2 est conçu en ayant vu le
cycle 1. **VALIDATION.** Le compteur d'essais est cumulatif sur tous les cycles en
base, pas remis à zéro.

---

## 8. Modèle de configuration des prop firms

**WHAT.** Un fichier YAML par prop firm dans `configs/prop_firms/`. Le moteur ne
contient **aucune** règle propre à une firme.

```yaml
firm: exemple_2_etapes          # identifiant
status: template                # template | draft | paper | small_live | active
rules_verified: false           # true seulement après lecture des règles officielles
source_url: null                # document d'où viennent les règles
retrieved_at: null
programs:
  - name: challenge_100k
    phase: challenge            # challenge | verification | funded
    account_size: 100000
    currency: USD
    profit_target: 0.10         # fraction de la taille du compte
    max_daily_loss: 0.05
    daily_loss_basis: balance_or_equity_start_of_day   # | balance | equity
    daily_reset_tz: Europe/Prague
    max_total_drawdown: 0.10
    drawdown_type: static       # static | trailing_intraday | trailing_eod
    trailing_lock_at_start: false
    min_trading_days: 4
    max_calendar_days: null
    leverage: {fx: 100, indices: 20, metals: 20, crypto: 2, commodities: 10, equities: 5}
    max_position_lots: null
    allowed_instruments: [fx, indices, metals, commodities, crypto]
    trading_hours: null         # null = horaires du marché
    news_restriction: {enabled: false, minutes_before: 2, minutes_after: 2}
    weekend_holding: true
    consistency_rule: null      # ex. {max_day_share_of_profit: 0.40}
    payout: {split: 0.80, min_days_between: 14}
    other_constraints: []
```

**WHY.** Ajouter la prop N = ajouter un fichier. Les règles changent souvent ; elles
doivent être des données datées et sourcées, pas du code.

**HOW.** `qt/prop/rules.py` charge, valide (types, bornes, champs obligatoires) et
normalise. Une règle inconnue fait **échouer** le chargement plutôt que d'être ignorée :
une contrainte ignorée en silence est exactement celle qui grille le compte.

**RISK.** Les fichiers fournis sont des **gabarits** aux valeurs illustratives, pas les
règles d'une firme réelle (je ne les invente pas : elles doivent venir des documents
officiels, datées). `status: template` empêche tout usage hors simulation.
**VALIDATION.** Tests de chargement, de rejet des champs inconnus, et de chaque règle
(perte journalière, drawdown statique/trailing, objectif, jours minimum, cohérence).

---

## 9. Interface Broker / PropFirm

**WHAT.**

```python
class BrokerInterface(ABC):
    def connect(self) -> None
    def get_account(self) -> AccountSnapshot
    def get_positions(self) -> list[Position]
    def get_orders(self, open_only=True) -> list[Order]
    def place_order(self, intent: OrderIntent) -> Order       # idempotent par client_order_id
    def cancel_order(self, order_id: str) -> Order
    def modify_order(self, order_id: str, **changes) -> Order
```

Implémentations : `SimulatedBroker` (paper, avec **injection de pannes** : déconnexion,
rejet, remplissage partiel, double accusé, latence, prix aberrant). Aucun adaptateur
de courtier réel dans ce cycle — c'est une décision, pas un oubli (section 11).

Au-dessus : `OrderManager` (idempotence, retries sûrs, ordres périmés, remplissages
partiels), `Reconciler` (état local vs courtier), `KillSwitch` (global et par compte).

**WHY.** STRATÉGIE ≠ COURTIER. Le même `OrderManager` pilote n'importe quel courtier.

**HOW.** Le `client_order_id` est déterministe (hash de compte + stratégie + signal +
horodatage) : un retry après une coupure réseau **interroge d'abord** le courtier sur
cet id avant de renvoyer, ce qui rend le doublon impossible plutôt qu'improbable.

**RISK.** Un doublon d'ordre double le risque en silence. **VALIDATION.** Tests de
coupure réseau au milieu d'un envoi, double accusé, rejet, remplissage partiel,
ordre périmé, divergence de positions → kill switch.

---

## 10. Protocole de paper trading

**WHAT.** Toute stratégie au statut PAPER TEST tourne sur `SimulatedBroker` avec les
vraies données du jour, le vrai moteur de risque, le vrai traducteur prop et le vrai
`OrderManager` — seul le courtier est simulé.

**HOW.** Pour chaque trade on enregistre attendu vs réalisé : prix d'entrée, prix de
sortie, slippage, latence, P&L. Durée minimale : **60 jours de bourse** ou **30 trades**,
le plus long des deux.

**Détection de décroissance** (`qt/monitoring/decay.py`) : test de l'espérance réalisée
contre la distribution Monte Carlo du backtest, CUSUM sur les rendements de trade,
Kolmogorov-Smirnov sur la distribution des trades, écart de slippage. Divergence →
`PAUSE → INVESTIGATE → RESEARCH`. **Jamais** de ré-optimisation automatique sur les
dernières pertes.

**RISK.** 60 jours ne prouvent pas un edge (il en faudrait des années) ; ils prouvent
que **l'exécution** colle au backtest. C'est leur seul rôle. **VALIDATION.** Rejeu
d'historique à travers la boucle papier : il doit reproduire le backtest au coût près.

---

## 11. Critères de passage en production

**WHAT.** Une stratégie devient **LIVE CANDIDATE** seulement si **toutes** ces
conditions sont vraies :

| # | critère | mesure |
|---|---|---|
| 1 | Walk-forward OOS positif après coûts | Sharpe OOS net > 0, ≥ 50 % des années positives |
| 2 | Robuste | ≥ 70 % des perturbations gardent Sharpe > 0 |
| 3 | Résiste aux coûts | Sharpe > 0 avec coûts × 1,5 |
| 4 | Pas un artefact de sélection | DSR ≥ 0,90 sur tous les essais cumulés, PBO ≤ 0,5 |
| 5 | Période de test positive | Sharpe test net > 0 |
| 6 | Holdout positif, consulté une fois | Sharpe holdout net > 0 |
| 7 | Monte Carlo acceptable | P(drawdown > 25 % à 10 % de vol cible) ≤ 10 % |
| 8 | Paper trading cohérent | ≥ 60 jours, espérance réalisée dans l'intervalle 90 % du backtest, slippage ≤ 1,5 × modèle |
| 9 | Infrastructure | kill switch testé, réconciliation sans écart, monitoring actif |
| 10 | Décision humaine | aucune activation automatique de capital réel |

Et pour une **prop firm** : règles `rules_verified: true` avec source datée →
paper → petit compte réel → actif, chaque transition validée à la main.

**WHY.** Un excellent backtest n'est pas un critère. **RISK.** Ces critères rejetteront
probablement presque tout. C'est le comportement attendu, pas un défaut.
**VALIDATION.** Le pipeline ne peut pas émettre `LIVE_CANDIDATE` sans relevé papier en
base : la valeur n'est pas atteignable dans un cycle de recherche pur.

---

## Ce que ce système ne fera pas

- Il ne garantit aucune performance. Le score interne **organise la recherche**, il ne
  prédit rien.
- Il ne passe aucun ordre réel. Ajouter un adaptateur de courtier réel est une étape
  séparée, explicite, avec des clés en variables d'environnement à permissions minimales.
- Il n'augmente jamais le risque parce qu'une stratégie a gagné.
