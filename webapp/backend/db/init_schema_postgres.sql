-- Postgres + PostGIS schema for lightning tracker (init)
CREATE EXTENSION IF NOT EXISTS postgis;

-- raw_files: recortado/comprimido netCDF/Zarr metadata
CREATE TABLE IF NOT EXISTS raw_files (
  id            bigserial PRIMARY KEY,
  source_url    text,
  source_time   timestamptz,
  downloaded_at timestamptz NOT NULL DEFAULT now(),
  file_format   text,
  checksum      text,
  uncompressed_size bigint,
  compressed_size bigint,
  bbox          geometry(Polygon,4326),
  min_lat       double precision,
  min_lon       double precision,
  max_lat       double precision,
  max_lon       double precision,
  compressed_blob bytea,
  metadata      jsonb,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_url, source_time)
);

CREATE INDEX IF NOT EXISTS idx_raw_files_source_time ON raw_files (source_time);
CREATE INDEX IF NOT EXISTS idx_raw_files_bbox_gist ON raw_files USING GIST (bbox);

-- lightning_events: normalized events for fast queries
CREATE TABLE IF NOT EXISTS lightning_events (
  id           bigserial PRIMARY KEY,
  raw_file_id  bigint REFERENCES raw_files(id) ON DELETE SET NULL,
  kind         text NOT NULL DEFAULT 'flash',
  event_time   timestamptz NOT NULL,
  geom         geometry(Point,4326) NOT NULL,
  latitude     double precision NOT NULL,
  longitude    double precision NOT NULL,
  intensity    double precision,
  attributes   jsonb,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_lightning_events_kind ON lightning_events (kind);
CREATE INDEX IF NOT EXISTS idx_lightning_events_event_time ON lightning_events (event_time);
CREATE INDEX IF NOT EXISTS idx_lightning_events_rawfile ON lightning_events (raw_file_id);
CREATE INDEX IF NOT EXISTS idx_lightning_events_geom_gist ON lightning_events USING GIST (geom);
CREATE INDEX IF NOT EXISTS brin_lightning_events_event_time ON lightning_events USING BRIN (event_time);

-- daily_tables: CSV/JSON generated per taker/day
CREATE TABLE IF NOT EXISTS daily_tables (
  id           bigserial PRIMARY KEY,
  taker_id     integer NOT NULL,
  taker_name   text,
  date         date NOT NULL,
  generated_at timestamptz NOT NULL DEFAULT now(),
  csv_blob     bytea,
  csv_text     text,
  metadata     jsonb,
  filesize     bigint,
  UNIQUE (taker_id, date)
);

CREATE INDEX IF NOT EXISTS idx_daily_tables_taker_date ON daily_tables (taker_id, date);

-- optional lightweight catalog
CREATE TABLE IF NOT EXISTS table_catalog (
  id           bigserial PRIMARY KEY,
  daily_table_id bigint REFERENCES daily_tables(id) ON DELETE CASCADE,
  taker_id     integer NOT NULL,
  date         date NOT NULL,
  preview_json jsonb,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_table_catalog_taker_date ON table_catalog (taker_id, date);

-- Notes:
-- 1) For heavy blobs prefer object storage and store URL + metadata in raw_files.
-- 2) Consider partitioning lightning_events by RANGE(event_time) for large datasets.
