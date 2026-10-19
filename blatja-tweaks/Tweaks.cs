using System.Runtime.InteropServices;
using Microsoft.Win32;

namespace BlatjaTweaks;

internal static class Tweaks
{
    private const string UltimateScheme = "e9a42b02-d5df-448d-aa00-03f14749eb61";
    private const string HighPerfScheme = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c";
    private const string BalancedScheme = "381b4222-f694-41f0-9685-ff5bb260df2e";
    private const string BlatjaScheme = "b1a71a00-0000-4000-8000-000000000001";

    private const string TcpInterfaces = @"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces";
    private const string Mmcss = @"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile";
    private const string FnExeName = "FortniteClient-Win64-Shipping.exe";
    private const string Ifeo = @"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\" + FnExeName;

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool SystemParametersInfo(uint action, uint param, int[] value, uint winIni);

    private static void SetMouse(int speed, int t1, int t2)
    {
        Reg.Set(@"HKCU\Control Panel\Mouse", "MouseSpeed", speed.ToString(), RegistryValueKind.String);
        Reg.Set(@"HKCU\Control Panel\Mouse", "MouseThreshold1", t1.ToString(), RegistryValueKind.String);
        Reg.Set(@"HKCU\Control Panel\Mouse", "MouseThreshold2", t2.ToString(), RegistryValueKind.String);
        SystemParametersInfo(0x0004 /*SPI_SETMOUSE*/, 0, new[] { t1, t2, speed }, 3);
    }

    private const string IfeoRoot = @"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\";
    private static readonly string[] Launchers = { "EpicGamesLauncher.exe", "EpicWebHelper.exe", "steam.exe", "steamwebhelper.exe", "Battle.net.exe" };

    private static void Svc(string start, params string[] names)
    {
        foreach (var n in names)
        {
            Service(n, start);
            if (start == "disabled") Sh.Run("sc", $"stop {n}");
        }
    }

    private static void Service(string name, string start)
    {
        var r = Sh.Run("sc", $"config {name} start= {start}");
        // 1060 = service absent (fréquent sur Tiny11) : rien à faire
        if (r.Code != 0 && r.Code != 1060) throw new InvalidOperationException($"sc : {r.Output.Split('\n')[0].Trim()}");
    }

    private static string RequireFortniteExe() =>
        Fortnite.FindExe() ?? throw new FileNotFoundException("Fortnite introuvable (Epic Games Launcher).");

