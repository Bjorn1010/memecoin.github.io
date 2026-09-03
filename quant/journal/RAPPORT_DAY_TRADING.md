# Day trading en papier — relevé

Généré par `scripts/intraday_day.py`. **Aucun ordre réel n'a jamais été passé** :
ce dépôt ne contient aucun adaptateur de courtier.

Ce relevé existe pour remplacer une affirmation par des chiffres. La recherche de
ce dépôt conclut que le day trading de détail ne paie pas ; le bot le fait quand
même, sur données réelles, et le résultat s'écrit ici tout seul.

## Le relevé

| | |
|---|---|
| trades terminés | 576 |
| séances | 60 |
| gain **brut** moyen | +2.853 bp |
| coût moyen (fourchette) | 0.599 bp |
| gain **net** moyen | **+2.254 bp** |
| gain net **médian** | **-2.104 bp** |
| trades gagnants | 45.8 % |
| résultat cumulé | **+12.98 €** |
| par heure de marché | +0.0333 € |
| t de Student | 1.66 |
| sorties au stop | 181 |

La ligne qui décide est **gain net moyen**. Le brut est ce que montrent les
vendeurs de formations ; la fourchette est ce que le marché prélève entre les
deux, à chaque aller-retour, sans exception.

## Le test que personne ne montre : la moyenne tient-elle à quelques coups ?

Une moyenne positive portée par une poignée de trades n'est pas un avantage,
c'est une loterie gagnée. On retire les meilleurs trades et on regarde ce qui
reste :

| | gain net moyen |
|---|---|
| tous les 576 trades | +2.254 bp |
| sans les **5** meilleurs | +0.955 bp |
| sans les **10** meilleurs | -0.092 bp |

Et le trade **médian** rapporte -2.104 bp : c'est ce que
fait le trade typique, par opposition à la moyenne que quelques coups tirent
vers le haut. Si la médiane est négative, la stratégie perd presque à chaque
fois et se rattrape rarement — ce n'est pas la même chose qu'un avantage.

## Face à l'objectif

Objectif annoncé : **10 000 € par mois**.

- rythme actuel : **+4.54 € par mois** sur 500 € de capital
- il en faudrait : 10 000 €
- facteur manquant : **x2 201**

## Vingt derniers trades

| entrée | actif | sens | brut bp | coût bp | net bp | net € | sortie |
|---|---|---|---|---|---|---|---|
| 2026-09-02T19:45 | Nasdaq 100 | vente | -7.25 | 0.70 | -7.95 | -0.080 | stop |
| 2026-09-02T18:20 | Nasdaq 100 | vente | +5.22 | 0.70 | +4.52 | +0.045 | durée |
| 2026-09-02T17:35 | S&P 500 | achat | +5.43 | 0.50 | +4.93 | +0.049 | durée |
| 2026-09-02T17:10 | Nasdaq 100 | achat | +5.02 | 0.70 | +4.32 | +0.043 | durée |
| 2026-09-02T16:25 | S&P 500 | achat | -3.59 | 0.50 | -4.09 | -0.041 | durée |
| 2026-09-02T14:45 | S&P 500 | vente | +16.31 | 0.50 | +15.81 | +0.158 | durée |
| 2026-09-02T14:10 | S&P 500 | vente | -26.95 | 0.50 | -27.45 | -0.275 | stop |
| 2026-09-02T13:55 | Nasdaq 100 | achat | +31.05 | 0.70 | +30.35 | +0.303 | durée |
| 2026-09-02T13:35 | S&P 500 | vente | -14.71 | 0.50 | -15.21 | -0.152 | stop |
| 2026-09-01T18:50 | S&P 500 | achat | +9.60 | 0.50 | +9.10 | +0.091 | durée |
| 2026-09-01T18:50 | Nasdaq 100 | achat | +20.98 | 0.70 | +20.28 | +0.203 | durée |
| 2026-09-01T18:40 | S&P 500 | achat | -9.84 | 0.50 | -10.34 | -0.103 | stop |
| 2026-09-01T18:30 | S&P 500 | achat | -6.26 | 0.50 | -6.76 | -0.068 | stop |
| 2026-09-01T18:15 | Nasdaq 100 | achat | -16.92 | 0.70 | -17.62 | -0.176 | stop |
| 2026-09-01T15:50 | S&P 500 | vente | +35.05 | 0.50 | +34.55 | +0.345 | durée |
| 2026-09-01T15:40 | Nasdaq 100 | vente | +43.74 | 0.70 | +43.04 | +0.430 | durée |
| 2026-09-01T13:35 | S&P 500 | achat | +30.58 | 0.50 | +30.08 | +0.301 | durée |
| 2026-09-01T13:35 | Nasdaq 100 | achat | +37.20 | 0.70 | +36.50 | +0.365 | durée |
| 2026-08-31T19:45 | S&P 500 | vente | -12.27 | 0.50 | -12.77 | -0.128 | stop |
| 2026-08-31T19:45 | Nasdaq 100 | vente | -13.86 | 0.70 | -14.56 | -0.146 | stop |

---

Règles : fade d'extrême, fenêtre 24 barres, seuil 1.5 écarts-types, détention max 12 barres, stop 2.0 écarts-types, 100 € par trade, maximum 6 trades par séance. Actifs : SPY, QQQ.

Aucune position ne traverse la clôture. L'entrée se fait à l'ouverture de la
barre **suivant** le signal : entrer à la clôture de la barre du signal
serait un look-ahead d'une barre, et sur des barres de 5 minutes il vaut à
lui seul plus que l'avantage recherché.
