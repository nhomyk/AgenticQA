# The Agentic Development Lifecycle: I Built a Loop That Ships Features Without a Human

### From "describe it" to "SHIP IT" in one autonomous cycle — what happens when every phase of software delivery is governed, tested, and self-healing by default

---

Software development has lifecycles. SDLC. CI/CD. DevSecOps. Each one was invented to answer a question that the previous framework couldn't: How do we move faster without breaking things?

But every lifecycle we've ever built assumes one thing: a human in the loop at every critical decision point. A human reviews the PR. A human approves the deploy. A human decides if the test failure is blocking.

AI agents change that assumption fundamentally. And almost nobody is talking about what the development lifecycle looks like when the agent *is* the loop.

I've been building that answer for the past year. I'm calling it the **ADLC — the Agentic Development Lifecycle**.

---

## What is the ADLC?

The traditional SDLC has phases: Requirements → Design → Implementation → Testing → Deployment → Maintenance. Humans hand off between each one.

The ADLC is a closed loop. There are no handoffs because there is no boundary between phases. A single agent-governed cycle handles:

1. **Describe** — a non-technical user types what they want
2. **Generate** — an LLM writes the implementation
3. **Scan** — static security analysis on the generated code
4. **Test** — headless tests auto-generated and run immediately
5. **Self-Heal** — if tests fail, the code is rewritten and re-validated
6. **Ship** — SHIP IT verdict issued with full provenance chain
7. **Learn** — every outcome feeds back into the system's knowledge

Then it cycles. The next feature starts with richer baseline data, better patterns, and a more hardened governance layer than the last.

That's the ADLC. Not a pipeline. A cycle.

---

## Why This Is Different From "AI-Assisted Development"

The phrase "AI-assisted development" implies a human using AI as a tool — Copilot suggestions, ChatGPT for boilerplate. The human is still the decision-maker. The AI is autocomplete at scale.

The ADLC inverts that. The agent is the decision-maker across the entire cycle. The human's role shifts from *doing the work* to *describing the outcome* — and then approving or overriding the verdict at the end.

The difference matters because of what happens in the middle:

```
Traditional:  human → writes code → human → writes tests → human → reviews PR → human → deploys

ADLC:         human → describes → [autonomous loop] → human ← verdict
                                       ↑
                              AgenticQA cycle:
                              generate → scan → test → heal → certify
```

Everything between description and verdict is governed autonomously. The human is bookending a cycle, not managing a pipeline.

---

## The Loop in Practice: What I Built Today

Here's what the ADLC looks like in practice. I'll walk through what actually runs when a user types a feature description into AgenticQA's landing page.

### The Interface

The landing page was built with one design constraint: a non-technical product manager should feel as comfortable using it as a senior engineer. The input is a single textarea. No configuration, no required fields, no documentation to read first.

```
┌─────────────────────────────────────────────────────┐
│  What would you like to build?                      │
│                                                     │
│  Add a user profile page with avatar upload         │
│  and bio editing                                    │
│                                    [ Build & Validate → ] │
└─────────────────────────────────────────────────────┘
```

The moment you hit submit, the ADLC cycle begins.

### Phase 1: Architecture Scan

Before any code is generated, AgenticQA scans the repository the feature will land in. It builds a real-time picture of the attack surface:

- How many external HTTP integrations exist?
- Are there shell execution paths?
- Where are the auth boundaries?
- What's the current test coverage?

This isn't boilerplate security theater. The architecture scan determines how strict the security gate will be for the generated feature. High attack surface repo + new external HTTP integration = heightened scrutiny.

Attack surface score: **4/100** for a minimal FastAPI backend. Clean baseline.

### Phase 2: Code Generation

The LLM generates a complete Streamlit UI implementation. Not a stub — a full working component that:

- Calls the FastAPI backend at the correct API paths
- Handles connection errors gracefully
- Renders a task list with complete/delete actions
- Uses environment variables for the API base URL (not hardcoded strings)

60 lines. Correct on the first pass. The LLM was given the architecture context from Phase 1, so it knew what endpoints existed and how they were shaped.

### Phase 3: Security Scan

The generated code runs through 12 integration category detectors:

