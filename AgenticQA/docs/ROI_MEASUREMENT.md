# AgenticQA ROI Measurement Model

Use a baseline→delta framework to quantify value after adoption.

## Core Formula
For each KPI:

- Baseline: pre-adoption value over a fixed window
- Current: post-adoption value over equivalent window
- Delta: $\Delta = \text{Current} - \text{Baseline}$
- Improvement % (for "lower is better" metrics):
  $\text{Improvement\%} = \frac{\text{Baseline} - \text{Current}}{\text{Baseline}} \times 100$

## KPI Set (Initial)

### Reliability / Delivery
- CI failure rate
- Flake rate
- Mean time to detect (MTTD) quality regressions
- Mean time to resolve (MTTR) CI/test issues
- Re-run volume per pipeline

### Throughput / Efficiency
- Engineer triage hours per sprint
- Lead time impact from quality gates
- Prompt-to-fix cycle time

### Quality Outcomes
- Escaped defect rate
- Reopen rate for fixed defects
- Release rollback / hotfix frequency

## Baseline Window Recommendations
- Preferred: 2–4 weeks pre-adoption
- Minimum: 7 days if data is sparse
- Keep windows consistent by team and repository

## Reporting Cadence
- Weekly operational pulse
- Sprint summary (primary stakeholder review)
- Quarterly executive rollup

## Evidence Artifacts
- Portability score snapshot + trend classification
- KPI baseline/current/delta table
- Top 3 wins and top 3 blockers
- Action plan for next period

## Sample ROI Table (Template)

| KPI | Baseline | Current | Delta | Direction | Notes |
|---|---:|---:|---:|---|---|
| CI failure rate | 18% | 12% | -6 pts | Improved | Fewer flaky failures |
| MTTR (hours) | 9.5 | 6.0 | -3.5 | Improved | Faster triage routing |
| Re-run volume | 140 | 95 | -45 | Improved | Better first-pass stability |

## Governance Rules
- Define metric owner per KPI.
- Freeze definitions each quarter to preserve comparability.
- Flag anomalies (schema shifts, pipeline migrations) in report metadata.
