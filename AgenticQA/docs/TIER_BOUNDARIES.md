# AgenticQA Tier Boundaries

This document defines feature entitlements by plan to avoid packaging ambiguity.

## Principles
- Keep Free adoption frictionless.
- Reserve team-scale automation and collaboration for Pro.
- Reserve governance, security, and compliance controls for Enterprise.
- Keep add-ons modular and attachable to Pro/Enterprise unless explicitly allowed.

## Entitlement Matrix (Draft)

| Capability | Free / Community | Pro / Team | Enterprise |
|---|---:|---:|---:|
| Local-first bootstrap | ✅ | ✅ | ✅ |
| Health checks + JUnit ingest | ✅ | ✅ | ✅ |
| Core dashboard visibility | ✅ | ✅ | ✅ |
| Advanced analytics | ❌ | ✅ | ✅ |
| Collaboration intelligence | ❌ | ✅ | ✅ |
| Prompt-to-workflow execution | ❌ | ✅ | ✅ |
| Branch/commit automation | ❌ | ✅ | ✅ |
| Optional PR creation | ❌ | ✅ | ✅ |
| Graph-powered routing recommendations | ❌ | ✅ | ✅ |
| Policy guardrails (basic) | ❌ | ✅ | ✅ |
| SSO/SAML | ❌ | ❌ | ✅ |
| Tenant isolation | ❌ | ❌ | ✅ |
| Advanced RBAC | ❌ | ❌ | ✅ |
| Approval workflows | ❌ | ❌ | ✅ |
| Audit exports | ❌ | ❌ | ✅ |
| Retention policy controls | ❌ | ❌ | ✅ |
| Private/self-hosted deployment | ❌ | Optional | ✅ |
| SLA / priority support | ❌ | ❌ | ✅ |

## Add-on Eligibility (Draft)

| Add-on | Free | Pro | Enterprise |
|---|---:|---:|---:|
| RAG+ Intelligence | ❌ | ✅ | ✅ |
| Autonomous Repair | ❌ | ✅ | ✅ |
| Prompt Ops Automation | ❌ | ✅ | ✅ |
| Compliance Suite | ❌ | Optional | ✅ |

## Guardrail Decisions to Finalize
1. Whether limited Prompt Ops should exist in Free as a trial cap.
2. Whether private deployment is Enterprise-only or Pro+ add-on.
3. Minimum audit/compliance controls guaranteed at Enterprise launch.

## Enforcement Notes
- Gate API routes and UI controls by entitlement policy.
- Ensure docs, marketing copy, and product behavior use identical boundaries.
- Add integration tests for plan-gated features.
