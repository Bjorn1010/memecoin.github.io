# Mayhem bot — état des connaissances

Source de vérité pour les cycles autonomes. À relire au début de chaque cycle, et à mettre
à jour à la fin. La consigne de la Routine pointe ici plutôt que de dupliquer ces faits,
parce qu'une consigne figée devient fausse au bout de deux cycles et induit en erreur.

## Coûts réels (mesurés, pas supposés)

- **Priority fee : 0.000025 SOL par transaction.** Mesuré sur 40 transactions Mayhem lues
  on-chain (`src/tools/measureFees.ts`). Le modèle a longtemps facturé 0.003 — **120x trop**.
  Sur 364 jambes cela représentait 1.09 SOL de frais fictifs contre 0.009 réels, assez pour
  ruiner un capital de 2 SOL à lui seul. **Toute conclusion de rentabilité antérieure à cette
  mesure est invalide, y compris les conclusions négatives.**
- **Frais de plateforme : 1% par jambe, 2% par aller-retour.** Celui-ci est réel (pump.fun) et
  c'est désormais le coût qui contraint. Une variante n'est viable que si son edge de prix
  dépasse 2%.

## Ce qui marche

- **Profondeur du pool à l'entrée** : relation monotone, mesurée au coût réel.
  40 SOL → +0.9% d'edge, 22.1% de gagnants (n=217) ;
  150 SOL → +4.4%, 24.4% (n=41) ;
  250 SOL → +7.8%, 35.0% (n=20).
  Seul le premier est sous le seuil de 2% des frais de plateforme.
  (Une mesure antérieure concluait l'inverse : elle passait par le frais fantôme.)
- **`maxHoldSeconds = 600` est indispensable.** Sans lui, une position sur un token mort ne
  sort jamais : pas de trade = pas de mouvement de prix = aucun seuil déclenché. La stratégie
  se bloque à 8/8, et les comparaisons deviennent une course à la saturation plutôt qu'un test
  de politique de sortie.

## Ce qui est réfuté

- Trail large -45% : pire taux de gagnants (16%).
- Stop serré -6% : indiscernable de -12%.
- Grosses positions (0.75 SOL) : edge de prix -11.4%, ruinée en minutes. Baisser la charge
  fixe en pourcentage n'aide pas si l'edge est négatif.
- **Post-migration : prémisse morte.** 20 migrations détectées, pools à 1$-126$ (médiane ~6$)
  des heures après. Décodeur vérifié correct (octet 48 = complete, réserves nulles) : les
  courbes se terminent vraiment, mais les tokens sont vidés dans la foulée.
  **Ne jamais baisser `MIN_POST_MIGRATION_LIQUIDITY_USD` (25000)** : c'est la seule protection
  contre des fills sur des pools à 6$. La stratégie reste une sonde ; qu'elle ne trade jamais
  est le résultat attendu.

## Artefacts démasqués (quatre) — à re-tester avant d'annoncer tout gain

1. Entrée bookée au prix d'une bonding curve **en cours de vidage** à la migration → faux +1300%.
2. Données de curve **réinjectées pour un mint déjà migré** → sortie 22x hors plage, et un
   `stop_loss` booké sur +176%.
3. Entrée **sans réserves connues** (slippage 0) appariée à une sortie calculée sur réserves →
   8 allers-retours de 3.5x à 13x en quelques secondes. **Les deux prix étaient dans la plage
   on-chain : le contrôle de plage seul ne suffit pas.**
4. Fills post-migration à **slippage nul dans un pool quasi vide** → +1464% en 81 secondes.

Contrôles à appliquer : prix d'entrée **et** de sortie contre la plage on-chain
(`mayhem_events`) ; multiple énorme sur durée courte ; slippage exactement 0 des deux côtés ;
slippage incohérent avec la profondeur du pool ; `stop_loss` à pct positif ou `take_profit` à
pct négatif. Un gain spectaculaire sur une durée courte est **suspect par défaut**.

Nuance : pour un mint migré, nos prix viennent de DexScreener alors que `mayhem_events`
contient des prix de bonding curve d'avant migration — la comparaison de plage sonnera « hors
plage » à tort. Juger alors sur l'amplitude réelle du mint et la durée.

## Distribution source

Trades de Mayhem : **médiane -47.6%, moyenne +26.7%** — une loterie portée par ~9.6% de trades
à +100% et plus. Il faut capturer la queue sans se faire saigner par les perdants fréquents ni
par les frais. Sa taille d'achat médiane est 0.0249 SOL (p90 = 0.164, p99 = 1.08).

## Statut

Aucune configuration n'est démontrée rentable à ce jour. Si aucune ne tient après de nombreux
cycles, « ce wallet n'est pas copiable de façon rentable » est une conclusion valide et utile.
**Ne pas fabriquer un résultat positif.**
