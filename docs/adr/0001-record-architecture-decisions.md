# ADR 0001: Record architecture decisions

- Status: Accepted
- Date: 2026-11-02

## Context

FlockLake combines radar science, data engineering and platform operations. Many choices have
credible alternatives (orchestrator, table format, object store, transformation tool). Without a
record, the reasons are lost and the same debates come back.

## Decision

Significant decisions are recorded as short Markdown ADRs in `docs/adr/`, numbered in order, in
the format: Context, Decision, Consequences, Alternatives considered, Revisit when.

- An ADR is written in the same pull request as the change it explains.
- Accepted ADRs are not rewritten. A new ADR supersedes an old one, and the old one's status
  changes to "Superseded by ADR NNNN".
- "Revisit when" names a concrete trigger, not a date.

## Consequences

- New contributors can read why the platform looks the way it does.
- Small overhead per decision; trivial choices do not need an ADR.

## Alternatives considered

- A single design document: drifts and loses history.
- Decisions only in pull-request descriptions: hard to find later.
