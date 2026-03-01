# AgenticQA Security Benchmark Report

**Date:** 2026-03-01
**Scanner Version:** 13 scanners (10 core + 3 AI-specific)
**Total Repos:** 11 major AI agent frameworks
**Total Files Scanned:** 16,662
**Total Scan Time:** 273 seconds (~4.5 minutes)

## Executive Summary

AgenticQA scanned 11 of the most widely-used AI agent frameworks and found **52,724 security findings** including **1,339 critical issues** across 16,662 source files. Every repo was classified as **EU AI Act high-risk**. Traditional security tools (Snyk, Semgrep, Checkmarx) would miss **8,438 of these findings** — the ones detected by our AI-specific scanners that have no equivalent in traditional SAST/DAST tooling.

## Repos Scanned

| Repo | GitHub Stars | Language | Files | Findings | Critical |
|------|-------------|----------|-------|----------|----------|
| LlamaIndex | 40k+ | Python | 4,305 | 17,698 | 413 |
| LangChain | 100k+ | Python | 2,532 | 10,836 | 119 |
| Semantic Kernel (Microsoft) | 25k+ | Python/C# | 1,633 | 8,217 | 208 |
| CrewAI | 25k+ | Python | 1,598 | 7,363 | 43 |
| AutoGPT | 170k+ | Python/TS | 2,935 | 3,052 | 119 |
| MetaGPT | 50k+ | Python | 1,022 | 1,976 | 46 |
| OpenAI Agents SDK | 15k+ | Python | 499 | 1,761 | 89 |
| Haystack (deepset) | 18k+ | Python | 1,693 | 1,304 | 210 |
| Open Interpreter | 60k+ | Python | 157 | 377 | 74 |
| Swarm (OpenAI) | 20k+ | Python | 267 | 122 | 18 |
| AutoGen (Microsoft) | 40k+ | Python | 21 | 18 | 0 |

## Scanner Results

### Traditional Security Coverage (tools like Snyk/Semgrep CAN detect these)

| Scanner | Total | What it finds |
|---------|-------|---------------|
| Architecture Scanner | 43,927 | Attack surface: env secrets, shell exec, HTTP calls, DB access, file I/O |
| Legal Risk Scanner | 278 | Credential exposure, SSRF risks, missing auth |
| CVE Reachability | 0* | Known CVE vulnerabilities in dependencies |
| HIPAA PHI Scanner | 0 | Hardcoded PHI, PHI in logs |

*CVE scan requires pip-audit/npm-audit installed in target repos

### AI-Specific Coverage (traditional tools CANNOT detect these)

| Scanner | Total | What it finds |
|---------|-------|---------------|
| **Shadow AI Detection** | **4,448** | Unapproved models (gpt-4o, gemini, llama), unauthorized provider imports, AI env vars |
| **Bias Detection** | **2,300** | Protected attributes (gender, race, age) in decision contexts, stereotyping patterns |
| **Indirect Injection Guard** | **1,475** | Prompt injection payloads hidden in documents for RAG pipeline poisoning |
| **AI Model SBOM** | **574 models** | 12 providers, license violations, deprecated/unversioned models |
| **Prompt Injection Scanner** | **185** | Code-level injection vectors: direct concat, template injection, unsafe output |
| **Agent Trust Graph** | **30** | Circular trust chains, missing human-in-loop, unconstrained delegation |
| **Data Flow Tracer** | **31** | Cross-agent data leakage, credential flow to untrusted sinks |

**Total AI-specific findings: 8,438+ (16% of all findings) that Snyk/Semgrep/Checkmarx would miss entirely.**

## What Traditional Tools Miss: Real Examples

### 1. Shadow AI (4,448 findings)
Every single repo uses models from multiple providers without any governance:
- **LlamaIndex**: 1,161 findings, 10 different providers (OpenAI, Anthropic, Cohere, DeepSeek, Meta, Mistral, Google, HuggingFace, Replicate, Together)
- **LangChain**: 656 findings, models from 8+ providers scattered across the codebase
- **CrewAI**: 623 findings with deep OpenAI and Anthropic embedding

