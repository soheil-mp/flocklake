# Data sources

FlockLake uses only open data that is not about people. Every source below was checked on
**2 November 2026** by listing the public buckets anonymously; sizes are measured, not quoted.
Re-check before relying on any number: upstream layouts change (the NEXRAD archive moved to a
new bucket in 2025).

## Summary

| Source | What it holds | Access | Format | Cadence | Measured size | Licence |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| **Aloft** | Vertical profiles of birds (vol2bird output) for European radars | S3 bucket `aloftdata` (eu-west-1), anonymous | ODIM HDF5 profiles, VPTS CSV (daily), gzipped VPTS CSV (monthly) | 5 min; bucket refreshed daily | 26 KB per profile file; ~2 MB per radar-day CSV; 8–18 MB per radar-month `.csv.gz` | CC BY 4.0 |
| **OPERA Open Radar Data** (EUMETNET) | Single-site polar volumes from ~20 countries, plus composites | S3 bucket `openradar-24h` at `s3.waw3-1.cloudferro.com`, anonymous, **rolling 24 hours**; ORD API; MQTT notifications | ODIM HDF5 (BUFR for some older data) | 5 min (country-dependent) | Herwijnen (NL): 24.4 MB per volume, **7.0 GB per radar-day**; Belgium: one file per quantity, 0.5–1 MB each | CC BY 4.0, exceptions noted in metadata |
| **NOAA NEXRAD Level II** | US WSR-88D (S-band) polar volumes | S3 bucket `unidata-nexrad-level2` (us-east-1), anonymous; SNS topic for new objects | NEXRAD Archive II (message 31) | ~4–10 min, depends on the volume coverage pattern | KDOX on 15 Oct 2026: 209 volumes (~8.8 MB each) + 24 `_MDM` metadata files, **1.85 GB per radar-day** | Open data (NOAA); attribution requested |
| **Open-Meteo** | Winds and geopotential height on pressure levels | HTTPS API, no key for non-commercial use | JSON | Hourly | KBs per request | CC BY 4.0 |
| **ERA5** *(optional)* | Reanalysis winds | Copernicus Climate Data Store API (account + key) | GRIB / NetCDF | Hourly | MBs per request | Copernicus licence |
| **EMODnet Human Activities** *(optional)* | Offshore wind-farm polygons for context maps | OGC WFS | GeoJSON | Static | KBs | Check the layer's licence before use |

The size column is why this project has a **storage budget** (see
[ADR 0007](../adr/0007-storage-budget-and-manifest-first-ingestion.md)): one Dutch radar produces
about 2.5 TB of raw volumes per year, while the profile products derived from it fit in a few
hundred megabytes.

## Aloft (European bird profiles)

- Endpoint: `https://aloftdata.s3-eu-west-1.amazonaws.com` (anonymous `ListObjectsV2` works).
- Top level: `coverage.csv` (~14 MB, `directory,file_count`), and one prefix per processing
  source: `baltrad/`, `uva/`, `ecog-04003/`.
- Layout per source:
  - `{source}/hdf5/{radar}/{yyyy}/{mm}/{dd}/{radar}_vp_{yyyymmddThhmmssZ}_{suffix}.h5`
  - `{source}/daily/{radar}/{yyyy}/{radar}_vpts_{yyyymmdd}.csv`
  - `{source}/monthly/{radar}/{yyyy}/{radar}_vpts_{yyyymm}.csv.gz`
- Radars use ODIM node names (`nldhl` Den Helder, `nlhrw` Herwijnen, `bejab` Jabbeke, ...).
  The `baltrad` daily archive for `nldhl` starts in 2012.
- `coverage.csv` was last modified at 02:29 UTC on the day of the check, so the bucket is
  refreshed nightly. Its ETag is a cheap change signal for a sensor.
- A daily VPTS CSV holds 287–288 profiles (5-minute steps) × 25 height bins (0–4800 m, 200 m
  wide). Columns, in order:

  `radar, datetime, height, u, v, w, ff, dd, sd_vvp, gap, eta, dens, dbz, dbz_all, n, n_dbz,
  n_all, n_dbz_all, rcs, sd_vvp_threshold, vcp, radar_latitude, radar_longitude, radar_height,
  radar_wavelength, source_file`

- The format is the **VPTS CSV** data exchange standard (a Frictionless Table Schema), documented
  at <https://aloftdata.eu/vpts-csv/>. FlockLake validates against that schema rather than a
  hand-written copy.
- Profiles are produced by vol2bird. For `nldhl` (C-band, 5.3 cm) the file records a radar
  cross-section of 11 cm² and an `sd_vvp` threshold of 2 m/s.
- Long-term archives are also deposited on Zenodo (per country, per radar, per month).

