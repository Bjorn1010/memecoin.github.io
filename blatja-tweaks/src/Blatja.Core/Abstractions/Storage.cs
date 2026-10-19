using System.Text.Json;

namespace Blatja.Core;

/// <summary>Valeur d'origine d'une entrée de registre, capturée avant modification.</summary>
public sealed class BackupEntry
{
    public string Path { get; set; } = "";
    public string Name { get; set; } = "";
    public bool Existed { get; set; }
    public RegKind Kind { get; set; }
    /// <summary>DWord : nombre ; String : texte ; Binary : base64.</summary>
    public string? Text { get; set; }

    public static BackupEntry From(string path, string name, RegValue? v) => new()
    {
        Path = path, Name = name, Existed = v is not null, Kind = v?.Kind ?? RegKind.DWord,
        Text = v is null ? null : v.Value.Kind switch
        {
            RegKind.DWord => Convert.ToInt64(v.Value.Data).ToString(),
            RegKind.String => (string)v.Value.Data,
            _ => Convert.ToBase64String((byte[])v.Value.Data),
        },
    };

    public RegValue? ToValue()
    {
        if (!Existed || Text is null) return null;
        return Kind switch
        {
            RegKind.DWord => RegValue.DWordU(unchecked((uint)long.Parse(Text))),
            RegKind.String => RegValue.Str(Text),
            _ => RegValue.Bin(Convert.FromBase64String(Text)),
        };
    }
}

public sealed class BackupRecord
{
    public string OpId { get; set; } = "";
    public DateTime CreatedAt { get; set; } = DateTime.Now;
    public List<BackupEntry> Entries { get; set; } = new();
    /// <summary>Données propres à une opération (ancien plan d'alimentation, type de démarrage d'un service…).</summary>
    public Dictionary<string, string> Extra { get; set; } = new();
}

public interface IBackupStore
{
    void Save(BackupRecord record);
    BackupRecord? Load(string opId);
    void Remove(string opId);
    IReadOnlyList<BackupRecord> All();
}

public enum JournalOutcome { Succeeded, Skipped, Failed, VerificationFailed, Refused, Cancelled }

public sealed record JournalEntry(DateTime Time, string OpId, string OpName, string Action, JournalOutcome Outcome, string Message);

public interface IJournal
{
    void Append(JournalEntry entry);
    IReadOnlyList<JournalEntry> Recent(int max = 200);
}

/// <summary>Sauvegardes JSON : un fichier par opération.</summary>
public sealed class JsonBackupStore : IBackupStore
{
    private readonly string _dir;
    private static readonly JsonSerializerOptions Opts = new() { WriteIndented = true };

    public JsonBackupStore(string directory) { _dir = directory; }

    private string FileFor(string id) => System.IO.Path.Combine(_dir, id + ".json");

    public void Save(BackupRecord record)
    {
        Directory.CreateDirectory(_dir);
        string tmp = FileFor(record.OpId) + ".tmp";
        File.WriteAllText(tmp, JsonSerializer.Serialize(record, Opts));
        File.Move(tmp, FileFor(record.OpId), overwrite: true);   // écriture atomique
    }

    public BackupRecord? Load(string opId)
    {
        try { return File.Exists(FileFor(opId)) ? JsonSerializer.Deserialize<BackupRecord>(File.ReadAllText(FileFor(opId))) : null; }
        catch (JsonException) { return null; }
    }

    public void Remove(string opId) { try { File.Delete(FileFor(opId)); } catch (IOException) { } }

    public IReadOnlyList<BackupRecord> All()
    {
        if (!Directory.Exists(_dir)) return Array.Empty<BackupRecord>();
        var list = new List<BackupRecord>();
        foreach (var f in Directory.EnumerateFiles(_dir, "*.json"))
        {
            try { if (JsonSerializer.Deserialize<BackupRecord>(File.ReadAllText(f)) is { } r) list.Add(r); } catch (JsonException) { }
        }
        return list;
    }
}

/// <summary>Journal des modifications : une ligne JSON par événement, tolérant aux lignes corrompues.</summary>
public sealed class FileJournal : IJournal
{
    private readonly string _file;
    private readonly object _lock = new();

    public FileJournal(string file) { _file = file; }

    public void Append(JournalEntry e)
    {
        lock (_lock)
        {
            Directory.CreateDirectory(System.IO.Path.GetDirectoryName(_file)!);
            File.AppendAllText(_file, JsonSerializer.Serialize(e) + Environment.NewLine);
        }
    }

    public IReadOnlyList<JournalEntry> Recent(int max = 200)
    {
        lock (_lock)
        {
            if (!File.Exists(_file)) return Array.Empty<JournalEntry>();
            var list = new List<JournalEntry>();
            foreach (var line in File.ReadLines(_file))
            {
                try { if (JsonSerializer.Deserialize<JournalEntry>(line) is { } e) list.Add(e); } catch (JsonException) { }
            }
            list.Reverse();
            return list.Take(max).ToList();
        }
    }
}
