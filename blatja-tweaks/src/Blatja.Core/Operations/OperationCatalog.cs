namespace Blatja.Core;

public static class Categories
{
    public const string Gaming = "GAMING", Cpu = "CPU", Gpu = "GPU", Memory = "MEMOIRE", Network = "RESEAU", Storage = "STOCKAGE", Debloat = "DEBLOAT";
    public static readonly string[] All = { Gaming, Cpu, Gpu, Memory, Network, Storage, Debloat };
}

/// <summary>Catalogue des optimisations. Chaque entrée est identifiée, documentée, détectable et réversible.</summary>
public static class OperationCatalog
{
    private const string TcpInterfaces = @"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces";
    private const string Mmcss = @"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile";
    private const string GameConfig = @"HKCU\System\GameConfigStore";
    private const string Ifeo = @"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\";
    private const string ContentDelivery = @"HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager";

    private static readonly string[] Launchers = { "EpicGamesLauncher.exe", "EpicWebHelper.exe", "steam.exe", "steamwebhelper.exe", "Battle.net.exe" };
    private static readonly string[] Browsers = { "chrome.exe", "msedge.exe", "firefox.exe" };

    private static RegTarget D(string path, string name, int v, int? def = null) =>
        new(path, name, RegValue.DWord(v), def is { } d ? RegValue.DWord(d) : null);
    private static RegTarget S(string path, string name, string v, string? def = null) =>
        new(path, name, RegValue.Str(v), def is null ? null : RegValue.Str(def));

