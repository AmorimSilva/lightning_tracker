Tables and API — Lightning Tracker

Overview

This document describes the table-generation script and the three HTTP endpoints the backend exposes for table generation and retrieval.

Table semantics

- Table shape: 4 rows (rings) × 288 columns (5-minute bins) representing a full calendar day from 00:00 to 23:55 local time.
- Each cell counts the number of GLM *flashes* (NOT events) within the ring and 5-minute interval.
- Rings (rows) correspond to configured radii in `config/settings.yaml` (example labels: `0-30`, `30-50`, `50-100`, `100-200`).
- Time columns are labeled `HH:MM` with 5-minute resolution (00:00, 00:05, ..., 23:55).
- The table is anchored to a specific local date. If the requested end time is during the same day (for example 09:00), any bins from that time until 23:55 will be zero (empty).

CSV format

- The generator writes CSVs using `;` as separator and UTF-8 encoding.
- The CSV layout uses radii labels as the row index and time labels as the header columns.
- Example header row (abridged): `;00:00;00:05;00:10;...;23:55`

Script: `src/web_tables.py`

- Usage (command line):

```
python -m src.web_tables --settings config/settings.yaml --name "Taker Name" --lat 12.34 --lon -45.67 [--end-local "YYYY-MM-DDTHH:MM:SS"]
```

- Behavior:
  - By default `--end-local` is now (local timezone); the script anchors to that local date's midnight (00:00).
  - Downloads GLM flash files for the calendar day (midnight..end_local), converts to local times and counts flashes into 5-minute bins.
  - Writes a CSV into the configured `archive_tables_dir` and prints a JSON object to stdout with metadata, CSV path and the table values.

Returned JSON fields

- `takerName`: requested taker name
- `csvPath`: absolute path to the saved CSV on disk
- `csvRelativePath`: relative path from the archive tables root (useful for cataloging)
- `savedAtLocal`: local timestamp when the CSV was written
- `endLocal`: the provided end_local string (local)
- `hourLabels`: array of 288 `HH:MM` strings (00:00..23:55)
- `radiiLabels`: array of 4 radii labels
- `values4x24`: 4 arrays each with 288 integer counts (the name is kept for compatibility with existing consumers)

Backend HTTP API

The webapp exposes three endpoints for tables (see `webapp/backend` sources):

1) POST /api/tables/generate
- Body (JSON):
  - `name` (string) — taker name
  - `lat` (number) — taker latitude
  - `lon` (number) — taker longitude
  - `endLocal` (string, optional) — local end time in `YYYY-MM-DDTHH:MM:SS` or `HH:MM` formats. If omitted, uses the server's local now.
- Response: JSON equal to the script stdout: `csvPath`, `csvRelativePath`, `hourLabels` (288), `radiiLabels` (4), `values4x24` (4×288), etc.

2) GET /api/tables/latest?slug={taker_slug}&limit=10
- Returns a list of the most recent saved CSVs for the given taker slug (relative paths and saved timestamps). The catalog reads files under the archive tables root.

3) GET /api/tables/load?path={relative_path}
- Loads the CSV from disk (relative path under tables root) and returns parsed JSON with `hourLabels`, `radiiLabels`, and `values4x24` (4×288).

Notes and compatibility

- The JSON still uses `hourLabels` and `values4x24` keys for backward compatibility, but each "hour" label now corresponds to a 5-minute slot.
- Consumers (frontend/backend) must be prepared to handle 288 columns rather than 24.

Next steps (rendering + animation)

- The plot exposes the image time being viewed and a computed "next update" timestamp (every 5 minutes). It supports short animations (up to 3 hours) at 3 FPS. Implementation details and API headers are described in the project README and renderer code.

