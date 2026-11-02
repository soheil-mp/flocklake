# ADR 0004: Orchestrate with Dagster software-defined assets

- Status: Accepted
- Date: 2026-11-02

## Context

The pipelines are naturally described as **data products per radar per night**: a profile
exists for (nldhl, 2026-10-19), and a night summary depends on it. The orchestrator must
support:

- two-dimensional partitions (radar × night) and backfills over them;
- event-style triggers (an object appears upstream) and time-based schedules;
- data-quality checks attached to the data they check;
- dbt integration, lineage, and a local developer experience without a cloud account;
- Kubernetes deployment with an official Helm chart.

## Decision

Use **Dagster OSS** (Apache-2.0) with software-defined assets:

- `MultiPartitionsDefinition` of a static radar dimension and a daily night dimension.
- Sensors for upstream changes (the ETag of Aloft's `coverage.csv`, the OPERA notification inbox).
- Asset checks for data quality; blocking checks stop downstream materialisation.
- `dagster-dbt` to load dbt models as assets with the same partitions.
- Concurrency pools to keep downloads polite to upstream services.
- Ephemeral instance mode for the GitHub Actions daily run; the official Helm chart with the
  Kubernetes run launcher for the cluster.

## Consequences

- The asset graph is the lineage graph, visible in the UI.
- Partition logic lives in code and is unit-testable.
- Dagster is a large dependency, so it is confined to `flocklake-pipelines`; the science and
  ingestion packages do not import it.

## Alternatives considered

- **Apache Airflow 3:** mature and now has assets, but its model is still task-first; partitioned
  backfills over two dimensions are more manual.
- **Prefect 3:** simple Python flows, but weaker asset and partition modelling.
- **Cron + scripts:** no lineage, no backfills, no checks.

## Revisit when

- Dagster OSS licensing or Helm chart support changes.
- The two-dimensional partitions hit scaling limits (thousands of radars × years).
