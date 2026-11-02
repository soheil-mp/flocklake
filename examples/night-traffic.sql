-- Hourly bird migration traffic for one night, straight from the public Aloft bucket.
-- Run with: duckdb < examples/night-traffic.sql   (tested with DuckDB 1.5; nothing else to install)
-- Data: Aloft bird migration data repository (aloftdata.eu), CC BY 4.0.

SET TimeZone = 'UTC';

-- Migration traffic rate (birds per km per hour) over Den Helder, night of 19–20 Oct 2026
WITH profiles AS (
    SELECT *
    FROM read_csv([
        'https://aloftdata.s3-eu-west-1.amazonaws.com/baltrad/daily/nldhl/2026/nldhl_vpts_20261019.csv',
        'https://aloftdata.s3-eu-west-1.amazonaws.com/baltrad/daily/nldhl/2026/nldhl_vpts_20261020.csv'
    ])
    WHERE datetime BETWEEN '2026-10-19 16:00:00+00' AND '2026-10-20 07:00:00+00'
      AND NOT gap
),
per_scan AS (   -- MTR = Σ density × ground speed × layer thickness
    SELECT datetime, sum(coalesce(dens, 0) * coalesce(ff, 0) * 3.6 * 0.2) AS mtr
    FROM profiles
    GROUP BY datetime
)
SELECT strftime(time_bucket(INTERVAL 1 HOUR, datetime), '%H:%M') AS hour_utc,
       round(avg(mtr)) AS birds_per_km_per_hour,
       bar(avg(mtr), 0, 150, 30) AS chart
FROM per_scan
GROUP BY ALL
ORDER BY min(datetime);
