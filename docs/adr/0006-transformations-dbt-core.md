# ADR 0006: SQL transformations with dbt-core and dbt-duckdb

- Status: Accepted
- Date: 2026-11-02

## Context

Gold data products (integrated profiles, night summaries, band traffic, phenology) are
set-based transformations of silver tables. They need tests, enforced column contracts,
documentation, incremental builds and lineage.

## Decision

- Use **dbt-core** (Apache-2.0) with the **dbt-duckdb** adapter, attached to the DuckLake catalog.
- Layering: `staging` (1:1 with silver), `intermediate`, `marts` (gold).
- Model contracts enforced on every mart; generic and singular tests; dbt unit tests for the
  physics (MTR, band overlap, circular means).
- Incremental models partitioned by night, merged idempotently.
- `sqlfluff` lints SQL in pre-commit and CI.
- Array-heavy work (the profile engine) stays in Python; dbt starts at tabular profiles.

## Consequences

- Most data engineers can read and extend the models.
- The dbt Fusion engine is not used: it is distributed under the Elastic Licence 2.0, which is
  not an open-source licence. dbt-core remains Apache-2.0.

## Alternatives considered

- **SQLMesh:** virtual environments and column-level lineage are attractive; smaller ecosystem
  of adapters and examples for DuckLake.
- **Python-only transforms (Polars):** fast, but loses dbt's tests, contracts and docs.

## Revisit when

- dbt-core's licence or maintenance changes.
- DuckLake support in dbt-duckdb lags behind DuckLake releases.
