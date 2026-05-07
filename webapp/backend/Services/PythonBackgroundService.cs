using System.Diagnostics;

namespace LightningTracker.WebApi.Services;

public class PythonBackgroundService
{
    private readonly string _pythonCommand;
    private readonly string _workingDirectory;
    private readonly string _settingsPath;
    private readonly string _contentRoot;

    public PythonBackgroundService(ConfigurationService config, IHostEnvironment env)
    {
        _pythonCommand = config.GetPythonCommand();
        _workingDirectory = config.GetPythonWorkingDirectory();
        _settingsPath = config.GetPythonWorkingDirectory() is string wd 
            ? Path.Combine(wd, "config", "settings.yaml")
            : "config\\settings.yaml";
        _contentRoot = env.ContentRootPath;
    }

    public async Task<byte[]?> GetBackgroundPngAsync(
        double lonMin, double lonMax, double latMin, double latMax, DateTime utcTime, CancellationToken ct)
    {
        var args = new List<string>
        {
            "-m", "src.web_background",
            "--settings", _settingsPath,
            "--lon-min", lonMin.ToString(System.Globalization.CultureInfo.InvariantCulture),
            "--lon-max", lonMax.ToString(System.Globalization.CultureInfo.InvariantCulture),
            "--lat-min", latMin.ToString(System.Globalization.CultureInfo.InvariantCulture),
            "--lat-max", latMax.ToString(System.Globalization.CultureInfo.InvariantCulture),
            "--utc-time", utcTime.ToString("O")
        };

        var psi = new ProcessStartInfo
        {
            FileName = _pythonCommand,
            WorkingDirectory = ResolveWorkingDirectory(),
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
        };

        foreach (var arg in args)
            psi.ArgumentList.Add(arg);

        using var proc = new Process { StartInfo = psi };
        if (!proc.Start())
            return null;

        using var ms = new MemoryStream();
        var stdoutTask = proc.StandardOutput.BaseStream.CopyToAsync(ms, ct);
        var stderrTask = proc.StandardError.ReadToEndAsync(ct);
        
        await Task.WhenAll(stdoutTask, stderrTask);
        await proc.WaitForExitAsync(ct);

        if (proc.ExitCode != 0)
            return null; // or throw based on preference, returning null implies no bg available

        return ms.ToArray();
    }

    private string ResolveWorkingDirectory()
    {
        if (Path.IsPathRooted(_workingDirectory))
            return _workingDirectory;

        return Path.GetFullPath(Path.Combine(_contentRoot, _workingDirectory));
    }
}