## OPERA Open Radar Data (European polar volumes)

- The EUMETNET OPERA programme publishes radar data declared *high-value datasets* under
  Implementing Regulation (EU) 2023/138, through the RODEO project.
- **S3 (rolling 24 hours):** endpoint `https://s3.waw3-1.cloudferro.com`, bucket
  `openradar-24h`, anonymous (`--no-sign-request`). Objects older than about a day disappear,
  so a capture job must run at least daily or the data is gone.
- Key layout:
  `{yyyy}/{mm}/{dd}/{CC}/{radar}/PVOL/{radar}@{yyyymmddThhmm}@{elevations}@{quantities}.h5`,
  for example
  `2026/11/01/BE/behel/PVOL/behel@20261101T0000@0.3_0.5_0.8_1.8_3.0_5.0_7.5_10.0_13.0_16.0_20.0_25.0@DBZH.h5`.
  Composites live under `OPERA/COMP/`.
- Countries present on 1 Nov 2026: BE CH CZ DE DK EE ES FI FR HR HU IE IS LT MT NL NO PL RO SE SK.
- Packaging differs per country. The Dutch radars put all quantities
  (`CCORH DBZH PHIDP RHOHV SQIH TH VRADH WRADH ZDR`) in one ~25 MB file; Belgium splits one
  quantity per file. Both are ODIM HDF5, so one reader serves both, but the download planner
  must handle both shapes.
- **ORD API:** `https://api.meteogate.eu/eu-eumetnet-weather-radar` (OpenAPI docs at `/docs`),
  OGC API – EDR style: `collections/observations/locations/{wigos-id}` and
  `collections/observations/items` filtered by `bbox`, `datetime`, `naming_authority`,
  `standard_name`. Location IDs are WIGOS identifiers (for example `0-578-0-nohur`). A query with no
  data returns HTTP 204. Anonymous use is rate-limited; watch the `x-ratelimit-remaining`
  header. Keys for higher limits: <https://devportal.meteogate.eu/>.
- **Notifications:** an MQTT service announces new data (public username `everyone`, port 8884),
  which makes event-driven ingestion possible (milestone M15).

## NOAA NEXRAD Level II (US polar volumes)

- Bucket `unidata-nexrad-level2` in us-east-1, anonymous. It replaced `noaa-nexrad-level2`,
  which was retired on 1 September 2025. Same key pattern and file format.
- Key layout: `{yyyy}/{mm}/{dd}/{ICAO}/{ICAO}{yyyymmdd}_{hhmmss}_V06`, plus `..._V06_MDM`
  metadata files that ingestion must skip.
- New-object notifications: SNS `arn:aws:sns:us-east-1:684042711724:NewNEXRADLevel2Archive`.
  Subscribing needs an SQS queue in your own AWS account (optional, milestone M15).
- Real-time chunks: bucket `unidata-nexrad-level2-chunks`, filterable SNS topic
  `arn:aws:sns:us-east-1:684042711724:NewNEXRADLevel2ObjectFilterable`.
- Decoding: `xradar` (MIT) reads Level II; since v0.12.0 (April 2026) it can stream chunked
  data from S3. Volume coverage patterns with supplemental low-level scans (SAILS/MESO-SAILS)
  repeat the 0.5° sweep within a volume; the profile engine must handle repeated sweeps.

## Weather context

- **Open-Meteo**: hourly `wind_speed_{level}hPa`, `wind_direction_{level}hPa` and
  `geopotential_height_{level}hPa` for 1000–500 hPa cover the 0–5 km band of bird profiles.
  850 hPa is roughly 1.5 km above sea level; FlockLake interpolates by geopotential height,
  not by a fixed pressure-to-height table.
- **ERA5** through the Copernicus CDS is the reference reanalysis for historical seasons
  (needs a free account; the key goes in `.env`).

## What FlockLake deliberately does not ingest

- Citizen-science checklists (eBird, observation.org, GBIF occurrences): they carry observer
  names and identifiers. FlockLake has no personal data, so these stay out.
- Proprietary dedicated bird-radar data (for example offshore platform radars): not openly
  licensed.

## Attribution

Products derived from CC BY 4.0 sources must credit them. FlockLake carries attribution in
dataset metadata, API responses, exports and the dashboard footer:

- Aloft: "Contains data from the Aloft bird migration data repository (aloftdata.eu), CC BY 4.0."
- OPERA: "Contains data from EUMETNET OPERA Open Radar Data, CC BY 4.0."
- NEXRAD: "NOAA National Weather Service Radar Operations Center, NEXRAD Level II, via NSF Unidata
  and the AWS Open Data Sponsorship Program."
- Open-Meteo: "Weather data by Open-Meteo.com, CC BY 4.0."
