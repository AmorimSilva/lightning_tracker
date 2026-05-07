import psycopg2
conn = psycopg2.connect('host=127.0.0.1 port=6543 dbname=lightning user=user password=pass')
cur = conn.cursor()

# Recent events total
cur.execute("select count(*) from lightning_events where event_time >= '2026-05-06 18:00:00+00'")
print("Total recent (since 18:00 UTC):", cur.fetchone()[0])

# Recent events near RJ/Macae area
cur.execute("select count(*) from lightning_events where event_time >= '2026-05-06 18:00:00+00' and latitude between -25 and -20 and longitude between -45 and -39")
print("RJ/Macae area (recent):", cur.fetchone()[0])

# Recent near all key takers
locs = [
    (-1.44, -48.49, 'Belem'),
    (-3.69, -38.87, 'Termoceare'),
    (-12.67, -38.31, 'Termocamacari'),
    (-22.41, -41.86, 'Macae'),
    (-22.72, -43.28, 'REDUC'),
    (-23.87, -46.43, 'RPBC'),
]

for lat, lon, name in locs:
    for kind in ['flash', 'event']:
        cur.execute(
            "select count(*) from lightning_events where kind=%s and event_time >= '2026-05-06 18:00:00+00' and latitude between %s and %s and longitude between %s and %s",
            (kind, lat - 2.5, lat + 2.5, lon - 2.5, lon + 2.5)
        )
        print(f"  {name} ({kind}): {cur.fetchone()[0]}")
