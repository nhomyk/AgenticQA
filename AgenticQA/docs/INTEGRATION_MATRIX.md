# AgenticQA Integration Matrix (Draft)

## Source Control / CI / Security Integrations by Tier

| Integration | Free / Community | Pro / Team | Enterprise | Notes |
|---|---:|---:|---:|---|
| GitHub (cloud) | ✅ | ✅ | ✅ | Basic in Free; advanced workflow controls in Pro+ |
| GitHub Enterprise | ❌ | Optional | ✅ | Enterprise governance and audit alignment |
| GitLab (cloud) | ✅ | ✅ | ✅ | Basic ingestion in Free |
| GitLab Self-Managed | ❌ | Optional | ✅ | Preferred in Enterprise private deployments |
| Jenkins | ❌ | ✅ | ✅ | Team automation and enterprise scale |
| SIEM (Splunk/Datadog/Sentinel, etc.) | ❌ | Optional | ✅ | Compliance/audit and security operations |
| Slack / Teams notifications | ✅ | ✅ | ✅ | Basic alerts in Free, richer routing in Pro+ |
| Artifact stores (JUnit, logs, reports) | ✅ | ✅ | ✅ | Core ingestion across all tiers |

## Capability Depth by Tier

### Free / Community
- Basic connectors for quick onboarding
- Limited automation depth
- Community support model

### Pro / Team
- Expanded connector configuration
- Automation and routing workflows
- Team-level notification and triage intelligence

### Enterprise
- Governance-aligned integration posture
- Tenant/security/compliance controls
- Private networking and deployment support

## Deployment Mode Considerations

| Deployment Mode | Free | Pro | Enterprise |
|---|---:|---:|---:|
| Local-only | ✅ | ✅ | ✅ |
| Cloud-managed | ✅ | ✅ | ✅ |
| Private/self-hosted | ❌ | Optional | ✅ |

## Open Decisions
1. Confirm which "Optional" items are packaged as add-ons vs included in Enterprise base.
2. Define support SLAs by integration criticality.
3. Publish minimum supported versions for GHE, GitLab, Jenkins, and SIEM endpoints.
