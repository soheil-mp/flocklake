# ADR 0005: DuckLake on a PostgreSQL catalog with S3-compatible storage

- Status: Accepted
- Date: 2026-11-02

## Context

Tables need ACID writes from several concurrent runs, time travel (to pin the exact data behind a
published result), schema evolution, and Parquet files on object storage. The platform must run
on a laptop and in Kubernetes. Total data is small (gigabytes), so operational simplicity
outweighs features for petabyte scale.

## Decision

- **Table format:** DuckLake 1.0 (MIT, released April 2026): Parquet data files, metadata in a
  SQL database.
- **Catalog database:** PostgreSQL, so that several Dagster runs can write at once (a DuckDB-file
  catalog allows a single writer only).
- **Object storage:** S3 API. Locally: **SeaweedFS** (Apache-2.0) in Docker Compose; in
  Kubernetes: SeaweedFS Helm chart. Code only speaks S3, so a cloud bucket is a config change.
- **Arrays** (polar volumes) are stored as Zarr v3 next to the tables, referenced from them.
- Every gold publication records the DuckLake snapshot ID it was built from.

## Consequences

- One engine (DuckDB) for ingestion SQL, dbt and the API.
- Weekly maintenance is needed: merge small files, expire snapshots, clean orphaned files.
- DuckLake 1.0 added Iceberg-compatible features; an export path to Iceberg stays open.

## Alternatives considered

- **Apache Iceberg + Lakekeeper/Polaris REST catalog:** the industry standard at scale, but
  more moving parts for gigabytes of data.
- **Plain Parquet + Hive partitions:** no transactions, no time travel.
- **MinIO** as object store: its community edition entered maintenance mode in December 2025 and
  the repository was archived in February 2026.
- **RustFS / Garage:** RustFS is younger; Garage is AGPL-3.0 (acceptable as a service, but
  SeaweedFS is permissive and mature).

## Revisit when

- Data grows beyond what one DuckDB process handles comfortably.
- A consumer requires Iceberg natively.
