# Product Requirements: ROI OS MVP

## Objective
Ship a commercially usable MVP that proves measurable CI/CD quality improvement via baseline→delta reporting.

## Required capabilities
- Compute and persist baseline scorecards per repository
- Compute current scorecard and trend deltas
- Return quick-win recommendations with evidence context
- Export report artifacts for weekly stakeholder review
- Support portfolio view across multiple repos

## Functional requirements
1. API: Create baseline for repo
2. API: Fetch current scorecard with baseline delta
3. API: Export ROI report for repo/time window
4. Dashboard: Show score breakdown and trend
5. Dashboard: Show recommended actions and expected impact
6. Dashboard: Trigger baseline save

## Quality requirements
- Deterministic scoring for same input data
- Graceful behavior with sparse telemetry
- API response latency acceptable for interactive dashboard use
- Unit and endpoint test coverage for baseline/delta/report behavior

## Acceptance criteria
- User can onboard a repo and generate first scorecard within one session
- User can save baseline and view non-null delta after subsequent runs
- User can export a report containing baseline/current/delta rows
- Recommendation list is non-empty when key signals are missing
