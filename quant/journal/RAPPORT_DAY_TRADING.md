# Day trading en papier — relevé

Généré par `scripts/intraday_day.py`. **Aucun ordre réel n'a jamais été passé** :
ce dépôt ne contient aucun adaptateur de courtier.

Ce relevé existe pour remplacer une affirmation par des chiffres. La recherche de
ce dépôt conclut que le day trading de détail ne paie pas ; le bot le fait quand
même, sur données réelles, et le résultat s'écrit ici tout seul.

## Le relevé

| | |
|---|---|
| trades terminés | 656 |
| séances | 60 |
| gain **brut** moyen | +2.890 bp |
| coût moyen (fourchette) | 0.599 bp |
| gain **net** moyen | **+2.291 bp** |
| gain net **médian** | **-0.861 bp** |
| trades gagnants | 48.3 % |
| résultat cumulé | **+15.03 €** |
| par heure de marché | +0.0385 € |
| t de Student | 2.06 |
| sorties au stop | 146 |

La ligne qui décide est **gain net moyen**. Le brut est ce que montrent les
vendeurs de formations ; la fourchette est ce que le marché prélève entre les
deux, à chaque aller-retour, sans exception.

## Le test que personne ne montre : la moyenne tient-elle à quelques coups ?

Une moyenne positive portée par une poignée de trades n'est pas un avantage,
c'est une loterie gagnée. On retire les meilleurs trades et on regarde ce qui
reste :

| | gain net moyen |
|---|---|
| tous les 656 trades | +2.291 bp |
| sans les **5** meilleurs | +1.180 bp |
| sans les **10** meilleurs | +0.397 bp |

Et le trade **médian** rapporte -0.861 bp : c'est ce que
fait le trade typique, par opposition à la moyenne que quelques coups tirent
vers le haut. Si la médiane est négative, la stratégie perd presque à chaque
fois et se rattrape rarement — ce n'est pas la même chose qu'un avantage.

## Face à l'objectif

Objectif annoncé : **10 000 € par mois**.

- rythme actuel : **+5.26 € par mois** sur 500 € de capital
- il en faudrait : 10 000 €
- facteur manquant : **x1 901**

## Vingt derniers trades

| entrée | actif | sens | brut bp | coût bp | net bp | net € | sortie |
|---|---|---|---|---|---|---|---|
| 2026-09-02T19:45 | Nasdaq 100 | vente | -7.25 | 0.70 | -7.95 | -0.080 | stop |
| 2026-09-02T18:20 | S&P 500 | vente | +10.32 | 0.50 | +9.82 | +0.098 | durée |
| 2026-09-02T18:20 | Nasdaq 100 | vente | +11.14 | 0.70 | +10.44 | +0.104 | durée |
| 2026-09-02T17:10 | S&P 500 | achat | +3.12 | 0.50 | +2.62 | +0.026 | durée |
| 2026-09-02T17:10 | Nasdaq 100 | achat | +9.30 | 0.70 | +8.60 | +0.086 | durée |
| 2026-09-02T16:25 | S&P 500 | achat | -0.85 | 0.50 | -1.35 | -0.013 | durée |
| 2026-09-02T14:45 | S&P 500 | vente | +4.11 | 0.50 | +3.61 | +0.036 | durée |
| 2026-09-02T14:35 | Nasdaq 100 | vente | +17.33 | 0.70 | +16.63 | +0.166 | durée |
| 2026-09-02T14:10 | S&P 500 | vente | -26.95 | 0.50 | -27.45 | -0.275 | stop |
| 2026-09-02T13:55 | Nasdaq 100 | achat | +53.73 | 0.70 | +53.03 | +0.530 | durée |
| 2026-09-02T13:35 | S&P 500 | vente | -14.71 | 0.50 | -15.21 | -0.152 | stop |
| 2026-09-01T18:50 | S&P 500 | achat | +14.21 | 0.50 | +13.71 | +0.137 | durée |
| 2026-09-01T18:50 | Nasdaq 100 | achat | +25.86 | 0.70 | +25.16 | +0.252 | durée |
| 2026-09-01T18:40 | S&P 500 | achat | -9.84 | 0.50 | -10.34 | -0.103 | stop |
| 2026-09-01T18:30 | S&P 500 | achat | -6.26 | 0.50 | -6.76 | -0.068 | stop |
| 2026-09-01T18:15 | Nasdaq 100 | achat | -16.92 | 0.70 | -17.62 | -0.176 | stop |
| 2026-09-01T16:35 | Nasdaq 100 | achat | +4.51 | 0.70 | +3.81 | +0.038 | durée |
| 2026-09-01T16:30 | S&P 500 | achat | -10.88 | 0.50 | -11.38 | -0.114 | durée |
| 2026-09-01T15:50 | S&P 500 | vente | +22.10 | 0.50 | +21.60 | +0.216 | durée |
| 2026-09-01T15:40 | Nasdaq 100 | vente | +10.97 | 0.70 | +10.27 | +0.103 | durée |

---

Règles : fade d'extrême, fenêtre 24 barres, seuil 1.5 écarts-types, détention max 6 barres, stop 2.0 écarts-types, 100 € par trade, maximum 6 trades par séance. Actifs : SPY, QQQ.

Aucune position ne traverse la clôture. L'entrée se fait à l'ouverture de la
barre **suivant** le signal : entrer à la clôture de la barre du signal
serait un look-ahead d'une barre, et sur des barres de 5 minutes il vaut à
lui seul plus que l'avantage recherché.
