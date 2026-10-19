# Blatja Tweaks

Outil d'optimisation Windows 10/11 (testé sur Tiny11) : monitoring réel, analyse, optimisations documentées et réversibles, gaming.
Un seul `.exe` autonome (aucune installation, .NET inclus).

## Principes

- **Données réelles ou « Indisponible »** : aucune valeur n'est inventée. Température CPU et usage GPU non-NVIDIA ne sont pas exposés par Windows → affichés comme indisponibles.
- **État réel** : chaque optimisation lit Windows (registre, services, `powercfg`, `fsutil`) pour savoir si elle est appliquée.
- **Chaque modification est sauvegardée, vérifiée et journalisée.** Si la vérification échoue, elle est annulée.
- **Aucun gain garanti** : le rapport avant/après donne des mesures instantanées avec leurs limites, jamais un « +X FPS ».
- **Sécurité préservée** : Defender, pare-feu, Windows Update, SmartScreen, isolation de noyau et services critiques sont refusés par construction.

## Pages

Dashboard · Monitoring (1/5/15 min, infobulles) · Analyse et optimisation (scan → diagnostic → plan → exécution → rapport) ·
Gaming (jeux détectés, profils, latence) · CPU · GPU · RAM et processus · Réseau et latence · Stockage et démarrage · Windows Debloat ·
Utilitaires · Historique · Points de restauration · Paramètres.

## Structure

```
src/Blatja.Core   moteur, opérations, sécurité, jeux, diagnostic (net8.0, sans dépendance Windows)
src/Blatja.App    interface WPF, adaptateurs Windows, mesures
tests/Blatja.Tests tests (xUnit)
```

## Développer

```
dotnet test tests/Blatja.Tests
dotnet publish src/Blatja.App -c Release -o out      # produit « Blatja Tweaks.exe »
```

Variables utiles en développement : `BLATJA_PAGE=<page>` (ouvre une page), `BLATJA_READONLY=1` (simule l'absence de droits administrateur).

## Limites connues

- Les modifications système n'ont pas été exécutées sur un vrai Windows par l'auteur de cette refonte : le moteur est testé avec des doublures, et l'interface a été vérifiée sous Wine.
- Mesures GPU, température et boost : cartes NVIDIA avec `nvidia-smi` uniquement.
- Le boost GPU n'est pas un overclock avec tension (MSI Afterburner pour cela) et disparaît au redémarrage.

Polices : Poppins et Share Tech Mono (SIL Open Font License).
