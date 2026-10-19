namespace Blatja.Core;

/// <summary>État réel d'une optimisation sur le système (jamais l'état d'un bouton).</summary>
public enum OpState { Enabled, Disabled, NotApplicable, Unknown, Error }
public enum Impact { None, Low, Medium, High }
/// <summary>Il n'existe volontairement pas de niveau « élevé » : une opération dangereuse est refusée, pas avertie.</summary>
public enum Risk { Low, Medium }
public enum OpAction { Apply, Revert }
public enum RestartKind { None, SignOut, Reboot }

public readonly record struct Applicability(bool Ok, string? Reason)
{
    public static readonly Applicability Yes = new(true, null);
    public static Applicability No(string reason) => new(false, reason);
}

/// <summary>
/// Opération d'optimisation identifiée et documentée.
/// Cycle : Detect → Capture (valeurs d'origine) → Apply → Detect (vérification) ; Revert restaure la capture.
/// </summary>
public abstract class Operation
{
    public required string Id { get; init; }
    public required string Name { get; init; }
    /// <summary>Ce que fait l'optimisation, en langage clair.</summary>
    public required string Description { get; init; }
    /// <summary>Effet réel sur Windows (clé modifiée, service arrêté…).</summary>
    public required string Effect { get; init; }
    public string Drawbacks { get; init; } = "Aucun inconvénient connu.";
    /// <summary>Page d'affichage : GAMING, CPU, GPU, MEMOIRE, RESEAU, STOCKAGE, DEBLOAT.</summary>
    public required string Category { get; init; }
    public string Group { get; init; } = "";
    public Impact Impact { get; init; } = Impact.Low;
    public Risk Risk { get; init; } = Risk.Low;
    public RestartKind Restart { get; init; } = RestartKind.None;
    public bool RequiresAdmin { get; init; } = true;
    public bool Recommended { get; init; } = true;
    public int MinBuild { get; init; }

    /// <summary>Vrai si l'état d'origine de Windows équivaut déjà à l'optimisation : la restauration y ramène sans la « désactiver ».</summary>
    public virtual bool EnabledIsDefault => false;

    public virtual Applicability CheckApplicable(SystemContext c) =>
        c.Info.Build >= MinBuild ? Applicability.Yes : Applicability.No($"Nécessite Windows (build {MinBuild} ou plus) — build détecté : {c.Info.Build}.");

    /// <summary>Ressources touchées, sous la forme « reg:CHEMIN|Nom » ou « svc:Nom ». Sert à la politique de sécurité.</summary>
    public abstract IEnumerable<string> Targets(SystemContext c);

    public abstract OpState Detect(SystemContext c);
    public abstract void Capture(SystemContext c, BackupRecord backup);
    public abstract void Apply(SystemContext c);
    /// <param name="backup">Capture d'avant modification, ou null si l'optimisation a été activée en dehors de Blatja.</param>
    public abstract void Revert(SystemContext c, BackupRecord? backup);
}

/// <summary>Refuse toute opération qui toucherait à un mécanisme de sécurité ou à un composant critique de Windows.</summary>
public static class SafetyPolicy
{
    private static readonly string[] ForbiddenServices =
    {
        "WinDefend", "WdNisSvc", "WdNisDrv", "WdFilter", "Sense", "SecurityHealthService", "wscsvc",
        "mpssvc", "BFE", "SharedAccess", "wuauserv", "UsoSvc", "WaaSMedicSvc", "BITS", "TrustedInstaller",
        "EventLog", "RpcSs", "DcomLaunch", "RpcEptMapper", "LSM", "Winmgmt", "CryptSvc", "SamSs", "Schedule", "gpsvc", "ProfSvc", "Dhcp", "Dnscache", "NlaSvc",
    };

    private static readonly string[] ForbiddenRegistryPrefixes =
    {
        @"HKLM\SOFTWARE\Microsoft\Windows Defender",
        @"HKLM\SOFTWARE\Policies\Microsoft\Windows Defender",
        @"HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate",
        @"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate",
        @"HKLM\SOFTWARE\Policies\Microsoft\WindowsFirewall",
        @"HKLM\SYSTEM\CurrentControlSet\Services\SharedAccess",
        @"HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard",
        @"HKLM\SYSTEM\CurrentControlSet\Control\Lsa",
        @"HKLM\SOFTWARE\Policies\Microsoft\Windows\System\EnableSmartScreen",
        @"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System",
        @"HKLM\SYSTEM\CurrentControlSet\Control\CI",
    };

    /// <summary>Renvoie la raison du refus, ou null si l'opération est autorisée.</summary>
    public static string? Violation(Operation op, SystemContext c)
    {
        foreach (var t in op.Targets(c))
        {
            if (t.StartsWith("svc:", StringComparison.Ordinal))
            {
                string name = t[4..];
                if (ForbiddenServices.Contains(name, StringComparer.OrdinalIgnoreCase))
                    return $"Le service « {name} » est un composant de sécurité ou critique de Windows.";
            }
            else if (t.StartsWith("reg:", StringComparison.Ordinal))
            {
                string path = t[4..].Split('|')[0];
                foreach (var p in ForbiddenRegistryPrefixes)
                    if (path.StartsWith(p, StringComparison.OrdinalIgnoreCase))
                        return $"La clé « {path} » est liée à la sécurité de Windows.";
            }
        }
        return null;
    }
}
