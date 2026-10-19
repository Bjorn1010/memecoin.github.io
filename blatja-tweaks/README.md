# Blatja Tweaks

Optimiseur Windows 11 / Tiny11 pour Fortnite. Un seul `.exe` autonome (aucune installation, .NET inclus), interface sombre WPF.

## Utilisation
Double-clic sur `Blatja Tweaks.exe` (demande les droits administrateur), active les interrupteurs voulus, puis **Appliquer les réglages**.
Un point de restauration est créé avant chaque application ; **Tout restaurer** remet Windows comme avant.

## Pages
Accueil (jauges CPU/GPU/RAM, graphique en direct, mode jeu, disque) · Restauration · Corrections ·
Réglages : Général, Débloat, Réseau & souris, Avancé, Services, Profils de jeu, Optimiseur d'apps · Carte graphique · BIOS.

## Ce que ça fait
- **Système** : plan Performances ultimes, Mode Jeu, Game DVR off, HAGS, minuteur système, priorité CPU, MMCSS jeux, effets visuels allégés
- **Entrées/réseau** : accélération souris off, Nagle off
- **Fortnite** : priorité CPU haute, GPU haute performance + plein écran exclusif, graphismes FPS (sauvegarde `.blatja.bak`)
- **GPU NVIDIA** : limite de puissance au max + fréquence minimale verrouillée à 90 % du boost (via `nvidia-smi`)

## Sécurité
Au démarrage, l'application impose la création d'un point de restauration Windows avant toute modification.
Le réglage « Isolation de noyau (VBS) » réduit la sécurité : il n'est pas inclus dans la configuration recommandée.

## Polices
Poppins, Rajdhani, Share Tech Mono (licence SIL OFL), embarquées dans l'exe.

## Limites
- Le gain réel dépend de la machine ; aucun logiciel ne garantit +300 FPS.
- Ce n'est pas un overclock avec offsets (tension/fréquence) : pour ça, MSI Afterburner. AMD : Adrenalin.

## Compiler
`dotnet publish BlatjaTweaks.csproj -c Release -o out` (ou workflow GitHub Actions « Blatja Tweaks (.exe) »).
