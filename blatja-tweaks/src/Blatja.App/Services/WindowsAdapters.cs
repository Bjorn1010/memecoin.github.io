using System.Diagnostics;
using System.Security.Principal;
using Blatja.Core;
using Microsoft.Win32;

namespace Blatja.App.Services;

/// <summary>Registre Windows réel (vue 64 bits). Les chemins commencent par HKLM\ ou HKCU\.</summary>
public sealed class WinRegistry : IRegistry
{
    private static RegistryKey? Open(string path, bool write, bool create)
    {
        int i = path.IndexOf('\\');
        var hive = path[..i] switch
        {
            "HKLM" => RegistryHive.LocalMachine,
            "HKCU" => RegistryHive.CurrentUser,
            _ => throw new ArgumentException("Ruche non prise en charge : " + path),
        };
        using var root = RegistryKey.OpenBaseKey(hive, RegistryView.Registry64);
        string sub = path[(i + 1)..];
        return create ? root.CreateSubKey(sub, writable: true) : root.OpenSubKey(sub, writable: write);
    }

    public RegValue? Get(string path, string name)
    {
        using var k = Open(path, false, false);
        if (k is null) return null;
        var v = k.GetValue(name, null, RegistryValueOptions.DoNotExpandEnvironmentNames);
        if (v is null) return null;
        return k.GetValueKind(name) switch
        {
            RegistryValueKind.DWord => RegValue.DWord((int)v),
            RegistryValueKind.String or RegistryValueKind.ExpandString => RegValue.Str((string)v),
            RegistryValueKind.Binary => RegValue.Bin((byte[])v),
            _ => null,
        };
    }

    public void Set(string path, string name, RegValue value)
    {
        using var k = Open(path, true, true)!;
        switch (value.Kind)
        {
            case RegKind.DWord: k.SetValue(name, Convert.ToInt32(value.Data), RegistryValueKind.DWord); break;
            case RegKind.String: k.SetValue(name, (string)value.Data, RegistryValueKind.String); break;
            default: k.SetValue(name, (byte[])value.Data, RegistryValueKind.Binary); break;
        }
    }

    public void DeleteValue(string path, string name)
    {
        using var k = Open(path, true, false);
        k?.DeleteValue(name, throwOnMissingValue: false);
    }

    public void DeleteKey(string path)
    {
        int i = path.LastIndexOf('\\');
        using var parent = Open(path[..i], true, false);
        parent?.DeleteSubKeyTree(path[(i + 1)..], throwOnMissingSubKey: false);
    }

    public bool KeyExists(string path) { using var k = Open(path, false, false); return k is not null; }

    public IReadOnlyList<string> SubKeys(string path) { using var k = Open(path, false, false); return k?.GetSubKeyNames() ?? Array.Empty<string>(); }

    public IReadOnlyList<string> ValueNames(string path) { using var k = Open(path, false, false); return k?.GetValueNames().Where(n => n.Length > 0).ToArray() ?? Array.Empty<string>(); }
}

/// <summary>Lance un programme sans shell ni fenêtre. Les arguments proviennent uniquement du code, jamais d'une saisie utilisateur.</summary>
public sealed class WinRunner : IProcessRunner
{
    public ProcessResult Run(string file, string args, int timeoutMs = 30000)
    {
        var psi = new ProcessStartInfo(file, args)
        {
            UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardOutput = true, RedirectStandardError = true,
        };
        try
        {
            using var p = Process.Start(psi) ?? throw new InvalidOperationException("Impossible de lancer " + file);
            var stdout = p.StandardOutput.ReadToEndAsync();
            var stderr = p.StandardError.ReadToEndAsync();
            if (!p.WaitForExit(timeoutMs))
            {
                try { p.Kill(true); } catch { }
                return new ProcessResult(-1, file + " ne répond pas (délai dépassé)");
            }
            return new ProcessResult(p.ExitCode, (stdout.Result + stderr.Result).Trim());
        }
        catch (System.ComponentModel.Win32Exception ex)
        {
            return new ProcessResult(-2, $"{file} introuvable : {ex.Message}");
        }
    }
}

public sealed class WinFiles : IFileSystem
{
    public bool FileExists(string path) => File.Exists(path);
    public bool DirectoryExists(string path) => Directory.Exists(path);
    public string ReadAllText(string path) => File.ReadAllText(path);
    public void WriteAllText(string path, string text) => File.WriteAllText(path, text);
    public void Copy(string from, string to, bool overwrite) { if (overwrite || !File.Exists(to)) File.Copy(from, to, overwrite); }
    public IEnumerable<string> EnumerateFiles(string dir, string pattern, bool recursive = false) =>
        Directory.Exists(dir) ? Directory.EnumerateFiles(dir, pattern, recursive ? SearchOption.AllDirectories : SearchOption.TopDirectoryOnly) : Array.Empty<string>();
    public IEnumerable<string> EnumerateDirectories(string dir) => Directory.Exists(dir) ? Directory.EnumerateDirectories(dir) : Array.Empty<string>();
}

public sealed class WinInfo : ISystemInfo
{
    public int Build { get; } = Environment.OSVersion.Version.Build;
    /// <summary>BLATJA_READONLY=1 force le mode lecture seule (réduit les droits, ne peut jamais en ajouter).</summary>
    public bool IsAdmin { get; } = Environment.GetEnvironmentVariable("BLATJA_READONLY") != "1"
        && new WindowsPrincipal(WindowsIdentity.GetCurrent()).IsInRole(WindowsBuiltInRole.Administrator);
    public string Description => $"{(Build >= 22000 ? "Windows 11" : "Windows 10")} (build {Build})";
}
