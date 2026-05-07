namespace LightningTracker.WebApi.Models;

public record LightningEvent(
    long Id,
    string Kind,
    DateTime EventTime,
    double Latitude,
    double Longitude,
    double? Intensity
);