| Category | Finding | Verdict |
|---|---|---|
| `EXTERNAL_HTTP` | `requests.post()` to backend | **INFO** (expected — UI layer) |
| `ENV_SECRETS` | `os.environ.get("API_BASE")` | **INFO** (URL config, not credential) |
| `SHELL_EXEC` | none | — |
| `DATABASE` | none | — |

This is where context-aware severity matters. The same `requests.post()` call that would be `HIGH` in a backend service is correctly classified as `INFO` in a frontend component. The scanner knows the difference between a UI making an API call (expected) and a backend making an unexpected outbound connection (suspicious).

**0 critical. 0 high. Attack surface: 8/100.**

### Phase 4: Test Generation + Execution

AgenticQA generates a full test suite for the generated code — headlessly, without spinning up a browser:

```python
# Generated automatically — developer never wrote this
def test_app_renders_without_exception():
    with patch("requests.get", return_value=_mock_ok({"tasks": []})):
        at = AppTest.from_file(str(app_file))
        at.run(timeout=10)
        assert not at.exception

def test_app_has_no_error_elements():
    # Verifies no st.error() fired on normal render
    ...

def test_app_handles_api_down():
    # Resilience test — what happens when backend is unreachable?
    with patch("requests.get", side_effect=ConnectionError):
        at.run(timeout=10)
        assert len(at.warning) >= 1  # graceful degradation
```

3 tests. All passing. First run.

### Phase 5: The Self-Healing Loop

What if they hadn't all passed?

```python
# What AgenticQA does autonomously on test failure:

for attempt in range(max_retries):
    if all_tests_pass:
        break

    # 1. LLM analyzes failing test output
    fixed_code = claude_haiku.rewrite(
        original_code=generated_ui,
        failing_tests=failing_test_names,
        error_output=pytest_output
    )

    # 2. Security re-scan on the fix (prevent regression)
    if security_scan(fixed_code).critical > 0:
        verdict = "REVIEW REQUIRED"
        break

    # 3. Re-run tests against the fixed code
    results = run_ui_tests(fixed_code)
```

No human sees any of this. The system found a problem, diagnosed it, generated a fix, validated the fix didn't introduce new vulnerabilities, and verified the fix worked — all before the verdict was rendered.

### Phase 6: The Verdict

```
┌──────────────────────────────────────────────────────┐
│  ✅ SHIP IT                                          │
│  ──────────────────────────────────────────────────  │
│  Security    0 critical · 0 high                     │
│  Tests       3/3 passed                              │
│  Coverage    0% → 33%                                │
│  Time        0.7s                                    │
│                                                      │
│  [ View in Dashboard → ]    [ New Feature ]          │
└──────────────────────────────────────────────────────┘
```

0.7 seconds from description to SHIP IT. End to end. No human touched anything in between.

### Phase 7: The Loop Closes — Learning

This is what makes it a *cycle* rather than a pipeline.

Every execution feeds back into AgenticQA's learning system:

- The architecture scan updates the repo's risk profile
- Test pass/fail rates adjust the adaptive thresholds for future scans
- Developer attribution links outcomes to patterns in specific files
- The org-level memory accumulates cross-repo fix rate intelligence

The next feature run starts smarter. The system has seen this repo before. It knows what's safe, what's risky, and what patterns reliably succeed. It doesn't repeat its past mistakes — it builds on its past successes.

---

## The Governance Layer: Why This Isn't Reckless

If the ADLC automates decisions that humans used to make, the obvious question is: what stops it from making catastrophic decisions autonomously?

The answer is the **Agent Constitution** — a machine-readable governance document that every agent checks before every action:

```bash
# Pre-action check — runs before any destructive operation
curl -X POST http://localhost:8000/api/system/constitution/check \
  -d '{"action_type": "delete", "context": {"ci_status": "FAILED"}}'
# → {"verdict": "DENY", "law": "T1-001", "reason": "Destructive op blocked: CI not passing"}
```

**Six Tier 1 laws** that can never be overridden:

- No destructive operations without CI passing
- Delegation depth ≤ 3 (no infinite agent chains)
- No PII in logs
- No traceless external writes
- No self-modification of governance files (the most important one)
- Per-agent file scope enforcement

