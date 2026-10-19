namespace Blatja.Core;

public enum RegKind { DWord, String, Binary }

/// <summary>Valeur de registre typée, comparable indépendamment de la représentation (int / uint).</summary>
public readonly record struct RegValue(RegKind Kind, object Data)
{
    public static RegValue DWord(int v) => new(RegKind.DWord, v);
    public static RegValue DWordU(uint v) => new(RegKind.DWord, unchecked((int)v));
    public static RegValue Str(string v) => new(RegKind.String, v);
    public static RegValue Bin(byte[] v) => new(RegKind.Binary, v);

    public bool SameAs(RegValue other)
    {
        if (Kind != other.Kind) return false;
        return Kind switch
        {
            RegKind.DWord => unchecked((uint)Convert.ToInt64(Data)) == unchecked((uint)Convert.ToInt64(other.Data)),
            RegKind.String => string.Equals((string)Data, (string)other.Data, StringComparison.OrdinalIgnoreCase),
            _ => ((byte[])Data).AsSpan().SequenceEqual((byte[])other.Data),
        };
    }

    public override string ToString() => Kind switch
    {
        RegKind.DWord => Convert.ToInt64(Data).ToString(),
        RegKind.String => $"\"{Data}\"",
        _ => BitConverter.ToString((byte[])Data),
    };
}

/// <summary>Accès au registre. Les chemins commencent par HKLM\ ou HKCU\.</summary>
public interface IRegistry
{
    RegValue? Get(string path, string name);
    void Set(string path, string name, RegValue value);
    void DeleteValue(string path, string name);
    void DeleteKey(string path);
    bool KeyExists(string path);
    IReadOnlyList<string> SubKeys(string path);
    IReadOnlyList<string> ValueNames(string path);
}

public sealed record ProcessResult(int ExitCode, string Output)
{
    public bool Ok => ExitCode == 0;
}

/// <summary>Lancement de programmes externes (sans shell, arguments fournis par le code uniquement).</summary>
public interface IProcessRunner
{
    ProcessResult Run(string file, string args, int timeoutMs = 30000);
}

public interface IFileSystem
{
    bool FileExists(string path);
    bool DirectoryExists(string path);
    string ReadAllText(string path);
    void WriteAllText(string path, string text);
    void Copy(string from, string to, bool overwrite);
    IEnumerable<string> EnumerateFiles(string dir, string pattern, bool recursive = false);
    IEnumerable<string> EnumerateDirectories(string dir);
}

public interface ISystemInfo
{
    /// <summary>Numéro de build Windows (ex. 19045 = Windows 10 22H2, 22631 = Windows 11 23H2).</summary>
    int Build { get; }
    bool IsAdmin { get; }
    string Description { get; }
}

public static class SystemInfoExtensions
{
    public static bool IsWindows11(this ISystemInfo i) => i.Build >= 22000;
}

/// <summary>Ensemble des accès système utilisés par les opérations. Remplacé par des doublures dans les tests.</summary>
public sealed record SystemContext(IRegistry Registry, IProcessRunner Runner, IFileSystem Files, ISystemInfo Info);
