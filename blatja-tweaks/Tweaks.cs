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

    private static string RequireFortniteExe() =>
        Fortnite.FindExe() ?? throw new FileNotFoundException("Fortnite introuvable (Epic Games Launcher).");

    public static List<Tweak> Build() => new()
    {
        // ───────────── Système ─────────────
        new()
        {
            Id = "power", Category = "SYSTÈME", Name = "Plan d'alimentation « Performances ultimes »",
            Description = "Empêche le processeur de baisser sa fréquence pendant le jeu.",
            Apply = () =>
            {
                var r = Sh.Run("powercfg", $"-duplicatescheme {UltimateScheme} {BlatjaScheme}");
                string guid = r.Code == 0 ? BlatjaScheme : HighPerfScheme;
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
            Id = "gamemode", Category = "SYSTÈME", Name = "Mode Jeu Windows",
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
            Id = "gamedvr", Category = "SYSTÈME", Name = "Désactiver la capture Xbox / Game DVR",
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
            Id = "hags", Category = "SYSTÈME", Name = "Planification GPU accélérée (HAGS)", NeedsReboot = true,
            Description = "Réduit la latence CPU→GPU. Nécessite une carte récente (NVIDIA GTX 1000+ / AMD RX 5000+).",
            Apply = () => Reg.Set(@"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode", 2),
            Revert = () => Reg.Del(@"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode"),
        },
        new()
        {
            Id = "timer", Category = "SYSTÈME", Name = "Résolution du minuteur système", NeedsReboot = true,
            Description = "Autorise les jeux à demander un minuteur précis : frametimes plus réguliers.",
            Apply = () => Reg.Set(@"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\kernel", "GlobalTimerResolutionRequests", 1),
            Revert = () => Reg.Del(@"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\kernel", "GlobalTimerResolutionRequests"),
        },
        new()
        {
            Id = "prio", Category = "SYSTÈME", Name = "Priorité CPU au programme actif",
            Description = "Win32PrioritySeparation = 0x26 : le jeu au premier plan passe avant les tâches de fond.",
            Apply = () => Reg.Set(@"HKLM\SYSTEM\CurrentControlSet\Control\PriorityControl", "Win32PrioritySeparation", 0x26),
            Revert = () => Reg.Set(@"HKLM\SYSTEM\CurrentControlSet\Control\PriorityControl", "Win32PrioritySeparation", 2),
        },
        new()
        {
            Id = "mmcss", Category = "SYSTÈME", Name = "Planificateur multimédia orienté jeux",
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
            Id = "visual", Category = "SYSTÈME", Name = "Effets visuels allégés",
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

        // ───────────── Entrées & réseau ─────────────
        new()
        {
            Id = "mouse", Category = "ENTRÉES & RÉSEAU", Name = "Désactiver l'accélération de la souris",
            Description = "Précision 1:1 : la visée devient constante, indispensable en compétitif.",
            Apply = () => SetMouse(0, 0, 0),
            Revert = () => SetMouse(1, 6, 10),
        },
        new()
        {
            Id = "nagle", Category = "ENTRÉES & RÉSEAU", Name = "Latence réseau réduite (Nagle off)",
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
            Id = "fnprio", Category = "FORTNITE", Name = "Priorité CPU « Haute » pour Fortnite",
            Description = "Windows lance Fortnite avec une priorité processeur élevée à chaque démarrage.",
            Apply = () => Reg.Set(Ifeo + @"\PerfOptions", "CpuPriorityClass", 3),
            Revert = () => Reg.DelKey(Ifeo + @"\PerfOptions"),
        },
        new()
        {
            Id = "fngpu", Category = "FORTNITE", Name = "GPU haute performance + plein écran exclusif",
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
            Id = "fnini", Category = "FORTNITE", Name = "Graphismes optimisés pour les FPS",
            Description = "Qualité minimale (ombres, effets, textures…), V-Sync et limite de FPS coupés. Sauvegarde auto.",
            Apply = Fortnite.ApplyLowSettings,
            Revert = Fortnite.RestoreSettings,
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