    public static IReadOnlyList<Operation> Build(GameDetector games, string localAppData, Func<string, bool> isProcessRunning)
    {
        string FortniteIni() => localAppData.Length == 0 ? "" : $@"{localAppData}\FortniteGame\Saved\Config\WindowsClient\GameUserSettings.ini";

        var ops = new List<Operation>
        {
            // ───────────── GAMING ─────────────
            new RegistryOperation(new[] { D(@"HKCU\Software\Microsoft\GameBar", "AutoGameModeEnabled", 1), D(@"HKCU\Software\Microsoft\GameBar", "AllowAutoGameMode", 1) }) { AbsentMeansEnabled = true,
                Id = "gamemode", Category = Categories.Gaming, Group = "Windows et jeu", Name = "Mode Jeu Windows", RequiresAdmin = false, Impact = Impact.Low,
                Description = "Garde le Mode Jeu de Windows actif : le jeu au premier plan reçoit la priorité sur les tâches de fond.",
                Effect = "HKCU\\Software\\Microsoft\\GameBar : AutoGameModeEnabled = 1, AllowAutoGameMode = 1.",
                Drawbacks = "Aucun inconvénient connu. Windows l'active déjà par défaut : cette option sert surtout à corriger une désactivation antérieure." },
            new RegistryOperation(new[] { D(GameConfig, "GameDVR_Enabled", 0, 1), D(@"HKCU\Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled", 0, 1), D(@"HKLM\SOFTWARE\Policies\Microsoft\Windows\GameDVR", "AllowGameDVR", 0) })
                { Id = "gamedvr", Category = Categories.Gaming, Group = "Windows et jeu", Name = "Capture Xbox / Game DVR désactivée", Impact = Impact.Medium,
                Description = "Arrête l'enregistrement vidéo en arrière-plan de la barre de jeu, qui consomme GPU et disque pendant que tu joues.",
                Effect = "GameDVR_Enabled = 0, AppCaptureEnabled = 0 et la stratégie AllowGameDVR = 0.",
                Drawbacks = "Les raccourcis Xbox d'enregistrement (Win+Alt+R) et de capture d'écran de la barre de jeu ne fonctionnent plus." },
            new RegistryOperation(new[] { D(GameConfig, "GameDVR_FSEBehaviorMode", 2), D(GameConfig, "GameDVR_HonorUserFSEBehaviorMode", 1), D(GameConfig, "GameDVR_DXGIHonorFSEWindowsCompatible", 1), D(GameConfig, "GameDVR_EFSEFeatureFlags", 0) })
                { Id = "fse", Category = Categories.Gaming, Group = "Affichage", Name = "Plein écran exclusif pour les jeux", RequiresAdmin = false, Impact = Impact.Low,
                Description = "Demande à Windows de ne pas convertir les jeux plein écran en fenêtre sans bordure, ce qui réduit la latence d'affichage dans certains jeux.",
                Effect = "HKCU\\System\\GameConfigStore : GameDVR_FSEBehaviorMode = 2 et trois valeurs associées.",
                Drawbacks = "Passer d'une fenêtre à l'autre (Alt+Tab) est parfois plus lent avec un jeu en plein écran exclusif." },
            new RegistryOperation(new[] { S(@"HKCU\Control Panel\Mouse", "MouseSpeed", "0", "1"), S(@"HKCU\Control Panel\Mouse", "MouseThreshold1", "0", "6"), S(@"HKCU\Control Panel\Mouse", "MouseThreshold2", "0", "10") })
                { Id = "mouse", Category = Categories.Gaming, Group = "Entrées", Name = "Souris sans accélération", RequiresAdmin = false, Impact = Impact.Low, Restart = RestartKind.SignOut,
                Description = "Supprime l'accélération du pointeur : un même geste donne toujours la même distance, ce qui rend la visée plus constante.",
                Effect = "HKCU\\Control Panel\\Mouse : MouseSpeed = 0, MouseThreshold1 = 0, MouseThreshold2 = 0.",
                Drawbacks = "Le pointeur paraît plus lent sur le bureau jusqu'à ce que tu règles la sensibilité. Effet à la prochaine ouverture de session." },
            new RegistryOperation(_ => FortniteGpuTargets(games), c => games.Find("fortnite")?.ExePath is null ? Applicability.No("Fortnite n'est pas détecté (Epic Games Launcher).") : Applicability.Yes)
                { Id = "fngpu", Category = Categories.Gaming, Group = "Fortnite", Name = "Fortnite : GPU dédié et plein écran exclusif", RequiresAdmin = false, Impact = Impact.Low,
                Description = "Indique à Windows d'utiliser la carte graphique la plus puissante pour Fortnite et de ne pas appliquer les optimisations plein écran à son exécutable.",
                Effect = "HKCU\\Software\\Microsoft\\DirectX\\UserGpuPreferences et AppCompatFlags\\Layers pour FortniteClient-Win64-Shipping.exe. Aucun fichier du jeu n'est modifié.",
                Drawbacks = "Sur un portable, le jeu utilisera toujours le GPU dédié : plus de chaleur et moins d'autonomie." },
            new GameIniOperation(() => FortniteIni() is { Length: > 0 } p ? p : null, () => isProcessRunning("FortniteClient-Win64-Shipping"), FortniteLowSettings)
                { Id = "fnini", Category = Categories.Gaming, Group = "Fortnite", Name = "Fortnite : qualité graphique orientée FPS", RequiresAdmin = false, Impact = Impact.High, Risk = Risk.Low,
                Description = "Met la qualité des ombres, textures, effets et post-traitement au minimum, coupe la synchronisation verticale et retire la limite d'images.",
                Effect = "Modifie des clés déjà présentes dans GameUserSettings.ini (fichier de réglages utilisateur). Une copie .blatja.bak est conservée.",
                Drawbacks = "L'image est nettement moins détaillée. Le jeu doit être fermé pendant l'application ; Fortnite peut réécrire certains réglages lui-même." },

            // ───────────── CPU ─────────────
            new PowerPlanOperation { Id = "power", Category = Categories.Cpu, Group = "Alimentation", Name = "Plan d'alimentation hautes performances", Impact = Impact.Medium,
                Description = "Active une copie du plan « Performances ultimes » : processeur à pleine fréquence, tous les cœurs actifs, économie d'énergie PCIe coupée.",
                Effect = "Crée un plan dédié (copie de Performances ultimes) et l'active. Ton plan actuel est mémorisé puis rétabli à la restauration ; les plans d'origine ne sont pas modifiés.",
                Drawbacks = "Consommation et chaleur plus élevées ; l'autonomie d'un portable diminue. Si « Performances ultimes » n'existe pas, le plan Performances élevées est utilisé." },
            new RegistryOperation(new[] { D(@"HKLM\SYSTEM\CurrentControlSet\Control\Power\PowerThrottling", "PowerThrottlingOff", 1) }) { CleanupEmptyKeys = true,
                Id = "throttle", Category = Categories.Cpu, Group = "Alimentation", Name = "Pas de bridage d'énergie du processeur", Impact = Impact.Low, MinBuild = 15063,
                Description = "Désactive le Power Throttling : Windows ne ralentit plus les applications en arrière-plan pour économiser du courant.",
                Effect = "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Power\\PowerThrottling : PowerThrottlingOff = 1.",
                Drawbacks = "Consommation légèrement plus élevée, surtout sur portable." },
            new RegistryOperation(new[] { D(@"HKLM\SYSTEM\CurrentControlSet\Control\PriorityControl", "Win32PrioritySeparation", 0x26, 2) })
                { Id = "prio", Category = Categories.Cpu, Group = "Planification", Name = "Priorité au programme au premier plan", Impact = Impact.Low,
                Description = "Donne des tranches de temps processeur plus longues au programme actif, au détriment des tâches de fond.",
                Effect = "HKLM\\SYSTEM\\CurrentControlSet\\Control\\PriorityControl : Win32PrioritySeparation = 0x26.",
                Drawbacks = "Les tâches en arrière-plan (téléchargements, encodage) peuvent aller un peu moins vite pendant que tu joues." },
            new RegistryOperation(new[] { D(@"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\kernel", "GlobalTimerResolutionRequests", 1) })
                { Id = "timer", Category = Categories.Cpu, Group = "Planification", Name = "Résolution du minuteur système", Impact = Impact.Low, Restart = RestartKind.Reboot, MinBuild = 19041,
                Description = "Autorise chaque application à demander un minuteur précis (jusqu'à 0,5 ms) : temps d'image plus réguliers dans certains jeux.",
                Effect = "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\kernel : GlobalTimerResolutionRequests = 1.",
                Drawbacks = "Légère hausse de consommation. Redémarrage nécessaire." },
            new RegistryOperation(new[] { D(Mmcss, "SystemResponsiveness", 0, 20), D(Mmcss + @"\Tasks\Games", "GPU Priority", 8, 8), D(Mmcss + @"\Tasks\Games", "Priority", 6, 2),
                    S(Mmcss + @"\Tasks\Games", "Scheduling Category", "High", "Medium"), S(Mmcss + @"\Tasks\Games", "SFIO Priority", "High", "Normal") })
                { Id = "mmcss", Category = Categories.Cpu, Group = "Planification", Name = "Planificateur multimédia orienté jeux", Impact = Impact.Low,
                Description = "Réserve moins de temps processeur au multimédia de fond et donne une priorité plus haute aux tâches de la catégorie « Games ».",
                Effect = "HKLM\\...\\Multimedia\\SystemProfile : SystemResponsiveness = 0 et les valeurs de la tâche « Games ».",
                Drawbacks = "La lecture audio/vidéo de fond peut être légèrement moins prioritaire en cas de charge très élevée." },

            // ───────────── GPU ─────────────
            new RegistryOperation(new[] { D(@"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode", 2) })
                { Id = "hags", Category = Categories.Gpu, Group = "Planification graphique", Name = "Planification GPU accélérée matériellement", Impact = Impact.Medium, Restart = RestartKind.Reboot, MinBuild = 19041,
                Description = "Laisse le GPU gérer sa propre file de tâches, ce qui peut réduire la latence entre le processeur et la carte graphique.",
                Effect = "HKLM\\SYSTEM\\CurrentControlSet\\Control\\GraphicsDrivers : HwSchMode = 2.",
                Drawbacks = "Demande une carte récente (NVIDIA GTX 1000+, AMD RX 5000+) et un pilote à jour. Peut causer des instabilités avec certains pilotes : restaure si tu constates des artefacts." },

            // ───────────── MÉMOIRE ET PROCESSUS ─────────────
            new RegistryOperation(_ => Browsers.Select(e => D(Ifeo + e + @"\PerfOptions", "CpuPriorityClass", 5)).ToList()) { CleanupEmptyKeys = true,
                Id = "appbrowser", Category = Categories.Memory, Group = "Priorité des applications", Name = "Navigateurs en priorité réduite", Impact = Impact.Low,
                Description = "Chrome, Edge et Firefox démarrent avec une priorité processeur sous la normale : ils pèsent moins sur un jeu lancé en même temps.",
                Effect = "HKLM\\...\\Image File Execution Options\\<navigateur>\\PerfOptions : CpuPriorityClass = 5.",
                Drawbacks = "Les pages peuvent être un peu plus lentes à charger pendant une forte charge CPU." },
            new RegistryOperation(_ => Launchers.Select(e => D(Ifeo + e + @"\PerfOptions", "CpuPriorityClass", 5)).ToList()) { CleanupEmptyKeys = true,
                Id = "applauncher", Category = Categories.Memory, Group = "Priorité des applications", Name = "Lanceurs de jeux en priorité réduite", Impact = Impact.Low,
                Description = "Epic Games Launcher, Steam et Battle.net consomment moins de processeur pendant que tu joues.",
                Effect = "PerfOptions\\CpuPriorityClass = 5 pour les exécutables des lanceurs (pas pour les jeux).",
                Drawbacks = "Les téléchargements et mises à jour lancés depuis ces applications peuvent être légèrement ralentis." },
            new ServiceOperation("auto", "SysMain") { Recommended = false,
                Id = "svcsys", Category = Categories.Memory, Group = "Services", Name = "SysMain (Superfetch)", Impact = Impact.Low,
                Description = "Arrête le préchargement des applications en mémoire.",
                Effect = "Service SysMain : type de démarrage Désactivé, puis arrêt.",
                Drawbacks = "Utile sur disque dur mécanique : sur un HDD, les applications s'ouvrent plus lentement. Sans effet notable sur SSD." },

            // ───────────── RÉSEAU ─────────────
            new RegistryOperation(c => c.Registry.SubKeys(TcpInterfaces).SelectMany(id => new[] { D($@"{TcpInterfaces}\{id}", "TcpAckFrequency", 1), D($@"{TcpInterfaces}\{id}", "TCPNoDelay", 1) }).ToList())
                { Id = "nagle", Category = Categories.Network, Group = "Latence", Name = "Algorithme de Nagle désactivé", Impact = Impact.Low,
                Description = "Envoie les petits paquets immédiatement au lieu de les regrouper : utile pour les jeux en ligne qui échangent de petits messages.",
                Effect = "TcpAckFrequency = 1 et TCPNoDelay = 1 sur chaque interface réseau.",
                Drawbacks = "Légère augmentation du nombre de petits paquets. Le gain sur le ping est faible et dépend du jeu." },
            new RegistryOperation(new[] { D(Mmcss, "NetworkThrottlingIndex", -1, 10) })
                { Id = "netthrottle", Category = Categories.Network, Group = "Latence", Name = "Plafonnement réseau multimédia retiré", Impact = Impact.Low,
                Description = "Windows limite par défaut le débit réseau pendant la lecture multimédia ; cette option retire cette limite.",
                Effect = "HKLM\\...\\Multimedia\\SystemProfile : NetworkThrottlingIndex = 0xFFFFFFFF.",
                Drawbacks = "Peut augmenter légèrement l'usage CPU lors de gros transferts pendant la lecture vidéo." },
            new RegistryOperation(new[] { D(@"HKLM\SOFTWARE\Policies\Microsoft\Windows\DeliveryOptimization", "DODownloadMode", 0) }) { CleanupEmptyKeys = true,
                Id = "dopolicy", Category = Categories.Network, Group = "Partage", Name = "Pas de partage des mises à jour (upload)", Impact = Impact.Low,
                Description = "Empêche ton PC d'envoyer des morceaux de mises à jour Windows à d'autres ordinateurs, ce qui consomme de la bande passante montante.",
                Effect = "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\DeliveryOptimization : DODownloadMode = 0. Windows Update continue de fonctionner normalement.",
                Drawbacks = "Les mises à jour se téléchargent uniquement depuis les serveurs Microsoft (parfois un peu plus lent sur un réseau local partagé)." },

            // ───────────── STOCKAGE ─────────────
            new LastAccessOperation { Id = "ntfs", Category = Categories.Storage, Group = "Disque", Name = "Moins d'écritures disque inutiles", Impact = Impact.Low,
                Description = "Coupe l'horodatage du dernier accès à chaque fichier : moins d'écritures sur le disque pendant les chargements.",
                Effect = "fsutil behavior set disablelastaccess 1.",
                Drawbacks = "L'heure du dernier accès aux fichiers n'est plus tenue à jour (utilisée seulement par quelques outils de sauvegarde)." },
            new ServiceOperation("delayed-auto", "WSearch") { Recommended = false,
                Id = "svcsearch", Category = Categories.Storage, Group = "Indexation", Name = "Indexation de la recherche", Impact = Impact.Low,
                Description = "Arrête l'indexation des fichiers en arrière-plan.",
                Effect = "Service WSearch : type de démarrage Désactivé, puis arrêt.",
                Drawbacks = "La recherche de fichiers dans l'Explorateur et le menu Démarrer devient plus lente." },

            // ───────────── DEBLOAT ─────────────
            new RegistryOperation(new[] { D(@"HKLM\SOFTWARE\Policies\Microsoft\Dsh", "AllowNewsAndInterests", 0) }) { CleanupEmptyKeys = true,
                Id = "widgets", Category = Categories.Debloat, Group = "Interface et distractions", Name = "Widgets et actualités désactivés", MinBuild = 22000, Impact = Impact.Low,
                Description = "Retire le panneau Widgets de la barre des tâches et son processus en arrière-plan.",
                Effect = "HKLM\\SOFTWARE\\Policies\\Microsoft\\Dsh : AllowNewsAndInterests = 0.",
                Drawbacks = "Plus d'actualités ni de météo dans la barre des tâches." },
            new RegistryOperation(new[] { D(@"HKCU\Software\Policies\Microsoft\Windows\WindowsCopilot", "TurnOffWindowsCopilot", 1) }) { CleanupEmptyKeys = true,
                Id = "copilot", Category = Categories.Debloat, Group = "Interface et distractions", Name = "Copilot désactivé", RequiresAdmin = false, MinBuild = 22621, Impact = Impact.Low,
                Description = "Désactive l'assistant Windows Copilot et son bouton.",
                Effect = "HKCU\\Software\\Policies\\Microsoft\\Windows\\WindowsCopilot : TurnOffWindowsCopilot = 1.",
                Drawbacks = "L'assistant n'est plus disponible. Disparaît selon la version de Windows 11 installée." },
            new RegistryOperation(new[] { D(ContentDelivery, "SubscribedContent-338388Enabled", 0, 1), D(ContentDelivery, "SubscribedContent-338389Enabled", 0, 1), D(ContentDelivery, "SubscribedContent-310093Enabled", 0, 1),
                    D(ContentDelivery, "SystemPaneSuggestionsEnabled", 0, 1), D(ContentDelivery, "SilentInstalledAppsEnabled", 0, 1), D(ContentDelivery, "OemPreInstalledAppsEnabled", 0, 1),
                    D(@"HKCU\Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo", "Enabled", 0, 1) })
                { Id = "tips", Category = Categories.Debloat, Group = "Interface et distractions", Name = "Suggestions et publicités retirées", RequiresAdmin = false, Impact = Impact.Low,
                Description = "Coupe les suggestions du menu Démarrer, les astuces Windows, les installations silencieuses d'applications et l'identifiant publicitaire.",
                Effect = "Valeurs ContentDeliveryManager et AdvertisingInfo mises à 0.",
                Drawbacks = "Plus de recommandations ni de suggestions d'applications dans Windows." },
            new RegistryOperation(new[] { D(@"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects", "VisualFXSetting", 2, 0), D(@"HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "EnableTransparency", 0, 1), S(@"HKCU\Control Panel\Desktop\WindowMetrics", "MinAnimate", "0", "1") })
                { Id = "visual", Category = Categories.Debloat, Group = "Interface et distractions", Name = "Effets visuels allégés", RequiresAdmin = false, Impact = Impact.Low, Restart = RestartKind.SignOut,
                Description = "Désactive la transparence et les animations de fenêtres pour alléger l'affichage du bureau.",
                Effect = "VisualFXSetting = 2, EnableTransparency = 0, MinAnimate = 0.",
                Drawbacks = "Le bureau est moins fluide visuellement (plus d'effet de flou ni d'animation d'ouverture). Effet complet à la prochaine ouverture de session." },
            new RegistryOperation(new[] { D(@"HKLM\SOFTWARE\Policies\Microsoft\Windows\CloudContent", "DisableWindowsConsumerFeatures", 1) }) { CleanupEmptyKeys = true,
                Id = "consumer", Category = Categories.Debloat, Group = "Applications préinstallées", Name = "Applications sponsorisées bloquées", Impact = Impact.Low,
                Description = "Empêche Windows d'installer automatiquement des applications et jeux promotionnels (Candy Crush, etc.).",
                Effect = "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\CloudContent : DisableWindowsConsumerFeatures = 1. Ne désinstalle aucune application existante.",
                Drawbacks = "Aucun inconvénient connu. Effet sur les nouveaux profils utilisateurs." },
            new RegistryOperation(new[] { D(@"HKCU\Software\Policies\Microsoft\Windows\Explorer", "DisableSearchBoxSuggestions", 1) }) { CleanupEmptyKeys = true,
                Id = "bing", Category = Categories.Debloat, Group = "Recherche Windows", Name = "Recherche web retirée du menu Démarrer", RequiresAdmin = false, Impact = Impact.Low,
                Description = "La recherche Windows ne contacte plus Bing : résultats locaux plus rapides, moins de trafic réseau.",
                Effect = "HKCU\\Software\\Policies\\Microsoft\\Windows\\Explorer : DisableSearchBoxSuggestions = 1.",
                Drawbacks = "Plus de résultats web dans la recherche du menu Démarrer." },
            new RegistryOperation(new[] { D(@"HKLM\SOFTWARE\Policies\Microsoft\Windows\AppPrivacy", "LetAppsRunInBackground", 2) }) { CleanupEmptyKeys = true,
                Id = "bg", Category = Categories.Debloat, Group = "Applications en arrière-plan", Name = "Applications du Store bloquées en arrière-plan", Impact = Impact.Medium,
                Description = "Empêche les applications du Microsoft Store de s'exécuter et de se synchroniser en arrière-plan.",
                Effect = "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\AppPrivacy : LetAppsRunInBackground = 2 (forcer le refus).",
                Drawbacks = "Les applications du Store (Courrier, Calendrier, Météo) ne notifient plus quand elles sont fermées." },
            new RegistryOperation(new[] { D(@"HKLM\SOFTWARE\Policies\Microsoft\Edge", "BackgroundModeEnabled", 0), D(@"HKLM\SOFTWARE\Policies\Microsoft\Edge", "StartupBoostEnabled", 0) }) { CleanupEmptyKeys = true,
                Id = "edge", Category = Categories.Debloat, Group = "Applications en arrière-plan", Name = "Edge ne tourne plus en arrière-plan", Impact = Impact.Low,
                Description = "Coupe le démarrage anticipé et l'exécution en arrière-plan de Microsoft Edge.",
                Effect = "HKLM\\SOFTWARE\\Policies\\Microsoft\\Edge : BackgroundModeEnabled = 0, StartupBoostEnabled = 0.",
                Drawbacks = "Edge met un peu plus de temps à s'ouvrir. Un bandeau « géré par votre organisation » peut apparaître dans Edge." },
            new RegistryOperation(new[] { D(@"HKLM\SOFTWARE\Policies\Microsoft\Windows\OneDrive", "DisableFileSyncNGSC", 1) }) { CleanupEmptyKeys = true, Recommended = false,
                Id = "onedrive", Category = Categories.Debloat, Group = "Synchronisation cloud", Name = "OneDrive désactivé", Impact = Impact.Low,
                Description = "Désactive la synchronisation OneDrive.",
                Effect = "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\OneDrive : DisableFileSyncNGSC = 1. Aucun fichier n'est supprimé.",
                Drawbacks = "Tes fichiers ne sont plus sauvegardés dans le cloud : à éviter si OneDrive protège tes documents." },
            new ServiceOperation("auto", "DiagTrack")
                { Id = "telemetry", Category = Categories.Debloat, Group = "Fonctions facultatives", Name = "Service de télémétrie (DiagTrack)", Impact = Impact.Low,
                Description = "Arrête le service qui collecte et envoie des données de diagnostic à Microsoft.",
                Effect = "Service DiagTrack : type de démarrage Désactivé, puis arrêt.",
                Drawbacks = "Windows envoie moins de données de diagnostic ; certaines fonctions de dépannage automatique peuvent être moins précises." },
            new ServiceOperation("demand", "WerSvc")
                { Id = "svcwer", Category = Categories.Debloat, Group = "Fonctions facultatives", Name = "Rapport d'erreurs Windows", Impact = Impact.Low,
                Description = "Arrête l'envoi automatique de rapports de plantage à Microsoft.",
                Effect = "Service WerSvc : type de démarrage Désactivé, puis arrêt.",
                Drawbacks = "Les rapports d'erreurs ne sont plus envoyés ; les diagnostics locaux restent disponibles." },
            new ServiceOperation("demand", "lfsvc")
                { Id = "svcloc", Category = Categories.Debloat, Group = "Fonctions facultatives", Name = "Service de localisation", Impact = Impact.Low,
                Description = "Désactive la géolocalisation du PC.",
                Effect = "Service lfsvc : type de démarrage Désactivé, puis arrêt.",
                Drawbacks = "Les applications qui utilisent ta position (météo, cartes) ne la trouvent plus automatiquement." },
            new ServiceOperation("demand", "XblAuthManager", "XblGameSave", "XboxNetApiSvc", "XboxGipSvc") { Recommended = false,
                Id = "svcxbox", Category = Categories.Debloat, Group = "Fonctions facultatives", Name = "Services Xbox", Impact = Impact.Low,
                Description = "Désactive les services Xbox (connexion, sauvegardes cloud, accessoires).",
                Effect = "Services XblAuthManager, XblGameSave, XboxNetApiSvc, XboxGipSvc : Désactivés, puis arrêtés.",
                Drawbacks = "Casse l'application Xbox, Game Pass PC, les jeux Microsoft Store et les manettes Xbox sans fil." },
            new ServiceOperation("auto", "Spooler") { Recommended = false,
                Id = "svcprint", Category = Categories.Debloat, Group = "Fonctions facultatives", Name = "Spouleur d'impression", Impact = Impact.Low,
                Description = "Désactive le service d'impression.",
                Effect = "Service Spooler : type de démarrage Désactivé, puis arrêt.",
                Drawbacks = "Plus aucune impression, y compris vers un PDF, tant qu'il est désactivé." },
        };

        foreach (var op in ops)
        {
            if (SafetyPolicy.Violation(op, EmptyContext) is { } why)
                throw new InvalidOperationException($"Opération « {op.Id} » refusée par la politique de sécurité : {why}");
        }
        return ops;
    }

    /// <summary>Contexte vide utilisé uniquement pour vérifier les cibles statiques à la construction du catalogue.</summary>
    private static readonly SystemContext EmptyContext = new(new NullRegistry(), new NullRunner(), new NullFiles(), new NullInfo());

    private static IReadOnlyList<RegTarget> FortniteGpuTargets(GameDetector games)
    {
        string? exe = games.Find("fortnite")?.ExePath;
        if (exe is null) return Array.Empty<RegTarget>();
        return new[]
        {
            S(@"HKCU\Software\Microsoft\DirectX\UserGpuPreferences", exe, "GpuPreference=2;"),
            S(@"HKCU\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers", exe, "~ DISABLEDXMAXIMIZEDWINDOWEDMODE"),
        };
    }

    private static readonly (string, string)[] FortniteLowSettings =
    {
        ("sg.ViewDistanceQuality", "0"), ("sg.ShadowQuality", "0"), ("sg.AntiAliasingQuality", "0"), ("sg.TextureQuality", "0"),
        ("sg.EffectsQuality", "0"), ("sg.PostProcessQuality", "0"), ("sg.FoliageQuality", "0"),
        ("bUseVSync", "False"), ("bMotionBlur", "False"), ("FrameRateLimit", "0.000000"), ("MenuFrameRateLimit", "0.000000"),
    };

    private sealed class NullRegistry : IRegistry
    {
        public RegValue? Get(string path, string name) => null;
        public void Set(string path, string name, RegValue value) { }
        public void DeleteValue(string path, string name) { }
        public void DeleteKey(string path) { }
        public bool KeyExists(string path) => false;
        public IReadOnlyList<string> SubKeys(string path) => Array.Empty<string>();
        public IReadOnlyList<string> ValueNames(string path) => Array.Empty<string>();
    }
    private sealed class NullRunner : IProcessRunner { public ProcessResult Run(string file, string args, int timeoutMs = 30000) => new(1, ""); }
    private sealed class NullFiles : IFileSystem
    {
        public bool FileExists(string path) => false; public bool DirectoryExists(string path) => false;
        public string ReadAllText(string path) => ""; public void WriteAllText(string path, string text) { }
        public void Copy(string from, string to, bool overwrite) { }
        public IEnumerable<string> EnumerateFiles(string dir, string pattern, bool recursive = false) => Array.Empty<string>();
        public IEnumerable<string> EnumerateDirectories(string dir) => Array.Empty<string>();
    }
    private sealed class NullInfo : ISystemInfo { public int Build => 99999; public bool IsAdmin => true; public string Description => "test"; }
}

/// <summary>Profils de jeu : ensembles d'opérations. La liste exacte est affichée à l'utilisateur avant application.</summary>
public sealed record GameProfile(string Key, string Name, string Summary, IReadOnlyList<string> OpIds);

public static class GameProfiles
{
    private static readonly string[] Balanced = { "gamemode", "gamedvr", "mouse", "fse" };
    private static readonly string[] Gaming = Balanced.Concat(new[] { "power", "mmcss", "throttle", "netthrottle", "nagle", "dopolicy", "bg", "appbrowser", "applauncher", "fngpu" }).ToArray();
    private static readonly string[] Max = Gaming.Concat(new[] { "prio", "timer", "hags", "fnini", "ntfs", "edge", "telemetry", "visual" }).ToArray();

    public static readonly IReadOnlyList<GameProfile> All = new[]
    {
        new GameProfile("balanced", "Équilibré", "Réglages Windows de jeu sans impact sur la consommation. Aucun changement lourd.", Balanced),
        new GameProfile("gaming", "Gaming", "Équilibré + alimentation, planification, réseau et réduction des tâches de fond.", Gaming),
        new GameProfile("max", "Performance maximale", "Gaming + minuteur, planification GPU, qualité Fortnite et allègement de Windows. Plus de chaleur et de consommation.", Max),
    };
}
