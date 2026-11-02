# FlockLake

**Bird migration, measured by weather radar.** FlockLake is an open data platform that turns
public weather-radar data from Europe and the US into quality-checked, lineage-tracked data
products about migrating birds: how many fly each night, at what altitude, in which direction,
and how that changes through the season.

Every night in spring and autumn, millions of songbirds migrate in the dark. Weather radars,
built to watch rain, record them too, and their data is published openly. FlockLake ingests that
data within a strict storage budget, turns radar volumes into vertical profiles of birds with
transparent, physics-based methods, and publishes nightly products through a dashboard, an API
and standard file formats.

> **Status: planning complete, building in progress.** The research, architecture and a
> 789-hour roadmap are done. The platform is being built milestone by milestone; see
> [Status and plans](#status-and-plans).

## What makes it different

- **Existing radar networks as the sensor.** Three open feeds in one lakehouse: Aloft bird
  profiles, EUMETNET OPERA polar volumes (Europe) and NOAA NEXRAD Level II (US).
- **Built for a small disk.** One Dutch radar produces 7 GB of data a day. FlockLake enforces a
  storage budget before it downloads anything, keeps manifests instead of raw files for archives
  that never expire, samples nights only, and reads just the parts of HDF5 files it needs.
- **Nights, not calendar days.** Data is partitioned by the night at each radar, from sunset to
  sunrise, so a night's total comes from exactly one partition.
- **Explainable science.** No learned models: every bird density, speed and flag comes from a
  documented formula and threshold. Results are checked against synthetic radar volumes with known
  truth and against the reference algorithm, vol2bird.
- **Production-grade data engineering.** Dagster assets with partitions, sensors and checks; dbt
  models with enforced contracts; DuckLake time travel; ODCS data contracts; OpenLineage;
  observability with SLOs; containers, Kubernetes, GitOps and signed releases.
- **Open standards out.** VPTS CSV, ODIM HDF5, Parquet, STAC and OGC API – EDR, so ecologists can
  load results straight into bioRad (R) or Python.

## Who it's for

- **Ecologists** studying nocturnal migration, flight altitudes and how birds respond to wind.
- **Wind-energy and environmental analysts** who want an observation-based history of bird
  traffic at turbine height near the coast.
- **People working on light pollution** who need to know which nights had heavy migration.
- **Data engineers** looking for a complete, realistic reference platform built on open
  scientific data.
- **Curious naturalists** who want to see last night's migration over their region.

## Built with

Python 3.13 and uv · xradar, xarray, h5py and Zarr for radar data · DuckDB and DuckLake on
PostgreSQL and S3-compatible storage · Dagster · dbt-core · Pandera, Frictionless and
datacontract-cli · FastAPI and pygeoapi · OpenTelemetry, Prometheus and Grafana · Docker,
Kubernetes (kind, Helm, Argo CD) and OpenTofu · GitHub Actions · a static TypeScript dashboard with
DuckDB-WASM and MapLibre.

The full list, with licences and the alternatives considered, is in
[docs/architecture.md](docs/architecture.md#11-tool-choices).

## How to run it

### Look at the data now

The data FlockLake starts from is public. With only [DuckDB](https://duckdb.org/docs/installation/)
installed, this computes hourly migration traffic over Den Helder (NL) for one night, straight
from the Aloft bucket:

```sh
git clone https://github.com/soheil-mp/flocklake.git
cd flocklake
duckdb < examples/night-traffic.sql
```

```text
┌──────────┬───────────────────────┬────────────────────────────────┐
│ hour_utc │ birds_per_km_per_hour │             chart              │
├──────────┼───────────────────────┼────────────────────────────────┤
│ 16:00    │                  20.0 │ ███▉                           │
│ 17:00    │                  60.0 │ ████████████                   │
│ 18:00    │                 108.0 │ █████████████████████▌         │
│ 19:00    │                  76.0 │ ███████████████▏               │
│ 20:00    │                  44.0 │ ████████▋                      │
│ ...      │                   ... │ ...                            │
```

Sunset at the radar was at 16:36 UTC; the peak in the 18:00 hour is the nightly take-off of
migrants. (Output from 2 November 2026; values can change if the upstream data is reprocessed.)

### Develop

Prerequisites: [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/)
(`uv tool install rust-just` works). uv installs Python 3.13 itself if needed.

```sh
git clone https://github.com/soheil-mp/flocklake.git
cd flocklake
just bootstrap              # packages and dev tools from uv.lock, plus the git hooks
just check                  # what CI runs: lint, format, strict types, secret scan, tests
just                        # list every recipe
```

The local data platform (`just up`) arrives with roadmap milestone M2 and will also need Docker
with Compose.

## Status and plans

What exists today:

- [Data sources](docs/research/data-sources.md), checked against the live buckets with measured
  sizes and licences.
- [The science](docs/research/radar-aeroecology.md): formulas, conventions and references, with
  the core conversion verified against real profile data.
- [Target architecture](docs/architecture.md) and [architecture decision records](docs/adr/).
- [ROADMAP.md](ROADMAP.md): 6 phases, 22 milestones, 177 estimated items, from engineering
  foundations to v1.0.0.

The work ahead is in [ROADMAP.md](ROADMAP.md) and the issues.

## Data sources and attribution

FlockLake uses only open data that is not about people.

- Aloft bird migration data repository ([aloftdata.eu](https://aloftdata.eu)), CC BY 4.0.
- EUMETNET OPERA Open Radar Data, CC BY 4.0.
- NOAA National Weather Service Radar Operations Center, NEXRAD Level II, via NSF Unidata and the
  AWS Open Data Sponsorship Program.
- Weather data by [Open-Meteo.com](https://open-meteo.com), CC BY 4.0.

## License

MIT, see [LICENSE](LICENSE). Data you download through FlockLake keeps its own licence (see
above).
