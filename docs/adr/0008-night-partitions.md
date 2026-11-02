# ADR 0008: Partition by radar night, not by calendar day

- Status: Accepted
- Date: 2026-11-02

## Context

Nocturnal migration runs from about sunset to sunrise and crosses midnight. Upstream files are
organised by UTC calendar day. Partitioning by UTC day splits every night into two partitions,
which makes nightly totals (migration traffic) depend on two partial runs and complicates
backfills and freshness checks.

## Decision

- The time dimension of every partition is the **night date**: the local evening date at the
  radar. In Dagster this is a daily partition whose window runs from 12:00 to 12:00 UTC.
  The noon cut-off is far from both dusk and dawn for European radars, and the night window
  inside each partition is computed precisely from sunset and sunrise at the radar's coordinates.
- For radars where noon UTC falls inside the night (far west of Greenwich), the cut-off is set per
  radar group; US radars use a 17:00 UTC cut-off.
- `dim_night` stores sunset, sunrise, civil twilight and night length per radar and date.
- Polar day (no night at all) produces an empty, valid partition with a `polar_day` flag.

## Consequences

- A nightly total is computed from exactly one partition.
- Freshness has a clear meaning: "night N is complete after sunrise plus a delay".
- Daytime phenomena (morning roost exodus) still fall into a well-defined partition: the one
  whose window contains them.

## Alternatives considered

- **UTC calendar days:** simple, but splits nights.
- **Variable windows from sunset to sunset:** precise, but partitions would have different lengths
  on every radar, which complicates the partition definition and backfills.

## Revisit when

- Daytime products (roosts, soaring migrants) become as important as nocturnal ones.
