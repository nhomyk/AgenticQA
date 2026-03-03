# LinkedIn Post — MCP Security Scanner

---

There was no security scanner for MCP servers. So I built one — the first one — and published it to the GitHub Marketplace.

Then I ran it against 5 popular open-source MCP servers to validate it.

Every single one had real, actionable findings.

🔴 CVSS 9.8 — arbitrary JavaScript execution. The LLM supplies the script. No validation. No sandbox. Full RCE controllable by any prompt-injected agent.
🟠 SSRF — unrestricted `url` parameter with no domain allowlist. A compromised agent can reach your AWS metadata endpoint from inside your network.
🟠 Auth credentials logged to stdout on first run. Every log aggregator that captures stdout now has the full bearer token.
🟠 Full host environment — `AWS_SECRET_ACCESS_KEY`, `GITHUB_TOKEN`, `DATABASE_URL` — cloned and forwarded to a spawned subprocess.
🟡 Unpinned `npx -y` supply chain risk. A compromised npm package installs and executes silently on next restart.

These aren't edge cases. They're structural patterns in how MCP tools are built — LLM-controlled arguments flowing into execution, network, and storage sinks with no sanitization layer. Nobody was checking for this automatically.

Now there is. One line:

```yaml
- uses: nhomyk/mcp-scan-action@v1
```

SARIF output to GitHub Security tab. 4 scan engines. No API key. Pure static analysis.

This is part of AgenticQA — an open-source platform I built that does autonomous CI/CD for AI systems: security scanning, EU AI Act compliance, HIPAA PHI detection, self-healing CI, and adversarial red-team hardening. Three GitHub Actions now live on the Marketplace.

Full writeup with all 5 findings in the comments.

🔗 github.com/marketplace/actions/mcp-security-scan

---

#MCPSecurity #ModelContextProtocol #AIAgents #DevSecOps #GitHubActions #AppSec #OpenSource
