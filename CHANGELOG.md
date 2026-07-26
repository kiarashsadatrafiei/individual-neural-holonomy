# Changelog

## v1.0.0 — integrated final analysis

### Stage 2

- Increased clone-bootstrap resolution to 20,000 draws.
- Expanded independent-noise robustness from 8 to all 20 validation clones.
- Added paired clone-bootstrap uncertainty for the constant-fast-gate contrast.
- Replaced “gauge-invariant nonfactorizability” wording with separate
  shared-frame interaction and within-clone conjugacy estimands.
- Exported the full pilot candidate table and preserved the practical
  double-null threshold interpretation.

### Stage 3

- Increased the final design to 8 pilot and 32 validation clones with 4 repeats.
- Calibrated the neutral RIC reference on pilot values only.
- Made clone/pretraining streams invariant to cohort size.
- Removed intervention flags from seeds so all ablations are paired to exactly
  the same exogenous streams.
- Ran every ablation on the full validation cohort and added paired
  clone-bootstrap intervals.
- Added stochastic same-history repeat nulls and simultaneous familywise lower
  bounds.
- Limited the supported claim to stable-versus-non-stable separation; retained
  the failed global four-regime taxonomy as an explicit secondary result.
- Rejected fast-RIC causality; retained supported retention, protention, and
  slow-κ contributions.

### Stage 4

- Regenerated the Stage-3-derived cohort with pilot-only RIC calibration.
- Corrected ICC uncertainty to resample whole clones rather than flattened
  clone-by-branch targets.
- Distinguished within-setup measurement repeatability from independent-session
  generalization and reported both.
- Expanded all stress tests to every validation clone and every observation
  repeat with cluster-bootstrap intervals.
- Corrected the integration-interval comment and regenerated lineage hashes.

### Stage 5

- Increased exact-equivalence draws to 10 and random degradation draws to 20.
- Increased hierarchical bootstrap resolution to 5,000 draws.
- Reclassified circular trial shifts as temporal-alignment nuisance rather than
  information loss.
- Required all three true information-loss families to pass strict
  bootstrap-supported ordering-decline, error-rise, and boundary criteria.
- Explicitly labeled Stage 5 as sensitivity analysis on the reused Stage 4
  validation cohort.
- Saved padded scenario-level arrays and draw counts for independent audit.

### Integration and quality control

- Added a final analysis protocol, one-command rerun, independent point-estimate
  recomputation, independent-root robustness, source-data tables/workbook,
  publication figures, paste-ready Methods/Results/captions, and a rendered Word
  report.
- Preserved the uploaded archives and manuscript as unmodified source material.

