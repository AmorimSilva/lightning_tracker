using System.Diagnostics;

namespace LightningTracker.WebApi.Services;

/// <summary>
/// Generates ABI IR Channel 13 full-disk reprojected tiles via web_abi_tile.py.
/// Caches results by rounded UTC time (10-minute granularity) and cmap.
/// No geographic extent is needed: the script always returns the full ABI disk.
/// </summary>
public class PythonAbiService
{
    private readonly string _pythonCommand;
    private readonly string _workingDirectory;
    private readonly string _settingsPath;
    private readonly ILogger<PythonAbiService> _logger;

    // Cache key: (roundedUtcMinutes, cmap)
    private readonly record struct CacheKey(long RoundedUtcMinutes, string Cmap);
    private readonly Dictionary<CacheKey, CacheEntry> _cache = new();
    private readonly SemaphoreSlim _lock = new(1, 1);
    private const int CacheEntryMaxAgeMinutes = 12;
    private const int AbiGranularityMinutes = 10;

    private record CacheEntry(byte[] Png, string Bounds, DateTime CreatedUtc);

    public PythonAbiService(ConfigurationService config, IHostEnvironment env, ILogger<PythonAbiService> logger)
    {
        _pythonCommand = config.GetPythonCommand();
        _logger = logger;

        var wd = config.GetPythonWorkingDirectory();
        _workingDirectory = Path.IsPathRooted(wd)
            ? wd
            : Path.GetFullPath(Path.Combine(env.ContentRootPath, wd));

        _settingsPath = "D:\\lightning_data\\settings_sync.yaml";
    }

    /// <summary>
    /// Gets the full-disk ABI IR tile PNG for the given UTC time.
    /// Returns null if the tile is unavailable.
    /// </summary>
    public async Task<AbiTileResult?> GetTileAsync(
        DateTime utcTime,
        string cmap,
        CancellationToken ct)
    {
        var roundedMinutes = (long)(utcTime - DateTime.UnixEpoch).TotalMinutes / AbiGranularityMinutes * AbiGranularityMinutes;
        var key = new CacheKey(roundedMinutes, cmap);

        // Independent 90-second timeout for the Python process
        using var cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
        cts.CancelAfter(TimeSpan.FromSeconds(90));

        await _lock.WaitAsync(cts.Token);
        try
        {
            // Cache hit?
            if (_cache.TryGetValue(key, out var cached))
            {
                var age = (DateTime.UtcNow - cached.CreatedUtc).TotalMinutes;
                if (age < CacheEntryMaxAgeMinutes)
                {
                    _logger.LogDebug("ABI tile cache hit (age={Age:F1}min)", age);
                    return new AbiTileResult(cached.Png, cached.Bounds, utcTime);
                }
                _cache.Remove(key);
            }

            // Evict stale entries
            var stale = _cache
                .Where(kv => (DateTime.UtcNow - kv.Value.CreatedUtc).TotalMinutes > CacheEntryMaxAgeMinutes)
                .Select(kv => kv.Key).ToList();
            foreach (var k in stale) _cache.Remove(k);

            var roundedUtc = DateTime.UnixEpoch.AddMinutes(roundedMinutes);
            var result = await RunPythonTileAsync(roundedUtc, cmap, cts.Token);
            if (result is null) return null;

            _cache[key] = new CacheEntry(result.Png, result.Bounds, DateTime.UtcNow);
            return result;
        }
        finally
        {
            _lock.Release();
        }
    }

    private async Task<AbiTileResult?> RunPythonTileAsync(
        DateTime utcTime,
        string cmap,
        CancellationToken ct)
    {
        var scriptPath = Path.Combine(_workingDirectory, "scripts", "web_abi_tile.py");

        var psi = new ProcessStartInfo
        {
            FileName = _pythonCommand,
            WorkingDirectory = _workingDirectory,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
            StandardOutputEncoding = null, // binary
        };

        psi.ArgumentList.Add("-u");
        psi.ArgumentList.Add(scriptPath);
        psi.ArgumentList.Add("--settings"); psi.ArgumentList.Add(_settingsPath);
        psi.ArgumentList.Add("--utc"); psi.ArgumentList.Add(utcTime.ToString("O"));
        psi.ArgumentList.Add("--cmap"); psi.ArgumentList.Add(cmap);

        _logger.LogInformation("ABI tile: spawning Python for utc={Utc}", utcTime);

        using var proc = new Process { StartInfo = psi };
        if (!proc.Start())
        {
            _logger.LogError("ABI tile: failed to start Python process");
            return null;
        }

        // Read stdout as raw binary bytes; stderr as text for logging
        using var ms = new MemoryStream();
        var stdoutTask = proc.StandardOutput.BaseStream.CopyToAsync(ms, ct);
        var stderrBuf = new System.Text.StringBuilder();
        var stderrTask = Task.Run(async () =>
        {
            char[] buf = new char[256];
            int n;
            while ((n = await proc.StandardError.ReadAsync(buf, 0, buf.Length)) > 0)
                stderrBuf.Append(buf, 0, n);
        }, ct);

        await Task.WhenAll(stdoutTask, stderrTask);
        await proc.WaitForExitAsync(ct);

        var stderr = stderrBuf.ToString().Trim();
        if (!string.IsNullOrWhiteSpace(stderr))
        {
            var logText = stderr.Length > 1200 ? stderr[..1200] : stderr;
            _logger.LogInformation("ABI tile stderr: {Stderr}", logText);
        }

        _logger.LogInformation("ABI tile: exit={Exit}, rawBytes={RawBytes}", proc.ExitCode, ms.Length);

        if (proc.ExitCode != 0)
        {
            _logger.LogWarning("ABI tile: Python failed with exit code {Code}. Stderr: {Stderr}", proc.ExitCode, stderr);
            return null;
        }

        var raw = ms.ToArray();
        if (raw.Length < 20)
        {
            _logger.LogWarning("ABI tile: output too short ({Bytes} bytes)", raw.Length);
            return null;
        }

        // Protocol: first line = "BOUNDS:<lat_min>,<lon_min>,<lat_max>,<lon_max>\n"
        int newlineIdx = Array.IndexOf(raw, (byte)'\n');
        if (newlineIdx < 0)
        {
            _logger.LogWarning("ABI tile: no newline found in output. First 50 bytes: {Bytes}", BitConverter.ToString(raw, 0, Math.Min(raw.Length, 50)));
            return null;
        }

        var header = System.Text.Encoding.ASCII.GetString(raw, 0, newlineIdx).Trim();
        if (!header.StartsWith("BOUNDS:", StringComparison.OrdinalIgnoreCase))
        {
            _logger.LogWarning("ABI tile: unexpected header: '{Header}'", header[..Math.Min(header.Length, 100)]);
            return null;
        }

        var bounds = header["BOUNDS:".Length..];
        var pngBytes = raw[(newlineIdx + 1)..];

        if (pngBytes.Length < 8)
        {
            _logger.LogWarning("ABI tile: PNG data too short ({Bytes} bytes)", pngBytes.Length);
            return null;
        }

        _logger.LogInformation("ABI tile: success — {Bytes} bytes PNG, bounds={Bounds}", pngBytes.Length, bounds);
        return new AbiTileResult(pngBytes, bounds, utcTime);
    }
}

public record AbiTileResult(byte[] Png, string Bounds, DateTime UtcTime);
