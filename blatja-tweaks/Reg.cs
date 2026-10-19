using Microsoft.Win32;

namespace BlatjaTweaks;

/// <summary>Accès registre : les chemins commencent par HKLM\ ou HKCU\.</summary>
internal static class Reg
{
    public static void Set(string path, string name, object value, RegistryValueKind kind = RegistryValueKind.DWord)
    {
        using var key = Open(path, create: true)!;
        key.SetValue(name, value, kind);
    }

    public static void Del(string path, string name)
    {
        using var key = Open(path, create: false);
        key?.DeleteValue(name, throwOnMissingValue: false);
    }

    public static void DelKey(string path)
    {
        int i = path.LastIndexOf('\\');
        using var parent = Open(path[..i], create: false);
        parent?.DeleteSubKeyTree(path[(i + 1)..], throwOnMissingSubKey: false);
    }

    public static string[] SubKeys(string path)
    {
        using var key = Open(path, create: false);
        return key?.GetSubKeyNames() ?? Array.Empty<string>();
    }

    public static object? Get(string path, string name)
    {
        using var key = Open(path, create: false);
        return key?.GetValue(name);
    }

    private static RegistryKey? Open(string path, bool create)
    {
        int i = path.IndexOf('\\');
        var root = path[..i] switch
        {
            "HKLM" => Registry.LocalMachine,
            "HKCU" => Registry.CurrentUser,
            _ => throw new ArgumentException("Ruche inconnue : " + path),
        };
        string sub = path[(i + 1)..];
        return create ? root.CreateSubKey(sub, writable: true) : root.OpenSubKey(sub, writable: true);
    }
}
