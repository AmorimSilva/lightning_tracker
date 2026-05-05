using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using LightningTracker.WebApi.Models;

namespace LightningTracker.WebApi.Services;

public sealed class RenderFrameCacheService
{
    private readonly PythonRenderService _renderer;
    private readonly string _cacheRoot;
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    private sealed record CachedRender(
        string? LastUpdateLocal,
        Dictionary<string, string> Headers
    );

    public RenderFrameCacheService(IConfiguration config, IHostEnvironment env, PythonRenderService renderer)
    {
        _renderer = renderer;
        var configured = config["RenderCache:Root"];
        _cacheRoot = !string.IsNullOrWhiteSpace(configured)
            ? (Path.IsPathRooted(configured) ? configured : Path.GetFullPath(Path.Combine(env.ContentRootPath, configured)))
            : Path.GetFullPath(Path.Combine(env.ContentRootPath, "cache", "render_frames"));
    }

    public async Task<(byte[] Png, PythonRenderService.RenderMetadata Metadata)> RenderCachedAsync(
        ServiceTaker taker,
        int mode,
        string? startLocal,
        string? endLocal,
        int initialLoadHours,
        int background,
        bool thumb,
        CancellationToken cancellationToken
    )
    {
        var key = BuildKey(taker, mode, startLocal, endLocal, initialLoadHours, background, thumb);
        var bucket = thumb ? "thumb" : "full";
        var cacheDir = Path.Combine(_cacheRoot, bucket);
        var pngPath = Path.Combine(cacheDir, key + ".png");
        var jsonPath = Path.Combine(cacheDir, key + ".json");

        if (File.Exists(pngPath) && File.Exists(jsonPath))
        {
            var cached = await ReadCachedAsync(pngPath, jsonPath, cancellationToken);
            if (cached is not null)
                return cached.Value;
        }

        var rendered = await _renderer.RenderAsync(
            taker,
            mode,
            startLocal,
            endLocal,
            initialLoadHours,
            background,
            thumb,
            cancellationToken
        );

        Directory.CreateDirectory(cacheDir);
        await File.WriteAllBytesAsync(pngPath, rendered.Png, cancellationToken);

        var payload = new CachedRender(rendered.Metadata.LastUpdateLocal, new Dictionary<string, string>(rendered.Metadata.Headers, StringComparer.OrdinalIgnoreCase));
        await File.WriteAllTextAsync(jsonPath, JsonSerializer.Serialize(payload, JsonOptions), Encoding.UTF8, cancellationToken);

        return rendered;
    }

    private static async Task<(byte[] Png, PythonRenderService.RenderMetadata Metadata)? > ReadCachedAsync(
        string pngPath,
        string jsonPath,
        CancellationToken cancellationToken
    )
    {
        try
        {
            var png = await File.ReadAllBytesAsync(pngPath, cancellationToken);
            var json = await File.ReadAllTextAsync(jsonPath, cancellationToken);
            var cached = JsonSerializer.Deserialize<CachedRender>(json, JsonOptions);
            if (cached is null)
                return null;

            var metadata = new PythonRenderService.RenderMetadata(
                cached.LastUpdateLocal,
                new Dictionary<string, string>(cached.Headers, StringComparer.OrdinalIgnoreCase)
            );

            return (png, metadata);
        }
        catch
        {
            return null;
        }
    }

    private static string BuildKey(
        ServiceTaker taker,
        int mode,
        string? startLocal,
        string? endLocal,
        int initialLoadHours,
        int background,
        bool thumb
    )
    {
        var normalized = string.Join("|",
            taker.Id.ToString(),
            taker.Name ?? string.Empty,
            taker.Lat.ToString(System.Globalization.CultureInfo.InvariantCulture),
            taker.Lon.ToString(System.Globalization.CultureInfo.InvariantCulture),
            mode.ToString(),
            startLocal ?? string.Empty,
            endLocal ?? string.Empty,
            initialLoadHours.ToString(),
            background.ToString(),
            thumb ? "1" : "0"
        );

        var hash = SHA256.HashData(Encoding.UTF8.GetBytes(normalized));
        return Convert.ToHexString(hash).ToLowerInvariant();
    }
}
