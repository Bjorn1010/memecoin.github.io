#!/usr/bin/env bash
# Une journée de papier-trading, de bout en bout, sur une machine neuve.
#
# Conçu pour tourner sans personne devant : une session planifiée clone le dépôt,
# lance ce script, et le relevé du jour se retrouve dans l'historique git.
#
# Le conteneur est éphémère et le lac de données est ignoré par git — mais
# `yahoo.daily()` demande la fenêtre maximale à chaque appel, donc l'historique se
# reconstruit tout seul. Rien à conserver entre deux exécutions **sauf le journal**,
# qui est versionné précisément pour ça.
#
# Idempotent : relancer le même jour remplace la ligne du jour au lieu de la dupliquer.

set -euo pipefail

cd "$(dirname "$0")/.."
BRANCH="claude/agent-ia-trading-quant-wf0h3t"

# --------------------------------------------------------------- environnement
if [[ ! -x .venv/bin/python ]]; then
    echo "== création de l'environnement"
    python3 -m venv .venv
    .venv/bin/pip install --quiet --upgrade pip
    .venv/bin/pip install --quiet -r requirements.txt
    .venv/bin/pip install --quiet -e .
fi

# ------------------------------------------------------------------- le cycle
echo "== cycle du $(date -u +%Y-%m-%d)"
set +e
.venv/bin/python -u scripts/paper_day.py
STATUS=$?
set -e

# ------------------------------------------------------------------ le relevé
# Le journal est commité même quand le cycle a échoué. Un relevé qui ne contient que
# les bons jours n'est pas un relevé de ce qui s'est passé, et ce sont justement les
# lignes en échec qui expliquent un trou dans la courbe.
if [[ -n "$(git status --porcelain journal/)" ]]; then
    git add journal/
    git -c user.name="quant paper bot" \
        -c user.email="noreply@anthropic.com" \
        commit -q -m "Papier-trading : cycle du $(date -u +%Y-%m-%d)

Généré par scripts/daily_paper.sh. Aucun ordre réel : ce dépôt ne contient
aucun adaptateur de courtier.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"

    for delay in 2 4 8 16; do
        git push -u origin "$BRANCH" && break
        echo "push échoué, nouvelle tentative dans ${delay}s"
        sleep "$delay"
    done
else
    echo "== journal inchangé, rien à commiter"
fi

exit $STATUS
