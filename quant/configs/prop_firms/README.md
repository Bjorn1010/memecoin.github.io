# Règles de prop firms — une firme = un fichier

Ajouter une prop firm = ajouter un fichier YAML ici. Aucune ligne de code à modifier.

**Les trois fichiers fournis sont des GABARITS** (`status: template`,
`rules_verified: false`). Leurs valeurs reprennent des structures de règles courantes
dans l'industrie (challenge en 2 étapes à drawdown statique, évaluation futures à
drawdown trailing en fin de journée, 1 étape à trailing intraday) mais **ne sont les
règles d'aucune firme réelle**. Les règles réelles changent souvent ; elles doivent
être copiées depuis les documents officiels, avec l'URL et la date de lecture.

Processus d'intégration (`qt/prop/onboarding.py`) :

```
template → draft (règles sourcées) → paper (rules_verified + tests) →
small_live (≥ 20 jours papier conformes + approbation humaine écrite) →
active (≥ 20 jours small-live sans écart + approbation humaine écrite)
```

Le chargeur refuse toute clé inconnue : une faute de frappe dans `max_daily_loss`
ferait ignorer la règle qui grille le compte.

Champs : voir `qt/prop/rules.py` (`Program`) et `docs/lab/ARCHITECTURE.md` §8.
