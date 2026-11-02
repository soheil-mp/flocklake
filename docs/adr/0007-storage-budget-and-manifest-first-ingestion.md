# ADR 0007: Storage budget, manifest-first ingestion and byte-range reads

- Status: Accepted
- Date: 2026-11-02

## Context

Measured on 2 November 2026: one Dutch OPERA radar produces 7.0 GB of volumes per day; one US
NEXRAD radar 1.85 GB per day. The development machine has little free disk. Yet the products
that matter (profiles and summaries) are a few megabytes per radar per day.

## Decision

1. **Storage budget as a hard limit.** `FLOCKLAKE_STORAGE_BUDGET_MB` (default 2048) with
   per-layer ceilings. Before any download, a planner adds up object sizes from the listing and
   refuses the run if the budget would be exceeded, reporting the shortfall.
2. **Manifest-first bronze.** Every listed upstream object gets a manifest row (key, size, ETag,
   last modified, source, licence), whether or not it is downloaded. Sources with permanent
   archives (Aloft, NEXRAD) can be re-downloaded from the manifest at any time, so their raw bytes
   are short-lived (TTL 7 days).
3. **Sampling policy.** By default: night windows only, one volume per 15 minutes, a short list
   of radars. All three are configuration.
4. **Byte-range reads.** For multi-quantity ODIM HDF5 files (the Dutch 25 MB volumes), read only
   the needed datasets (for example DBZH, VRADH, RHOHV, ZDR at the lower elevations) with HTTP
   range requests instead of downloading whole files. A spike in milestone M10 measures the
   saving; the decision is confirmed or reversed by data.
5. **Retention.** Raw 7 days, silver arrays 30 days, tables and gold kept. A weekly job enforces
   it and reports usage.

## Consequences

- The platform runs on a laptop and in a free CI runner.
- OPERA's cache expires after 24 hours, so OPERA data cannot be re-fetched later: its capture
  schedule is the most time-critical job and has its own freshness check.
- Backfills of whole seasons from raw volumes are bounded by the budget and must be planned in
  chunks; the planner makes this explicit.

## Alternatives considered

- **Download everything, delete later:** fails on the first night of OPERA data.
- **Stream-only processing without storing raw data:** loses reproducibility for the 24-hour
  source.

## Revisit when

- Byte-range reads turn out slower than full downloads with deletion.
- More disk becomes available (raise the budget; the design does not change).
