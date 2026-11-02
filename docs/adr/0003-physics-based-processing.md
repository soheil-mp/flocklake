# ADR 0003: Physics-based, rule-based processing only

- Status: Accepted
- Date: 2026-11-02

## Context

Separating birds from rain, insects and clutter can be done with published physical rules
(dual-polarisation thresholds, velocity statistics, cell detection), or with learned models
such as convolutional networks trained on labelled radar images. Forecasting migration usually
uses fitted statistical models.

FlockLake is meant to be a transparent data platform. Users (ecologists, analysts, reviewers)
must be able to see exactly why a layer was classified as birds and reproduce it.

## Decision

- All classification and estimation in FlockLake are **physics-based or rule-based**: formulas,
  documented thresholds and deterministic algorithms (see
  [radar aeroecology](../research/radar-aeroecology.md)).
- No learned models, no model weights, no training or evaluation datasets, no calls to model
  APIs. vol2bird runs only as a test reference, with its MistNet option disabled.
- Analytics are **descriptive**: integrals, percentiles, circular statistics, median/MAD
  baselines. FlockLake reports what radars observed; it does not forecast.
- Every threshold is configuration with a cited default, and is stored with the output.

## Consequences

- Every number is explainable and testable against synthetic truth.
- Some contamination that a learned model would catch (for example mixed rain and birds) is
  flagged rather than removed. The quality scorecard makes that visible.
- No forecasts; the product is observation and history.

## Alternatives considered

- **MistNet-style segmentation:** more accurate in mixed scenes, but opaque, heavy, and it brings
  model files and training data into the project.
- **Statistical forecasting:** useful operationally, but out of scope for a transparent
  observation platform.

## Revisit when

Not expected. A change would need a new ADR explaining how interpretability is kept.
