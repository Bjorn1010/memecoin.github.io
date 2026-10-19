using System.Diagnostics;

namespace BlatjaTweaks;

internal static class Sh
{
    /// <summary>Lance un programme sans fenêtre et renvoie (code de sortie, sortie texte).</summary>
    public static (int Code, string Output) Run(string file, string args, int timeoutMs = 30000)
    {
        var psi = new ProcessStartInfo(file, args)
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };
        using var p = Process.Start(psi) ?? throw new InvalidOperationException("Impossible de lancer " + file);
        var stdout = p.StandardOutput.ReadToEndAsync();
        var stderr = p.StandardError.ReadToEndAsync();
        if (!p.WaitForExit(timeoutMs))
        {
            try { p.Kill(true); } catch { }
            throw new TimeoutException(file + " ne répond pas");
        }
        return (p.ExitCode, (stdout.Result + stderr.Result).Trim());
    }
}