**Why this matters**: Companies using these frameworks inherit uncontrolled model sprawl. No traditional tool flags "you're calling gpt-4o but your policy only approves Claude."

### 2. Indirect Injection Patterns (1,475 findings)
Files containing patterns that could be exploited in RAG pipelines:
- **LlamaIndex**: 446 findings in 131 files (347 critical) — expected for a RAG framework but means every doc ingested through LlamaIndex should be scanned
- **Semantic Kernel**: 237 findings — Microsoft's own agent framework has injection-susceptible patterns
- **Haystack**: 208 findings — deepset's RAG pipeline has similar exposure

**Why this matters**: EchoLeak (CVE-2025-32711) proved these aren't theoretical — poisoned emails exfiltrated data through Copilot with zero clicks.

### 3. AI Model SBOM (574 unique models across 12 providers)
No traditional SBOM tool understands AI model licensing:
- **LlamaIndex**: 161 unique models, 122 license violations
- **CrewAI**: 120 models
- **LangChain**: 112 models

**Why this matters**: The EU AI Act requires knowing exactly which AI models are in your software supply chain.

### 4. EU AI Act Compliance
Every single repo classified as **high_risk** under Annex III:
- 9/11 repos match "employment" use case (AI making hiring/workforce decisions)
- 8/11 repos match "critical infrastructure"
- 5/11 repos match "legal" use case
- Conformity scores range from 0.5 to 1.0

**Why this matters**: Starting June 2026, deploying high-risk AI without conformity assessment = regulatory violation.

### 5. Agent Trust Graph (30 findings in 3 repos)
Only AgenticQA detects multi-agent trust issues:
- **CrewAI**: 25 findings — unconstrained delegation between agents, missing human-in-loop
- **Semantic Kernel**: 3 findings — privilege escalation paths
- **LangChain**: 2 findings — agent trust chain violations

## Competitive Comparison

| Capability | Snyk | Semgrep | Checkmarx | SonarQube | AgenticQA |
|-----------|------|---------|-----------|-----------|-----------|
| Dependency CVEs | Yes | No | Yes | No | Yes |
| SAST (code patterns) | Limited | Yes | Yes | Yes | Yes |
| Credential detection | Yes | Yes | Yes | Yes | Yes |
| SSRF detection | No | Yes | Limited | Limited | Yes |
| **AI model governance** | No | No | No | No | **Yes** |
| **Shadow AI detection** | No | No | No | No | **Yes** |
| **Prompt injection (code)** | No | No | No | No | **Yes** |
| **RAG injection guard** | No | No | No | No | **Yes** |
| **AI model SBOM** | No | No | No | No | **Yes** |
| **Agent trust graphs** | No | No | No | No | **Yes** |
| **EU AI Act compliance** | No | No | No | No | **Yes** |
| **Bias/fairness detection** | No | No | No | No | **Yes** |
| **Cross-agent data flow** | No | No | No | No | **Yes** |
| Price (annual) | $25k+ | $15k+ | $50k+ | $20k+ | **TBD** |

**AgenticQA provides 8 unique scanning capabilities that no traditional security tool offers.**

## How to Reproduce

```bash
# Clone target repo
git clone --depth 1 https://github.com/langchain-ai/langchain.git /tmp/target

# Run all 13 scanners
python scripts/run_client_scan.py /tmp/target --json --output results.json

# Or fail CI on critical findings
python scripts/run_client_scan.py /tmp/target --fail-on-critical
```

## Methodology Notes

- All scans are pure static analysis (no API keys, no network calls, no code execution)
- Shallow clones (--depth 1) to scan current state only
- 10,000 file cap per scanner to prevent OOM on large monorepos
- Bias/injection findings include test files (which contain intentional examples) — production filtering would reduce counts
- CVE scan requires pip-audit/npm-audit to be installed; returned 0 in this benchmark run
