# Faire tourner le bot en continu

Le bot est en **paper trading uniquement**. Il n'existe aucun adaptateur de courtier,
aucun identifiant, aucun chemin de passage d'ordre dans ce dépôt. Rien de ce qui suit ne
peut engager d'argent réel.

## La forme de déploiement à préférer

Une entrée cron appelant un cycle, pas un processus qui tourne indéfiniment.

```cron
# tous les jours à 22h10 UTC — après la clôture US (21h00 UTC), avant que Yahoo
# ne republie. Le décalage de 10 minutes laisse le temps aux données de se stabiliser.
10 22 * * 1-5  cd /chemin/vers/quant && .venv/bin/python -m qt.cli bot --cycles 1 >> logs/bot.log 2>&1
```

Pourquoi cron plutôt qu'un démon :

- **Le système d'exploitation le redémarre.** Un processus long qui meurt à 3 h du matin
  reste mort ; une entrée cron rate un cycle puis reprend.
- **Aucun état en mémoire à perdre.** Tout est dans SQLite. Un cycle interrompu laisse le
  livre précédent intact plutôt qu'un livre à moitié rééquilibré.
- **Le journal est le journal du système.** Pas de gestion de rotation à écrire.

`qt bot --cycles 0` existe pour observer le bot tourner, pas pour le déployer.

## Vérifier qu'il fait vraiment quelque chose

```bash
.venv/bin/python -m qt.cli bot-status
```

Trois champs à lire, dans cet ordre :

| Champ | Ce qu'il faut y voir |
|---|---|
| `last_cycle` | Doit avancer chaque jour ouvré. S'il stagne, cron ne tourne pas. |
| `last_reason` | `ok` en marche normale. `stale` signifie que le flux s'est arrêté. |
| `equity` | **Doit bouger.** Une équité figée signifiait autrefois que le livre n'était jamais valorisé — le système tournait, enregistrait, rapportait, et annonçait « aucune perte » quoi que fasse le marché. |

## Ce que le bot fait à chaque cycle

1. **Rafraîchit** les données. Échoue en douceur : une panne de source n'arrête pas un
   livre bâti sur vingt ans d'historique, elle le fait trader la vue de la veille.
2. **Vérifie la fraîcheur.** Le seul arrêt dur. Trader un flux qui a silencieusement
   cessé de se mettre à jour, c'est ainsi qu'un livre traverse un krach en croyant que
   rien ne s'est passé.
3. **Valorise** le livre détenu depuis le cycle précédent, et facture l'écart de
   fourchette sur la rotation nécessaire.
4. **Calcule** les poids — même code que le backtest, appelé de la même façon. Un chemin
   live qui réimplémente le chemin de recherche en divergera, et la divergence se
   découvre en production.
5. **Applique le risque** : cible de volatilité, plafonds, disjoncteur de drawdown. Le
   disjoncteur réduit, il ne liquide jamais. Liquider au creux d'un drawdown réalise la
   perte et garantit de rater la reprise.
6. **Enregistre tout** : le signal, le poids demandé, le poids autorisé, et pourquoi ils
   diffèrent.

## Récupérer l'historique

La base est du SQLite ordinaire, lisible par n'importe quel outil sans que le bot tourne :

```bash
sqlite3 data/runs/daily.sqlite \
  "SELECT datetime(ts/1000,'unixepoch') AS t, equity, drawdown, halted
   FROM equity WHERE run_id='daily' ORDER BY ts DESC LIMIT 20;"
```

## Ce qu'il faut surveiller les premières semaines

Le bot n'a jamais tourné en continu sur une période réelle. C'est le seul test qu'il ne
peut pas se faire à lui-même, et il n'est pas encore fait. Ce qu'il faut comparer :

- La courbe d'équité live contre un backtest de **la même fenêtre**. Un écart net signifie
  que le chemin live et le chemin de recherche ont divergé quelque part.
- La rotation réalisée contre celle du backtest. Si elle est plus élevée en live, la bande
  de non-trading ne fait pas son travail.
- Le nombre de cycles `stale` ou `error`. Un seul par mois est normal ; un par semaine
  signale une source qui se dégrade.
