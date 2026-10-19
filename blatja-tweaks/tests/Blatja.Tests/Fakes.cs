using Blatja.Core;

namespace Blatja.Tests;

public sealed class FakeRegistry : IRegistry
{
    private readonly Dictionary<(string, string), RegValue> _v = new();
    private readonly Dictionary<(string, string), string> _names = new();
    private readonly HashSet<string> _keys = new(StringComparer.OrdinalIgnoreCase);
    public bool ThrowOnSet { get; set; }
    public Func<string, string, bool>? FailSetWhen { get; set; }

    private static (string, string) K(string p, string n) => (p.ToLowerInvariant(), n.ToLowerInvariant());

    public RegValue? Get(string path, string name) => _v.TryGetValue(K(path, name), out var v) ? v : null;

    public void Set(string path, string name, RegValue value)
    {
        if (ThrowOnSet || (FailSetWhen?.Invoke(path, name) ?? false)) throw new UnauthorizedAccessException("accès refusé (test)");
        _v[K(path, name)] = value; _names[K(path, name)] = name; _keys.Add(path);
    }

    public void DeleteValue(string path, string name) { _v.Remove(K(path, name)); _names.Remove(K(path, name)); }
    public void DeleteKey(string path)
    {
        _keys.Remove(path);
        foreach (var k in _v.Keys.Where(k => k.Item1.StartsWith(path.ToLowerInvariant())).ToList()) _v.Remove(k);
    }
    public bool KeyExists(string path) => _keys.Contains(path) || _v.Keys.Any(k => k.Item1.StartsWith(path.ToLowerInvariant()));
    public IReadOnlyList<string> SubKeys(string path)
    {
        string prefix = path.ToLowerInvariant().TrimEnd('\\') + "\\";
        return _v.Keys.Select(k => k.Item1).Concat(_keys.Select(k => k.ToLowerInvariant()))
            .Where(p => p.StartsWith(prefix)).Select(p => p[prefix.Length..].Split('\\')[0]).Distinct().ToList();
    }
    public IReadOnlyList<string> ValueNames(string path) =>
        _v.Keys.Where(k => k.Item1 == path.ToLowerInvariant()).Select(k => _names.GetValueOrDefault(k, k.Item2)).ToList();

    public void Seed(string path, string name, RegValue v) { _v[K(path, name)] = v; _names[K(path, name)] = name; _keys.Add(path); }
}

public sealed class FakeRunner : IProcessRunner
{
    public List<string> Calls { get; } = new();
    public Func<string, string, ProcessResult>? Handler { get; set; }
    public ProcessResult Run(string file, string args, int timeoutMs = 30000)
    {
        Calls.Add($"{file} {args}");
        return Handler?.Invoke(file, args) ?? new ProcessResult(0, "");
    }
}

public sealed class FakeFiles : IFileSystem
{
    public Dictionary<string, string> Files { get; } = new(StringComparer.OrdinalIgnoreCase);
    public HashSet<string> Dirs { get; } = new(StringComparer.OrdinalIgnoreCase);
    public bool FileExists(string path) => Files.ContainsKey(path);
    public bool DirectoryExists(string path) => Dirs.Contains(path) || Files.Keys.Any(f => f.StartsWith(path + "\\", StringComparison.OrdinalIgnoreCase));
    public string ReadAllText(string path) => Files.TryGetValue(path, out var t) ? t : throw new FileNotFoundException(path);
    public void WriteAllText(string path, string text) => Files[path] = text;
    public void Copy(string from, string to, bool overwrite)
    {
        if (!overwrite && Files.ContainsKey(to)) return;
        Files[to] = Files[from];
    }
    public IEnumerable<string> EnumerateFiles(string dir, string pattern, bool recursive = false)
    {
        string rx = "^" + System.Text.RegularExpressions.Regex.Escape(pattern).Replace("\\*", ".*") + "$";
        return Files.Keys.Where(f => f.StartsWith(dir.TrimEnd('\\') + "\\", StringComparison.OrdinalIgnoreCase)
            && !f[(dir.TrimEnd('\\').Length + 1)..].Contains('\\')
            && System.Text.RegularExpressions.Regex.IsMatch(f[(f.LastIndexOf('\\') + 1)..], rx, System.Text.RegularExpressions.RegexOptions.IgnoreCase)).ToList();
    }
    public IEnumerable<string> EnumerateDirectories(string dir) => Array.Empty<string>();
}

public sealed class FakeInfo : ISystemInfo
{
    public int Build { get; set; } = 22631;
    public bool IsAdmin { get; set; } = true;
    public string Description => "Windows (test)";
}

public sealed class MemBackups : IBackupStore
{
    public Dictionary<string, BackupRecord> Items { get; } = new();
    public void Save(BackupRecord r) => Items[r.OpId] = r;
    public BackupRecord? Load(string id) => Items.TryGetValue(id, out var r) ? r : null;
    public void Remove(string id) => Items.Remove(id);
    public IReadOnlyList<BackupRecord> All() => Items.Values.ToList();
}

public sealed class MemJournal : IJournal
{
    public List<JournalEntry> Entries { get; } = new();
    public void Append(JournalEntry e) => Entries.Add(e);
    public IReadOnlyList<JournalEntry> Recent(int max = 200) => Entries.AsEnumerable().Reverse().Take(max).ToList();
}

public sealed class Env
{
    public FakeRegistry Reg { get; } = new();
    public FakeRunner Runner { get; } = new();
    public FakeFiles Files { get; } = new();
    public FakeInfo Info { get; } = new();
    public MemBackups Backups { get; } = new();
    public MemJournal Journal { get; } = new();
    public SystemContext Ctx => new(Reg, Runner, Files, Info);
    public OptimizationEngine Engine => new(Ctx, Backups, Journal);
}

public sealed class CustomOp : Operation
{
    public Func<SystemContext, OpState> DetectFn { get; init; } = _ => OpState.Disabled;
    public Action<SystemContext>? ApplyFn { get; init; }
    public Action<SystemContext, BackupRecord?>? RevertFn { get; init; }
    public string[] TargetList { get; init; } = Array.Empty<string>();
    public override IEnumerable<string> Targets(SystemContext c) => TargetList;
    public override OpState Detect(SystemContext c) => DetectFn(c);
    public override void Capture(SystemContext c, BackupRecord b) => b.Extra["captured"] = "1";
    public override void Apply(SystemContext c) => ApplyFn?.Invoke(c);
    public override void Revert(SystemContext c, BackupRecord? b) => RevertFn?.Invoke(c, b);

    public static CustomOp Make(string id, Func<SystemContext, OpState> detect, Action<SystemContext>? apply = null, bool admin = false, params string[] targets) => new()
    {
        Id = id, Name = id, Description = "d", Effect = "e", Category = Categories.Gaming, DetectFn = detect, ApplyFn = apply, RequiresAdmin = admin, TargetList = targets,
    };
}