    public static List<Tweak> Build() => new()
    {
        // ───────────── Système ─────────────
        new()
        {
            Id = "power", Category = "GÉNÉRAL", Name = "Plan d'alimentation « Performances ultimes »",
            Description = "Processeur toujours à pleine fréquence, tous les cœurs actifs, économie d'énergie PCIe coupée.",
            Apply = () =>
            {
                var r = Sh.Run("powercfg", $"-duplicatescheme {UltimateScheme} {BlatjaScheme}");
                string guid = r.Code == 0 ? BlatjaScheme : HighPerfScheme;
                if (r.Code == 0)
                {
                    // réglages appliqués uniquement à notre copie du plan, jamais aux plans d'origine
                    Sh.Run("powercfg", $"-setacvalueindex {BlatjaScheme} SUB_PROCESSOR PROCTHROTTLEMIN 100");
                    Sh.Run("powercfg", $"-setacvalueindex {BlatjaScheme} SUB_PROCESSOR CPMINCORES 100");
                    Sh.Run("powercfg", $"-setacvalueindex {BlatjaScheme} SUB_PCIEXPRESS ASPM 0");
                }
                var s = Sh.Run("powercfg", $"-setactive {guid}");
                if (s.Code != 0) throw new InvalidOperationException("powercfg : " + s.Output);
            },
            Revert = () =>
            {
                Sh.Run("powercfg", $"-setactive {BalancedScheme}");
                Sh.Run("powercfg", $"-delete {BlatjaScheme}");
            },
        },
        new()
        {
            Id = "gamemode", Category = "GÉNÉRAL", Name = "Mode Jeu Windows",
            Description = "Donne la priorité aux ressources du jeu au premier plan.",
            Apply = () =>
            {
                Reg.Set(@"HKCU\Software\Microsoft\GameBar", "AutoGameModeEnabled", 1);
                Reg.Set(@"HKCU\Software\Microsoft\GameBar", "AllowAutoGameMode", 1);
            },
            Revert = () =>
            {
                Reg.Del(@"HKCU\Software\Microsoft\GameBar", "AutoGameModeEnabled");
                Reg.Del(@"HKCU\Software\Microsoft\GameBar", "AllowAutoGameMode");
            },
        },
        new()
        {
            Id = "gamedvr", Category = "GÉNÉRAL", Name = "Désactiver la capture Xbox / Game DVR",
            Description = "Supprime l'enregistrement en arrière-plan qui coûte des images par seconde.",
            Apply = () =>
            {
                Reg.Set(@"HKCU\System\GameConfigStore", "GameDVR_Enabled", 0);
                Reg.Set(@"HKCU\Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled", 0);
                Reg.Set(@"HKLM\SOFTWARE\Policies\Microsoft\Windows\GameDVR", "AllowGameDVR", 0);
            },
            Revert = () =>
            {
                Reg.Set(@"HKCU\System\GameConfigStore", "GameDVR_Enabled", 1);
                Reg.Set(@"HKCU\Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled", 1);
                Reg.Del(@"HKLM\SOFTWARE\Policies\Microsoft\Windows\GameDVR", "AllowGameDVR");
            },
        },
        new()
        {
            Id = "hags", Category = "AVANCÉ", Name = "Planification GPU accélérée (HAGS)", NeedsReboot = true,
            Description = "Réduit la latence CPU→GPU. Nécessite une carte récente (NVIDIA GTX 1000+ / AMD RX 5000+).",
            Apply = () => Reg.Set(@"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode", 2),
            Revert = () => Reg.Del(@"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode"),
        },
        new()
        {
            Id = "timer", Category = "AVANCÉ", Name = "Résolution du minuteur système", NeedsReboot = true,
            Description = "Autorise les jeux à demander un minuteur précis : frametimes plus réguliers.",
            Apply = () => Reg.Set(@"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\kernel", "GlobalTimerResolutionRequests", 1),
            Revert = () => Reg.Del(@"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\kernel", "GlobalTimerResolutionRequests"),
        },
        new()
        {
            Id = "prio", Category = "AVANCÉ", Name = "Priorité CPU au programme actif",
            Description = "Win32PrioritySeparation = 0x26 : le jeu au premier plan passe avant les tâches de fond.",
            Apply = () => Reg.Set(@"HKLM\SYSTEM\CurrentControlSet\Control\PriorityControl", "Win32PrioritySeparation", 0x26),
            Revert = () => Reg.Set(@"HKLM\SYSTEM\CurrentControlSet\Control\PriorityControl", "Win32PrioritySeparation", 2),
        },
        new()
        {
            Id = "mmcss", Category = "AVANCÉ", Name = "Planificateur multimédia orienté jeux",
            Description = "Supprime le plafonnement réseau et donne la priorité GPU/CPU aux tâches « Games ».",
            Apply = () =>
            {
                Reg.Set(Mmcss, "NetworkThrottlingIndex", -1);
                Reg.Set(Mmcss, "SystemResponsiveness", 0);
                Reg.Set(Mmcss + @"\Tasks\Games", "GPU Priority", 8);
                Reg.Set(Mmcss + @"\Tasks\Games", "Priority", 6);
                Reg.Set(Mmcss + @"\Tasks\Games", "Scheduling Category", "High", RegistryValueKind.String);
                Reg.Set(Mmcss + @"\Tasks\Games", "SFIO Priority", "High", RegistryValueKind.String);
            },
            Revert = () =>
            {
                Reg.Set(Mmcss, "NetworkThrottlingIndex", 10);
                Reg.Set(Mmcss, "SystemResponsiveness", 20);
                Reg.Set(Mmcss + @"\Tasks\Games", "GPU Priority", 8);
                Reg.Set(Mmcss + @"\Tasks\Games", "Priority", 2);
                Reg.Set(Mmcss + @"\Tasks\Games", "Scheduling Category", "Medium", RegistryValueKind.String);
                Reg.Set(Mmcss + @"\Tasks\Games", "SFIO Priority", "Normal", RegistryValueKind.String);
            },
        },
        new()
        {
            Id = "visual", Category = "GÉNÉRAL", Name = "Effets visuels allégés",
            Description = "Désactive transparence et animations de fenêtres (effet complet à la prochaine session).",
            Apply = () =>
            {
                Reg.Set(@"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects", "VisualFXSetting", 2);
                Reg.Set(@"HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "EnableTransparency", 0);
                Reg.Set(@"HKCU\Control Panel\Desktop\WindowMetrics", "MinAnimate", "0", RegistryValueKind.String);
            },
            Revert = () =>
            {
                Reg.Set(@"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects", "VisualFXSetting", 0);
                Reg.Set(@"HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "EnableTransparency", 1);
                Reg.Set(@"HKCU\Control Panel\Desktop\WindowMetrics", "MinAnimate", "1", RegistryValueKind.String);
            },
        },


        new()
        {
            Id = "throttle", Category = "AVANCÉ", Name = "Pas de bridage d'énergie du processeur",
            Description = "Désactive le Power Throttling : Windows ne ralentit plus le jeu pour économiser du courant.",
            Apply = () => Reg.Set(@"HKLM\SYSTEM\CurrentControlSet\Control\Power\PowerThrottling", "PowerThrottlingOff", 1),
            Revert = () => Reg.Del(@"HKLM\SYSTEM\CurrentControlSet\Control\Power\PowerThrottling", "PowerThrottlingOff"),
        },
        new()
        {
            Id = "fse", Category = "GÉNÉRAL", Name = "Plein écran exclusif pour tous les jeux",
            Description = "Évite la couche de composition Windows : moins de latence d'affichage, plus d'images.",
            Apply = () =>
            {
                const string k = @"HKCU\System\GameConfigStore";
                Reg.Set(k, "GameDVR_FSEBehaviorMode", 2);
                Reg.Set(k, "GameDVR_HonorUserFSEBehaviorMode", 1);
                Reg.Set(k, "GameDVR_DXGIHonorFSEWindowsCompatible", 1);
                Reg.Set(k, "GameDVR_EFSEFeatureFlags", 0);
            },
            Revert = () =>
            {
                const string k = @"HKCU\System\GameConfigStore";
                Reg.Del(k, "GameDVR_FSEBehaviorMode");
                Reg.Del(k, "GameDVR_HonorUserFSEBehaviorMode");
                Reg.Del(k, "GameDVR_DXGIHonorFSEWindowsCompatible");
                Reg.Del(k, "GameDVR_EFSEFeatureFlags");
            },
        },
        new()
        {
            Id = "bg", Category = "GÉNÉRAL", Name = "Moins de tâches en arrière-plan",
            Description = "Bloque les applications de fond et le partage de mises à jour (upload) qui chargent CPU et réseau.",
            Apply = () =>
            {
                Reg.Set(@"HKLM\SOFTWARE\Policies\Microsoft\Windows\AppPrivacy", "LetAppsRunInBackground", 2);
                Reg.Set(@"HKLM\SOFTWARE\Policies\Microsoft\Windows\DeliveryOptimization", "DODownloadMode", 0);
            },
            Revert = () =>
            {
                Reg.Del(@"HKLM\SOFTWARE\Policies\Microsoft\Windows\AppPrivacy", "LetAppsRunInBackground");
                Reg.Del(@"HKLM\SOFTWARE\Policies\Microsoft\Windows\DeliveryOptimization", "DODownloadMode");
            },
        },
        new()
        {
            Id = "telemetry", Category = "GÉNÉRAL", Name = "Télémétrie Windows désactivée",
            Description = "Arrête le service de collecte de données (DiagTrack) qui consomme disque et CPU en tâche de fond.",
            Apply = () => { Service("DiagTrack", "disabled"); Sh.Run("sc", "stop DiagTrack"); },
            Revert = () => { Service("DiagTrack", "auto"); Sh.Run("sc", "start DiagTrack"); },
        },
        new()
        {
            Id = "ntfs", Category = "AVANCÉ", Name = "Disque : moins d'écritures inutiles",
            Description = "Coupe l'horodatage du dernier accès aux fichiers : moins d'activité disque pendant les chargements.",
            Apply = () => Sh.Run("fsutil", "behavior set disablelastaccess 1"),
            Revert = () => Sh.Run("fsutil", "behavior set disablelastaccess 2"),
        },
        new()
        {
            Id = "vbs", Category = "AVANCÉ", Name = "Isolation de noyau (VBS) désactivée", NeedsReboot = true, Recommended = false,
            Description = "Peut rendre quelques % de FPS sur certains processeurs, mais réduit la sécurité. Non inclus dans la configuration recommandée.",
            Apply = () =>
            {
                Reg.Set(@"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity", "Enabled", 0);
                Reg.Set(@"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard", "EnableVirtualizationBasedSecurity", 0);
            },
            Revert = () =>
            {
                Reg.Del(@"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity", "Enabled");
                Reg.Del(@"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard", "EnableVirtualizationBasedSecurity");
            },
        },

        // ───────────── Entrées & réseau ─────────────
        new()
        {
            Id = "mouse", Category = "RÉSEAU", Name = "Désactiver l'accélération de la souris",
            Description = "Précision 1:1 : la visée devient constante, indispensable en compétitif.",
            Apply = () => SetMouse(0, 0, 0),
            Revert = () => SetMouse(1, 6, 10),
        },
        new()
        {
            Id = "nagle", Category = "RÉSEAU", Name = "Latence réseau réduite (Nagle off)",
            Description = "Envoie les paquets immédiatement : moins de ping instable en partie.",
            Apply = () =>
            {
                foreach (var id in Reg.SubKeys(TcpInterfaces))
                {
                    Reg.Set($@"{TcpInterfaces}\{id}", "TcpAckFrequency", 1);
                    Reg.Set($@"{TcpInterfaces}\{id}", "TCPNoDelay", 1);
                }
            },
            Revert = () =>
            {
                foreach (var id in Reg.SubKeys(TcpInterfaces))
                {
                    Reg.Del($@"{TcpInterfaces}\{id}", "TcpAckFrequency");
                    Reg.Del($@"{TcpInterfaces}\{id}", "TCPNoDelay");
                }
            },
        },

        // ───────────── Fortnite ─────────────
        new()
        {
            Id = "fnprio", Category = "JEUX", Name = "Priorité CPU « Haute » pour Fortnite",
            Description = "Windows lance Fortnite avec une priorité processeur élevée à chaque démarrage.",
            Apply = () => Reg.Set(Ifeo + @"\PerfOptions", "CpuPriorityClass", 3),
            Revert = () => Reg.DelKey(Ifeo + @"\PerfOptions"),
        },
        new()
        {
            Id = "fngpu", Category = "JEUX", Name = "GPU haute performance + plein écran exclusif",
            Description = "Force la carte dédiée et coupe les « optimisations plein écran » pour Fortnite.",
            Apply = () =>
            {
                string exe = RequireFortniteExe();
                Reg.Set(@"HKCU\Software\Microsoft\DirectX\UserGpuPreferences", exe, "GpuPreference=2;", RegistryValueKind.String);
                Reg.Set(@"HKCU\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers", exe,
                    "~ DISABLEDXMAXIMIZEDWINDOWEDMODE", RegistryValueKind.String);
            },
            Revert = () =>
            {
                string? exe = Fortnite.FindExe();
                if (exe is null) return;
                Reg.Del(@"HKCU\Software\Microsoft\DirectX\UserGpuPreferences", exe);
                Reg.Del(@"HKCU\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers", exe);
            },
        },
        new()
        {
            Id = "fnini", Category = "JEUX", Name = "Graphismes optimisés pour les FPS",
            Description = "Qualité minimale (ombres, effets, textures…), V-Sync et limite de FPS coupés. Sauvegarde auto.",
            Apply = Fortnite.ApplyLowSettings,
            Revert = Fortnite.RestoreSettings,
        },

        // ───────────── Débloat ─────────────
        new()
        {
            Id = "widgets", Category = "DÉBLOAT", Name = "Widgets et actualités désactivés",
            Description = "Retire le panneau Widgets de la barre des tâches et son processus en arrière-plan.",
            Apply = () => Reg.Set(@"HKLM\SOFTWARE\Policies\Microsoft\Dsh", "AllowNewsAndInterests", 0),
            Revert = () => Reg.Del(@"HKLM\SOFTWARE\Policies\Microsoft\Dsh", "AllowNewsAndInterests"),
        },
        new()
        {
            Id = "copilot", Category = "DÉBLOAT", Name = "Copilot désactivé",
            Description = "Désactive l'assistant Windows Copilot et son bouton.",
            Apply = () => Reg.Set(@"HKCU\Software\Policies\Microsoft\Windows\WindowsCopilot", "TurnOffWindowsCopilot", 1),
            Revert = () => Reg.Del(@"HKCU\Software\Policies\Microsoft\Windows\WindowsCopilot", "TurnOffWindowsCopilot"),
        },
        new()
        {
            Id = "consumer", Category = "DÉBLOAT", Name = "Applications sponsorisées bloquées",
            Description = "Empêche Windows d'installer automatiquement des applications et jeux promotionnels.",
            Apply = () => Reg.Set(@"HKLM\SOFTWARE\Policies\Microsoft\Windows\CloudContent", "DisableWindowsConsumerFeatures", 1),
            Revert = () => Reg.Del(@"HKLM\SOFTWARE\Policies\Microsoft\Windows\CloudContent", "DisableWindowsConsumerFeatures"),
        },
        new()
        {
            Id = "tips", Category = "DÉBLOAT", Name = "Suggestions et publicités retirées",
            Description = "Coupe les suggestions du menu Démarrer, les astuces et l'identifiant publicitaire.",
            Apply = () =>
            {
                const string k = @"HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager";
                foreach (var n in new[] { "SubscribedContent-338388Enabled", "SubscribedContent-338389Enabled", "SubscribedContent-310093Enabled", "SystemPaneSuggestionsEnabled", "SilentInstalledAppsEnabled", "OemPreInstalledAppsEnabled" })
                    Reg.Set(k, n, 0);
                Reg.Set(@"HKCU\Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo", "Enabled", 0);
            },
            Revert = () =>
            {
                const string k = @"HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager";
                foreach (var n in new[] { "SubscribedContent-338388Enabled", "SubscribedContent-338389Enabled", "SubscribedContent-310093Enabled", "SystemPaneSuggestionsEnabled", "SilentInstalledAppsEnabled", "OemPreInstalledAppsEnabled" })
                    Reg.Set(k, n, 1);
                Reg.Set(@"HKCU\Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo", "Enabled", 1);
            },
        },
        new()
        {
            Id = "bing", Category = "DÉBLOAT", Name = "Recherche web retirée du menu Démarrer",
            Description = "La recherche Windows ne contacte plus Bing : résultats plus rapides, moins de réseau.",
            Apply = () => Reg.Set(@"HKCU\Software\Policies\Microsoft\Windows\Explorer", "DisableSearchBoxSuggestions", 1),
            Revert = () => Reg.Del(@"HKCU\Software\Policies\Microsoft\Windows\Explorer", "DisableSearchBoxSuggestions"),
        },
        new()
        {
            Id = "onedrive", Category = "DÉBLOAT", Name = "OneDrive désactivé", Recommended = false,
            Description = "Désactive la synchronisation OneDrive. À éviter si tu utilises OneDrive pour sauvegarder tes fichiers.",
            Apply = () => Reg.Set(@"HKLM\SOFTWARE\Policies\Microsoft\Windows\OneDrive", "DisableFileSyncNGSC", 1),
            Revert = () => Reg.Del(@"HKLM\SOFTWARE\Policies\Microsoft\Windows\OneDrive", "DisableFileSyncNGSC"),
        },
        new()
        {
            Id = "edge", Category = "DÉBLOAT", Name = "Edge ne tourne plus en fond",
            Description = "Coupe le démarrage anticipé et le mode arrière-plan de Microsoft Edge.",
            Apply = () =>
            {
                Reg.Set(@"HKLM\SOFTWARE\Policies\Microsoft\Edge", "BackgroundModeEnabled", 0);
                Reg.Set(@"HKLM\SOFTWARE\Policies\Microsoft\Edge", "StartupBoostEnabled", 0);
            },
            Revert = () =>
            {
                Reg.Del(@"HKLM\SOFTWARE\Policies\Microsoft\Edge", "BackgroundModeEnabled");
                Reg.Del(@"HKLM\SOFTWARE\Policies\Microsoft\Edge", "StartupBoostEnabled");
            },
        },

        // ───────────── Services ─────────────
        new()
        {
            Id = "svcwer", Category = "SERVICES", Name = "Rapport d'erreurs Windows",
            Description = "Arrête l'envoi de rapports de plantage à Microsoft.",
            Apply = () => Svc("disabled", "WerSvc"),
            Revert = () => Svc("demand", "WerSvc"),
        },
        new()
        {
            Id = "svcloc", Category = "SERVICES", Name = "Service de localisation",
            Description = "Désactive la géolocalisation du PC, inutile pour jouer.",
            Apply = () => Svc("disabled", "lfsvc"),
            Revert = () => Svc("demand", "lfsvc"),
        },
        new()
        {
            Id = "svcsys", Category = "SERVICES", Name = "SysMain (Superfetch)", Recommended = false,
            Description = "Préchargement en mémoire. Utile sur disque dur, superflu sur SSD : à désactiver seulement si tu as un SSD.",
            Apply = () => Svc("disabled", "SysMain"),
            Revert = () => Svc("auto", "SysMain"),
        },
        new()
        {
            Id = "svcsearch", Category = "SERVICES", Name = "Indexation de la recherche", Recommended = false,
            Description = "Arrête l'indexation des fichiers en arrière-plan. La recherche de fichiers devient plus lente.",
            Apply = () => Svc("disabled", "WSearch"),
            Revert = () => Svc("delayed-auto", "WSearch"),
        },
        new()
        {
            Id = "svcxbox", Category = "SERVICES", Name = "Services Xbox", Recommended = false,
            Description = "Désactive les services Xbox. À éviter si tu utilises Xbox Game Pass ou l'application Xbox.",
            Apply = () => Svc("disabled", "XblAuthManager", "XblGameSave", "XboxNetApiSvc", "XboxGipSvc"),
            Revert = () => Svc("demand", "XblAuthManager", "XblGameSave", "XboxNetApiSvc", "XboxGipSvc"),
        },
        new()
        {
            Id = "svcprint", Category = "SERVICES", Name = "Spouleur d'impression", Recommended = false,
            Description = "Désactive l'impression. À faire seulement si tu n'utilises aucune imprimante.",
            Apply = () => Svc("disabled", "Spooler"),
            Revert = () => Svc("auto", "Spooler"),
        },

        // ───────────── Optimiseur d'applications ─────────────
        new()
        {
            Id = "appbrowser", Category = "APPS", Name = "Navigateurs en priorité réduite",
            Description = "Chrome, Edge et Firefox passent en priorité sous la normale : ils ne volent plus de CPU au jeu.",
            Apply = () => { foreach (var e in new[] { "chrome.exe", "msedge.exe", "firefox.exe" }) Reg.Set(IfeoRoot + e + @"\PerfOptions", "CpuPriorityClass", 5); },
            Revert = () => { foreach (var e in new[] { "chrome.exe", "msedge.exe", "firefox.exe" }) Reg.DelKey(IfeoRoot + e + @"\PerfOptions"); },
        },
        new()
        {
            Id = "applauncher", Category = "APPS", Name = "Lanceurs de jeux en priorité réduite",
            Description = "Epic Games Launcher, Steam et Battle.net consomment moins de CPU pendant que tu joues.",
            Apply = () => { foreach (var e in Launchers) Reg.Set(IfeoRoot + e + @"\PerfOptions", "CpuPriorityClass", 5); },
            Revert = () => { foreach (var e in Launchers) Reg.DelKey(IfeoRoot + e + @"\PerfOptions"); },
        },
    };

    /// <summary>Supprime les fichiers temporaires. Renvoie le nombre de Mo libérés.</summary>
    public static long CleanTemp()
    {
        long freed = 0;
        foreach (var dir in new[] { Path.GetTempPath(), Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows), "Temp") })
        {
            if (!Directory.Exists(dir)) continue;
            foreach (var f in Directory.EnumerateFiles(dir, "*", SearchOption.AllDirectories))
            {
                try { long len = new FileInfo(f).Length; File.Delete(f); freed += len; } catch { }
            }
        }
        return freed / (1024 * 1024);
    }
}
