I scanned 5 popular MCP servers this week. Every single one had findings.

Not CVEs. Not known vulnerabilities in a database. Structural security patterns that nobody's checking for — because there's no standard tooling for MCP server security yet.

Here's what showed up across a browser automation server, a productivity API connector, a browser DevTools bridge, a vector database plugin, and a search MCP:

**1. Arbitrary JavaScript execution (critical)**
A browser automation MCP registers a tool that calls `page.evaluate(args.script)` — the LLM agent supplies the script, no validation, no sandboxing. This is RCE controllable by any agent with access to the tool — including a prompt-injected one.

```typescript
const result = await page.evaluate(args.script);
```

Risk score: 1.000.

**2. Auth token logged in plaintext (high)**
A major productivity platform's official MCP server generates a random auth token when none is configured and prints it to stdout:

```typescript
console.log(`Generated auth token: ${authToken}`)
```

Anyone capturing that stdout — log aggregators, CI pipelines, container logging — gets the Bearer token for all API operations. The data flow tracer traced the full path: SECRET_SOURCE → SINK_LOGGING [UNSANITIZED]. DataFlow risk: 1.000.

**3. Full process.env forwarded to child processes (high)**
A browser vendor's DevTools MCP copies every environment variable to a spawned subprocess:

```typescript
Object.entries(process.env).forEach(([key, value]) => { env[key] = value; });
```

Every secret on the host — cloud keys, GitHub tokens, API credentials — inherits to the child process. The fix is a three-line allowlist.

**4. SSRF via unrestricted HTTP tools (high)**
The same browser automation server exposes GET/POST/PUT/PATCH/DELETE tools with a user-controlled `url` parameter and no domain allowlist. The HTTP context's `baseURL` is also LLM-controlled. A prompt-injected agent can hit cloud metadata endpoints directly.

**5. Supply chain risk via unpinned npx (medium)**
A vector database vendor's plugin config uses `npx -y @vendor/mcp-server` — no version pin. If the package is compromised on npm, it auto-installs on every client restart.

---

These aren't exotic. They're the natural failure modes of MCP tool design:

- Tools accept LLM-controlled arguments. That's the whole point. But `args.url`, `args.script`, `args.filePath` reaching sinks without validation is the attack surface.
- MCP servers run with the host process's credentials. Every tool in the server has access to everything in `process.env`.
- Tool descriptions are a prompt injection surface. The LLM reads them. Adversarial content in a description is read as instruction.

I built this into a static scanner and wired it into CI. It runs on every push. The scanner learns — each real-world finding adds a pattern to the learned database, which loads on every subsequent scan. After 5 repos: 16 code patterns + 2 config patterns accumulated.

The scanner also runs a data flow tracer that independently tracks credential taint paths without needing to understand MCP structure at all. That's what caught the plaintext token logging.

Full writeup on Medium (link in comments). Scanner is open source in AgenticQA.

---

#MCPSecurity #ModelContextProtocol #AIAgents #AppSec #SecurityEngineering #OpenSource #SSRF #SupplyChainSecurity
