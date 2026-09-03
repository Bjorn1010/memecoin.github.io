# Papier-trading — relevé

Généré par `scripts/paper_day.py`. Aucun ordre réel n'a jamais été passé :
ce dépôt ne contient aucun adaptateur de courtier.

**Dernier cycle** : 2026-09-03 12:13 UTC — statut `ok`

## Où en est l'essai

| | |
|---|---|
| jours enregistrés | 1 |

## Étape 1 : le live colle-t-il au backtest ?

Pas encore mesurable. trop court pour mesurer quoi que ce soit

Annualiser deux semaines de rendements produit un nombre sans information,
et c'est toujours celui qu'on cite. Il est retenu jusqu'à 60 jours.

## Ce livre est-il achetable avec 500 € ?

| | actions entières | actions fractionnées |
|---|---|---|
| positions obtenues | **3 / 15** | 15 / 15 |
| capital investi | 207 € sur 729 € voulus | 729 € |
| erreur de poids | **1.045** | 0.000 |

L'erreur de poids est la somme des écarts entre le livre voulu et le livre
obtenu. Zéro = la stratégie mesurée, exactement. Au-dessus de ~0,2 ce n'est
plus la même stratégie, quel que soit le nom qu'on lui donne.

Les lignes qui disparaissent en actions entières ne sont pas les moins utiles :
ce sont les plus chères à l'action, ce qui n'a aucun rapport avec leur rôle
dans le portefeuille. Un critère de sélection que personne n'a choisi.

### À partir de quel capital le livre est-il reproductible ?

| capital | positions obtenues | investi / voulu | erreur (entières) | erreur (fractionnées) |
|---|---|---|---|---|
| 500 € | 3 / 15 | 28 % | 1.045 | 0.000 |
| 1 000 € | 7 / 15 | 54 % | 0.668 | 0.000 |
| 2 500 € | 10 / 15 | 73 % | 0.394 | 0.000 |
| 5 000 € | 12 / 15 | 83 % | 0.244 | 0.000 |
| 10 000 € | 14 / 15 | 92 % | 0.112 | 0.000 |
| 25 000 € | 15 / 15 | 95 % | 0.079 | 0.000 |
| 100 000 € | 15 / 15 | 99 % | 0.012 | 0.000 |

**Conséquence pratique** : avec 500 €, il faut un courtier qui
propose les **actions fractionnées** (Trading 212, Interactive Brokers,
Trade Republic et d'autres). Chez un courtier classique il faudrait environ
25 000 € pour tenir les quinze lignes.

## Livre actuel

| marché | poids |
|---|---|
| dollar américain (UUP) | +21.84% |
| obligations à haut rendement (HYG) | +21.03% |
| obligations d'État 10 ans (IEF) | +14.95% |
| obligations d'entreprises (LQD) | +12.65% |
| obligations d'État 20 ans (TLT) | +10.81% |
| immobilier US (VNQ) | +10.68% |
| matières premières (DBC) | +9.32% |
| pétrole (USO) | +8.59% |
| S&P 500 (SPY) | +7.86% |
| actions internationales (EFA) | +7.43% |
| petites capis US (IWM) | +5.85% |
| Nasdaq 100 (QQQ) | +5.05% |
| or (GLD) | +4.20% |
| pays émergents (EEM) | +4.07% |
| argent (SLV) | +1.56% |

## Dix derniers cycles

| date | statut | équité | perte | brut |
|---|---|---|---|---|
| 2026-09-03 | ok | 99 978.12 | -0.00 % | 1.46 |

---

Configuration : `{"allow_short": true  "horizons": [32  64  128  256]  "max_gross": 1.5  "max_weight": 0.25  "response": "tanh"  "scale": 1.0  "target_vol": 0.1  "vol_window": 60}`  mélange tendance 30%  cible de volatilité 10%  capital de départ 500.
