# ADR 0002: Use open weather-radar networks as the bird sensor

- Status: Accepted
- Date: 2026-11-02

## Context

The project's aim is to monitor birds with radar. Options range from building a small radar
sensor to using radars that already exist. Operational weather radars detect birds every night,
cover whole continents, and publish their data openly:

- **Aloft**: vertical profiles of birds for European radars, refreshed daily, CC BY 4.0.
- **OPERA Open Radar Data**: raw European polar volumes, rolling 24-hour cache, CC BY 4.0.
- **NOAA NEXRAD Level II**: raw US polar volumes, permanent archive, open.

Details and measured sizes are in [data sources](../research/data-sources.md).

## Decision

FlockLake ingests these three feeds, in this order:

1. Aloft profiles first (small, already processed): this is the fast path to a working,
   end-to-end platform and the reference against which FlockLake's own results are checked.
2. OPERA volumes second: raw data, the time-critical 24-hour window, and the Dutch and Belgian
   radars on the North Sea flyway.
3. NEXRAD volumes third: a second radar band (S-band), a second file format, and a permanent
   archive for backfills.

A dedicated low-cost radar sensor is a stretch goal, not a dependency.

## Consequences

- Real data from day one, with no hardware costs.
- The data is large, so a storage budget is mandatory ([ADR 0007](0007-storage-budget-and-manifest-first-ingestion.md)).
- Three formats and two continents force a source-agnostic profile schema, which is a good thing.
- Upstream layouts change (NEXRAD moved buckets in 2025). Source clients are isolated behind
  interfaces and covered by contract tests against live listings.

## Alternatives considered

- **Build a sensor** (for example a 24 or 60 GHz radar module): very limited range and no
  history; useful only as an extension.
- **Dedicated bird radars** (offshore platforms, airports): the data is not openly licensed.

## Revisit when

- A source changes its licence or access model.
- An openly licensed dedicated bird-radar feed appears.
