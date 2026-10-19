# Audit de BLATJA (version 1) et refonte

Audit réalisé sur le code existant avant la refonte (C# / .NET 8 / WPF, exe autonome, aucune dépendance NuGet).

## Ce que faisait la version 1

| Fonction | Verdict | Détail |
|---|---|---|
| Écriture de clés de registre (≈ 30 réglages) | **Fonctionnel** | Les valeurs étaient réellement écrites. |
| Boost GPU NVIDIA (`nvidia-smi`) | **Fonctionnel** | Limite de puissance + fréquence minimale. Cartes NVIDIA uniquement. |
| Mesures CPU / RAM / disque | **Fonctionnel** | Lues sur le système. |
| Point de restauration | **Partiel** | Créé via PowerShell, mais le nom saisi par l'utilisateur était injecté dans le script avec un filtrage minimal. |
| Interrupteur « actif » d'un réglage | **Trompeur** | L'état venait d'un fichier `state.json` local, pas de Windows. Un réglage modifié ailleurs (ou par une mise à jour Windows) restait affiché « actif ». |
| Restauration d'un réglage | **Partiel** | Réécrivait des valeurs par défaut codées en dur, pas les valeurs d'origine : elle pouvait écraser un réglage personnalisé. |
| Vérification après application | **Absente** | Aucune relecture du résultat. |
| « Score d'optimisation » | **Fictif** | C'était le ratio interrupteurs activés / total, présenté comme un score. Supprimé. |
| Mode démo (`BLATJA_DEMO`) | **Fictif (développement)** | Générait des mesures synthétiques pour les captures. Supprimé. |
| Priorité IFEO de Fortnite | **Risqué** | Clé surveillée par certains anti-triche. Supprimée. |
| Désactivation de l'isolation de noyau (VBS) | **Contraire à la politique de sécurité** | Réduit la sécurité du système. Supprimée. |
| Tests automatisés | **Absents** | |

## Problèmes d'architecture

- Toute la logique système (registre, services, `sc`, `powercfg`) vivait dans des lambdas de `Tweaks.cs` et dans le code-behind de `MainWindow` (543 lignes) : intestable sans Windows.
- Droits administrateur exigés dès le lancement (manifeste), même pour regarder des graphiques.
- Rendu du graphique à chaque image (60 fps) via `CompositionTarget.Rendering` et sondage `nvidia-smi` chaque seconde : consommation inutile.
- Textes marketing (« gagne des FPS ») sans mesure derrière.
- « Tout activer / Tout désactiver » ambigus : l'utilisateur ne savait pas ce qui allait être modifié.

## Ce qui a changé

- **`Blatja.Core`** (indépendant de Windows) : modèle d'opération (détection de l'état réel → capture des valeurs d'origine → application → **vérification** → restauration), moteur (scan non destructif, plan, exécution séquentielle, annulation propre, journal), politique de sécurité, détection des jeux, gestion du démarrage, règles de diagnostic, comparaison avant/après.
- **`Blatja.App`** (WPF) : interface, adaptateurs Windows, mesures. Aucune logique d'optimisation dans les vues.
- **`Blatja.Tests`** : 106 tests (Linux, sans Windows) avec des doublures du registre, des services et du système de fichiers.
- Droits minimaux : l'analyse et le monitoring fonctionnent sans administrateur ; l'élévation n'est demandée que pour modifier le système.
- Politique de sécurité : refus (et non simple avertissement) de toute opération touchant Defender, le pare-feu, Windows Update, SmartScreen, l'isolation de noyau, ou des services critiques. Vérifiée par des tests sur tout le catalogue.