The governance isn't aspirational. It's enforced in under 5ms, before every action, with zero exceptions. The loop doesn't run without it.

---

## The Two Interfaces: One Product, Two Users

The ADLC needs two surfaces: one for non-technical users who just want to describe a feature and get a SHIP IT, and one for engineering teams who want deep visibility into every scan, every agent decision, every compliance finding.

**The Landing Page** (`localhost:8000`) is the first surface. Minimal. Dark. One input. One button. Everything else hidden behind an "Advanced" toggle.

**The Dashboard** (`localhost:8501`) is the second. 16 pages covering GraphRAG agent intelligence, EU AI Act conformity scoring, HIPAA PHI scanning, Red Team adversarial testing, temporal violation graphs, and LLM model regression detection.

Same platform. Same pipeline. Different entry point.

This is the gap that no existing QA or DevSecOps tool fills. GitHub Actions is for engineers. Snyk is for security teams. Linear is for product managers. AgenticQA is the first platform that serves all three from a single agentic loop.

---

## The Metrics That Matter

When I ran the ADLC cycle against a fresh FastAPI codebase with zero frontend, zero tests, and zero security tooling:

| Before ADLC | After one cycle |
|---|---|
| Test coverage: 0% | Test coverage: 33%+ |
| UI: none | Streamlit UI: 60 lines, 3 tests |
| Security scan: never run | Attack surface: 8/100 |
| Time: required a sprint | Time: 0.7 seconds |

That's one cycle. The system gets better at every subsequent cycle because it's learning from every outcome.

After 50 cycles: 96% pattern confidence. Adaptive thresholds tuned to the specific failure modes of the specific repo. Developer risk profiles built from git blame attribution. Cross-repo org memory accumulating the institutional knowledge that usually lives in senior engineers' heads.

---

## What the ADLC Is Not

**It's not replacing engineers.** The ADLC handles the mechanical execution of software delivery — the parts that are repetitive, error-prone, and slow when humans do them manually. Engineers are freed to do the things AI systems are bad at: architectural judgment, user empathy, cross-functional negotiation, deciding what to build in the first place.

**It's not another AI coding assistant.** GitHub Copilot generates code in your editor. AgenticQA generates, validates, tests, secures, and certifies code in an autonomous loop. The human decision point is the description at the start and the verdict approval at the end. Everything in the middle is governed.

**It's not complete.** The ADLC I've built today handles the generate → scan → test → self-heal cycle for frontend features. The full vision includes backend scaffolding, database migrations, infrastructure provisioning, and cross-service dependency management — all governed by the same constitutional layer.

---

## Why This Matters Now

We are at the beginning of the agentic era in software. Every major AI lab is shipping autonomous coding capabilities. Every engineering team is asking what happens to their workflows when agents can write production code.

The question isn't whether agents will write code. They already do. The question is whether the development lifecycle around them will be rigorous enough to trust the output.

The ADLC is my answer to that question. Governance first. Learning loop built in. Constitutional enforcement before every action. Full provenance chain on every output. Self-healing when things go wrong.

Not a Copilot. A cycle.

---

## Try It

```bash
git clone https://github.com/nhomyk/AgenticQA.git
cd AgenticQA
pip install -e .

# Start the ADLC control plane
python agent_api.py

# Open the landing page — describe a feature, watch the cycle
open http://localhost:8000

# Or run the full demo from CLI (no API key needed)
python run_demo.py

# Open the dashboard for full visibility
streamlit run dashboard/app.py
# → http://localhost:8501
```

The demo creates a minimal FastAPI backend with no tests and no frontend, runs the full ADLC cycle against it, and returns a SHIP IT verdict in under 5 seconds. Every step is visible. Every decision is logged. Every output is signed.

That's the Agentic Development Lifecycle. The loop that ships features without a human in the middle — and never without governance around every edge.

---

*AgenticQA is open source. 1,538 unit tests. Python 3.8+. MIT licensed.*

*The landing page lives at `GET /`. The dashboard lives at `streamlit run dashboard/app.py`. The loop runs everywhere.*
