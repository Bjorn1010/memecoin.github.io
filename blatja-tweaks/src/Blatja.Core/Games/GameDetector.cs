using System.Text.Json;
using System.Text.RegularExpressions;

namespace Blatja.Core;

public sealed record DetectedGame(string Key, string Name, string Launcher, string? InstallPath, string? ExePath, bool Known);

/// <summary>Détecte les jeux réellement installés (manifestes Epic, bibliothèques Steam, Riot, Minecraft). Rien n'est supposé.</summary>
public sealed class GameDetector
{
    private readonly SystemContext _c;
    private readonly string _programData;
    private readonly string _appData;

    private static readonly Dictionary<string, (string Key, string Name)> SteamKnown = new()
    {
        ["730"] = ("cs2", "Counter-Strike 2"),
        ["1172470"] = ("apex", "Apex Legends"),
    };

    private static readonly string[] NotGames = { "Steamworks", "Proton", "Steam Linux Runtime", "Redistributable", "Wallpaper Engine" };

    public GameDetector(SystemContext c, string programData = @"C:\ProgramData", string appData = "")
    {
        _c = c; _programData = programData; _appData = appData;
    }

    private static string J(params string[] parts) => string.Join('\\', parts.Select(p => p.TrimEnd('\\', '/')));

    public IReadOnlyList<DetectedGame> Detect()
    {
        var games = new List<DetectedGame>();
        TryAdd(games, DetectEpic);
        TryAdd(games, DetectSteam);
        TryAdd(games, DetectRiot);
        TryAdd(games, DetectMinecraft);
        return games.OrderByDescending(g => g.Known).ThenBy(g => g.Name, StringComparer.OrdinalIgnoreCase).ToList();
    }

    public DetectedGame? Find(string key) => Detect().FirstOrDefault(g => g.Key == key);

    private static void TryAdd(List<DetectedGame> list, Func<IEnumerable<DetectedGame>> source)
    {
        try { list.AddRange(source()); } catch (Exception) { /* un lanceur illisible ne doit pas masquer les autres */ }
    }

    private IEnumerable<DetectedGame> DetectEpic()
    {
        string dir = J(_programData, "Epic", "EpicGamesLauncher", "Data", "Manifests");
        if (!_c.Files.DirectoryExists(dir)) yield break;
        foreach (var f in _c.Files.EnumerateFiles(dir, "*.item"))
        {
            JsonElement r;
            try { r = JsonDocument.Parse(_c.Files.ReadAllText(f)).RootElement; } catch (JsonException) { continue; }
            string app = Str(r, "AppName"), name = Str(r, "DisplayName"), loc = Str(r, "InstallLocation");
            if (app.Length == 0 || loc.Length == 0) continue;
            if (r.TryGetProperty("bIsIncompleteInstall", out var inc) && inc.ValueKind == JsonValueKind.True) continue;
            bool isGame = r.TryGetProperty("AppCategories", out var cats) && cats.ValueKind == JsonValueKind.Array &&
                          cats.EnumerateArray().Any(c => string.Equals(c.GetString(), "games", StringComparison.OrdinalIgnoreCase));
            if (!isGame) continue;

            if (app.Equals("Fortnite", StringComparison.OrdinalIgnoreCase))
            {
                string exe = J(loc, "FortniteGame", "Binaries", "Win64", "FortniteClient-Win64-Shipping.exe");
                yield return new DetectedGame("fortnite", "Fortnite", "Epic Games", loc, _c.Files.FileExists(exe) ? exe : null, true);
            }
            else yield return new DetectedGame("epic:" + app, name.Length > 0 ? name : app, "Epic Games", loc, null, false);
        }
    }

    private IEnumerable<DetectedGame> DetectSteam()
    {
        string? steam = _c.Registry.Get(@"HKCU\Software\Valve\Steam", "SteamPath")?.Data as string;
        if (string.IsNullOrWhiteSpace(steam)) yield break;
        steam = steam.Replace('/', '\\');

        var libraries = new List<string> { steam };
        string vdf = J(steam, "steamapps", "libraryfolders.vdf");
        if (_c.Files.FileExists(vdf))
            foreach (Match m in Regex.Matches(_c.Files.ReadAllText(vdf), "\"path\"\\s+\"([^\"]+)\""))
                libraries.Add(m.Groups[1].Value.Replace("\\\\", "\\").Replace('/', '\\'));

        foreach (var lib in libraries.Distinct(StringComparer.OrdinalIgnoreCase))
        {
            string apps = J(lib, "steamapps");
            if (!_c.Files.DirectoryExists(apps)) continue;
            foreach (var f in _c.Files.EnumerateFiles(apps, "appmanifest_*.acf"))
            {
                string text = _c.Files.ReadAllText(f);
                string id = Acf(text, "appid"), name = Acf(text, "name"), dir = Acf(text, "installdir");
                if (id.Length == 0 || name.Length == 0 || NotGames.Any(n => name.Contains(n, StringComparison.OrdinalIgnoreCase))) continue;
                string path = J(apps, "common", dir);
                if (SteamKnown.TryGetValue(id, out var k)) yield return new DetectedGame(k.Key, k.Name, "Steam", path, null, true);
                else yield return new DetectedGame("steam:" + id, name, "Steam", path, null, false);
            }
        }
    }

    private IEnumerable<DetectedGame> DetectRiot()
    {
        foreach (var (sub, key, name) in new[] { ("Riot Game valorant.live", "valorant", "Valorant"), ("Riot Game league_of_legends.live", "lol", "League of Legends") })
        {
            string reg = $@"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{sub}";
            if (_c.Registry.Get(reg, "InstallLocation")?.Data is string loc && loc.Length > 0)
                yield return new DetectedGame(key, name, "Riot Games", loc, null, true);
        }
    }

    private IEnumerable<DetectedGame> DetectMinecraft()
    {
        if (_appData.Length == 0) yield break;
        string dir = J(_appData, ".minecraft");
        if (_c.Files.DirectoryExists(dir)) yield return new DetectedGame("minecraft", "Minecraft", "Minecraft Launcher", dir, null, true);
    }

    private static string Str(JsonElement e, string name) => e.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() ?? "" : "";
    private static string Acf(string text, string key) => Regex.Match(text, $"\"{key}\"\\s+\"([^\"]*)\"", RegexOptions.IgnoreCase) is { Success: true } m ? m.Groups[1].Value : "";
}
