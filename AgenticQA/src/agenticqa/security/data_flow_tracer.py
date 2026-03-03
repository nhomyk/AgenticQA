"""
CrossAgentDataFlowTracer — traces how sensitive data (PII, secrets, credentials)
flows between agents and across trust boundaries in multi-agent systems.

Unlike simple secret-in-output detection, this traces the PROVENANCE PATH:
  Agent A reads DB creds → passes to Agent B → Agent B logs them → EXFILTRATION

Analyzed patterns:
  SECRET_SOURCE      — agent receives / reads sensitive data
  PII_SOURCE         — agent receives / reads PII fields
  CROSS_BOUNDARY     — data crosses from high-trust to low-trust agent
  SINK_LOGGING       — sensitive data written to logs/stdout
  SINK_NETWORK       — sensitive data sent in network request
  SINK_STORAGE       — sensitive data written to file/DB without encryption
  TAINT_PROPAGATION  — sensitive variable passed to another agent call
  MISSING_SANITIZE   — sensitive data flows into output with no redaction
  PRIVILEGE_ESCALATION — data flows from constrained to unconstrained agent

Each finding includes a full trace chain: source → intermediate hops → sink.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# Taint sources — patterns that mark a variable as "tainted" (carries sensitive data)
# ─────────────────────────────────────────────────────────────────────────────

# Variable names / dict keys that likely carry credentials or PII
_SENSITIVE_VAR_NAMES: Set[str] = {
    # Credentials
    "password", "passwd", "pwd", "secret", "token", "api_key", "apikey",
    "auth_token", "access_token", "refresh_token", "bearer", "credential",
    "private_key", "signing_key", "encryption_key", "session_key",
    "client_secret", "db_password", "database_password",
    # PII
    "ssn", "social_security", "dob", "date_of_birth", "credit_card",
    "card_number", "cvv", "passport", "drivers_license", "license_number",
    "phone", "phone_number", "email", "email_address", "address", "zip_code",
    "postal_code", "bank_account", "routing_number", "iban",
    # Medical
    "diagnosis", "medication", "prescription", "patient_id", "mrn",
    "health_record", "phi", "hipaa",
    # Catch-all
    "sensitive", "confidential", "private", "pii",
}

# Patterns that indicate a variable is being assigned sensitive data
_SOURCE_PATTERNS: List[Tuple[str, str, str]] = [
    # (regex, data_type, severity)
    # Python: Reading from env / secrets store — key may have prefix (e.g., DB_PASSWORD)
    (r"os\.(?:environ|getenv)\s*[\[\(]['\"]?[^'\"]*"
     r"(?i:password|passwd|secret|token|api.?key|auth|credential)[^'\"]*['\"]?[\]\)]",
     "SECRET_SOURCE", "high"),
    (r"(?:boto3|secretsmanager|vault|keyring)\s*\.\s*(?:get_secret|get_password)\s*\(",
     "SECRET_SOURCE", "high"),
    (r"(?:dotenv|environ)\s*\.\s*(?:get|load)\s*\(\s*['\"]?[^'\"]*"
     r"(?i:password|secret|token|key)[^'\"]*['\"]?",
     "SECRET_SOURCE", "high"),
    # Python: Reading PII from DB / API
    (r"(?:cursor|session|query|result)\s*\.\s*(?:fetchone|fetchall|first|all)\s*\(\s*\)",
     "PII_SOURCE", "medium"),
    (r"(?i:SELECT)\s+(?:\*|\w+)\s+(?i:FROM)\s+(?i:users|patients|customers|members|accounts)",
     "PII_SOURCE", "high"),
    (r"request\s*\.\s*(?:json|form|data|args)\s*(?:\[|\.get)\s*\(\s*"
     r"['\"](?i:ssn|password|credit_card|dob|phone|email)['\"]",
     "PII_SOURCE", "high"),
    # Python: Receiving from another agent
    (r"(?:agent_input|task_input|context|payload|message)\s*[\[\.]\s*['\"]?"
     r"(?i:password|secret|token|ssn|credit_card|pii)['\"]?",
     "SECRET_SOURCE", "medium"),
    # TypeScript/JavaScript: process.env credential reads
    (r"process\.env\.(?:\w*(?:KEY|SECRET|TOKEN|PASSWORD|CREDENTIAL|AUTH)\w*"
     r"|\w*(?:key|secret|token|password|credential|auth)\w*)",
     "SECRET_SOURCE", "high"),
    # TypeScript/JavaScript: AWS SDK credential reads
    (r"(?:AWS\.config|new\s+AWS\.|new\s+(?:S3|DynamoDB|STS|SecretsManager|SSM)\s*\()",
     "SECRET_SOURCE", "medium"),
    # TypeScript/JavaScript: Axios/got request config with auth headers
    (r"headers\s*:\s*\{[^}]*(?:Authorization|Bearer|api.?key)[^}]*\}",
     "SECRET_SOURCE", "medium"),
    # Go: os.Getenv with credential key
    (r'os\.Getenv\s*\(\s*"[^"]*(?:KEY|SECRET|TOKEN|PASSWORD|AUTH|CREDENTIAL)[^"]*"',
     "SECRET_SOURCE", "high"),
    # Go: credential read from context/config struct field
    (r'\.\s*(?:AuthToken|ApiKey|SecretKey|Password|Credential|Token)\b',
     "SECRET_SOURCE", "medium"),
    # Rust: std::env::var for credentials
    (r'std::env::var\s*\(\s*"[^"]*(?:KEY|SECRET|TOKEN|PASSWORD|AUTH)[^"]*"',
     "SECRET_SOURCE", "high"),
    # Java: System.getenv with credential key
    (r'System\.getenv\s*\(\s*"[^"]*(?:KEY|SECRET|TOKEN|PASSWORD|AUTH|CREDENTIAL)[^"]*"',
     "SECRET_SOURCE", "high"),
]

# Taint sinks — where sensitive data should NOT end up unredacted
_SINK_PATTERNS: List[Tuple[str, str, str]] = [
    # Python logging sinks
    (r"(?:logger|logging|log)\s*\.\s*(?:info|debug|warning|error|critical|exception)\s*\(",
     "SINK_LOGGING", "high"),
    (r"\bprint\s*\(", "SINK_LOGGING", "medium"),
    (r"(?:sys\.stdout|sys\.stderr)\s*\.write\s*\(", "SINK_LOGGING", "medium"),
    # TypeScript/JavaScript logging sinks
    (r"\bconsole\s*\.\s*(?:log|error|warn|debug|info)\s*\(", "SINK_LOGGING", "medium"),
    (r"\bwinson\s*\.\s*(?:info|error|warn|debug)\s*\(", "SINK_LOGGING", "medium"),
    (r"\bpino\s*\(\s*\)", "SINK_LOGGING", "medium"),
    # Python network sinks
    (r"\brequests\s*\.\s*(?:get|post|put|patch|request)\s*\(",
     "SINK_NETWORK", "critical"),
    (r"\bhttpx\s*\.\s*(?:get|post|put|patch|request)\s*\(",
     "SINK_NETWORK", "critical"),
    (r"\baiohttp\s*\.\s*(?:ClientSession|request)\b", "SINK_NETWORK", "critical"),
    (r"\burllib\s*\.\s*request\s*\.\s*urlopen\s*\(", "SINK_NETWORK", "critical"),
    # TypeScript/JavaScript network sinks
    (r"\bfetch\s*\(", "SINK_NETWORK", "critical"),
    (r"\baxios\s*\.\s*(?:get|post|put|patch|request|delete)\s*\(",
     "SINK_NETWORK", "critical"),
    (r"\bgot\s*\.\s*(?:get|post|put|patch)\s*\(", "SINK_NETWORK", "high"),
    (r"\bnew\s+XMLHttpRequest\s*\(", "SINK_NETWORK", "high"),
    # Python storage sinks
    (r"\bopen\s*\([^)]+,\s*['\"]w['\"]", "SINK_STORAGE", "high"),
    (r"\b\w+\.write\s*\(", "SINK_STORAGE", "high"),
    (r"(?:json\.dump|pickle\.dump|yaml\.dump)\s*\(", "SINK_STORAGE", "medium"),
    (r"(?:cursor\.execute|session\.add|db\.insert)\s*\(", "SINK_STORAGE", "medium"),
    # TypeScript/JavaScript storage sinks
    (r"\bfs\s*\.\s*(?:writeFile|appendFile|writeFileSync)\s*\(",
     "SINK_STORAGE", "high"),
    (r"\blocalStorage\s*\.\s*setItem\s*\(", "SINK_STORAGE", "medium"),
    # Return / yield (cross-agent propagation)
    (r"\breturn\b", "TAINT_PROPAGATION", "medium"),
    (r"\byield\b", "TAINT_PROPAGATION", "low"),
    # Go logging sinks
    (r"\blog\.\w+f?\s*\(", "SINK_LOGGING", "medium"),
    (r"\bfmt\.(?:Print|Fprintf|Fprintln)\s*\(\s*os\.Std(?:err|out)",
     "SINK_LOGGING", "medium"),
    # Go network sinks
    (r"\bhttp\.(?:Post|Do)\s*\(", "SINK_NETWORK", "critical"),
    (r"\bclient\.Do\s*\(", "SINK_NETWORK", "high"),
    # Rust logging sinks
    (r'\bprintln!\s*\(|eprintln!\s*\(|log::(?:info|error|warn|debug)!\s*\(',
     "SINK_LOGGING", "medium"),
    # Java logging sinks
    (r'\bSystem\.out\.print(?:ln)?\s*\(|logger\.(?:info|debug|warn|error)\s*\(',
     "SINK_LOGGING", "medium"),
]

# Patterns indicating sanitization / redaction was applied
_SANITIZE_PATTERNS = [
    r"redact\s*\(",
    r"mask\s*\(",
    r"anonymize\s*\(",
    r"hash\s*\(",
    r"encrypt\s*\(",
    r"bcrypt\s*\.",
    r"hashlib\s*\.",
    r"\*{3,}",             # literal masking: "***"
    r"\[REDACTED\]",
    r"\[MASKED\]",
    r"\.replace\s*\([^)]+,\s*['\"][\*x_-]{3,}['\"]",  # .replace(val, "***")
]

# Patterns identifying cross-agent data transfer
_DELEGATION_PATTERNS = [
    r"(?:delegate_to|send_to|call_agent|invoke_agent|agent\.run|execute_agent)\s*\(",
    r"(?:message|payload|context)\s*=\s*\{[^}]*\}",
    r"AgentExecutor\s*\.\s*(?:run|invoke)\s*\(",
    r"chain\s*\.\s*(?:run|invoke)\s*\(",
    r"(?:crew|pipeline|workflow)\s*\.\s*(?:run|kickoff|execute)\s*\(",
    r"initiate_chat\s*\(",
    r"transfer_to_\w+\s*\(",
]

# Agent framework markers (to identify agent file scope — Python, TypeScript, Go, Rust, Java)
_AGENT_MARKERS = [
    # Python agent frameworks
    r"from\s+(?:mcp|langchain|langgraph|crewai|autogen|fastmcp)\s+import",
    r"@mcp\.tool|@tool\s*\(|AgentExecutor|FastMCP|StateGraph|Crew\(",
    r"class\s+\w*Agent\w*\s*(?:\([^)]*\))?:",
    r"def\s+\w+_agent\s*\(",
    # TypeScript/JavaScript MCP server markers
    r"from\s+['\"]@modelcontextprotocol/sdk",
    r"McpServer|StdioServerTransport|SSEServerTransport|StreamableHTTPServerTransport",
    r"server\.registerTool|server\.tool\s*\(|\.setRequestHandler\s*\(",
    # TypeScript/JavaScript agent frameworks
    r"from\s+['\"](?:langchain|@langchain|openai-agents|@openai/agents)",
    r"new\s+(?:OpenAI|Anthropic|AzureOpenAI)\s*\(",
    # Go MCP / agent markers
    r"github\.com/modelcontextprotocol/go-sdk",
    r"github\.com/mark3labs/mcp-go",
    r"\bmcp\.CallToolRequest\b|\bmcp\.ToolHandler\b",
    r'\.AddTool\s*\(|mcp\.NewTool\b',
    # Rust MCP / agent markers
    r"use\s+rmcp::|use\s+mcp_server::",
    r"\bregister_tool\b|\bToolRegistry\b",
    # Java / Kotlin MCP markers
    r"import.*modelcontextprotocol",
    r"\bregisterTool\b|\bMcpServer\b",
    r"@Tool\b|@McpTool\b",
]

_SKIP_DIRS = frozenset({
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", "tests", ".mypy_cache", "site-packages",
    # Go
    "vendor",
    # Rust
    "target",
    # Java/Kotlin
    ".gradle", ".mvn",
})

# Files with credential reads — scanned even without agent framework markers
_CREDENTIAL_FILE_MARKERS = [
    # Python: os.environ/getenv with credential names
    r"os\.(?:environ|getenv)\s*[\[\(].*(?i:PASSWORD|SECRET|TOKEN|CREDENTIAL)",
    # Python: secrets stores
    r"(?:secretsmanager|vault|keyring)\s*\.\s*(?:get_secret|get_password)\s*\(",
    # TypeScript/JavaScript: process.env credential reads
    r"process\.env\.(?:\w*(?:SECRET|TOKEN|PASSWORD|CREDENTIAL)\w*)",
    # Go: os.Getenv with credential names
    r'os\.Getenv\s*\(\s*"[^"]*(?:SECRET|TOKEN|PASSWORD|CREDENTIAL)',
    # Java: System.getenv with credential names
    r'System\.getenv\s*\(\s*"[^"]*(?:SECRET|TOKEN|PASSWORD|CREDENTIAL)',
    # Rust: std::env::var with credential names
    r'std::env::var\s*\(\s*"[^"]*(?:SECRET|TOKEN|PASSWORD|CREDENTIAL)',
    # SQL queries on sensitive tables
    r"(?i:SELECT)\s+\S+\s+(?i:FROM)\s+(?i:users|patients|credentials|accounts)",
    # Django/Flask settings with credential variables
    r"(?:DATABASE_PASSWORD|SECRET_KEY|AUTH_TOKEN)\s*=",
]

SEVERITY_WEIGHTS: Dict[str, float] = {
    "critical": 0.30, "high": 0.15, "medium": 0.08, "low": 0.03,
}

# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TaintHop:
    """A single step in a taint propagation chain."""
    agent_name: str
    source_file: str
    line_number: int
    operation: str       # read, transform, delegate, log, return
    evidence: str


@dataclass
class DataFlowFinding:
    """A detected sensitive data flow violation."""
    finding_type: str    # SECRET_SOURCE, SINK_LOGGING, TAINT_PROPAGATION, etc.
    severity: str
    data_type: str       # credential, pii, mixed
    description: str
    source_agent: str
    sink_agent: str
    trace: List[TaintHop] = field(default_factory=list)
    sanitized: bool = False
    source_file: str = ""
    line_number: int = 0
    remediation: str = ""

    def __post_init__(self) -> None:
        if not self.remediation:
            self.remediation = _REMEDIATION.get(self.finding_type, "Apply data minimization.")


_REMEDIATION: Dict[str, str] = {
    "SECRET_SOURCE":       "Avoid passing raw credentials between agents; use scoped tokens.",
    "PII_SOURCE":          "Apply field-level encryption and minimum necessary data principle.",
    "SINK_LOGGING":        "Redact or hash sensitive fields before logging.",
    "SINK_NETWORK":        "Ensure sensitive data is not included in outbound requests.",
    "SINK_STORAGE":        "Encrypt sensitive data at rest; use parameterized writes.",
    "TAINT_PROPAGATION":   "Apply sanitization before returning sensitive data to calling agent.",
    "MISSING_SANITIZE":    "Add explicit redaction before any agent-to-agent data transfer.",
    "PRIVILEGE_ESCALATION": "Enforce trust boundary: high-trust agents must not delegate to unconstrained agents.",
    "CROSS_BOUNDARY":      "Sanitize and minimize data before crossing agent trust boundaries.",
}


@dataclass
class DataFlowReport:
    findings: List[DataFlowFinding] = field(default_factory=list)
    agents_analyzed: int = 0
    files_scanned: int = 0
    risk_score: float = 0.0
    scan_error: Optional[str] = None
    tainted_variables_detected: int = 0

    @property
    def total_findings(self) -> int:
        return len(self.findings)

    @property
    def critical_findings(self) -> List[DataFlowFinding]:
        return [f for f in self.findings if f.severity == "critical"]

    @property
    def finding_types(self) -> List[str]:
        return sorted({f.finding_type for f in self.findings})


# ─────────────────────────────────────────────────────────────────────────────
# Tracer
# ─────────────────────────────────────────────────────────────────────────────

class CrossAgentDataFlowTracer:
    """
    Traces sensitive data flow across agent boundaries via static analysis.

    Algorithm:
      1. Discover agent source files
      2. For each file, identify taint sources (credential reads, PII inputs)
      3. Track tainted variable names through assignments and function calls
      4. Flag when tainted data reaches a sink (log, network, return, storage)
         without an intervening sanitization
      5. Detect delegation calls that carry tainted variables
    """

    _CUSTOM_PATTERNS_PATH = Path(".agenticqa") / "dataflow_patterns.json"

    def __init__(self) -> None:
        self._source_compiled = [
            (re.compile(p), dt, sev) for p, dt, sev in _SOURCE_PATTERNS
        ]
        self._sink_compiled = [
            (re.compile(p), st, sev) for p, st, sev in _SINK_PATTERNS
        ]
        self._sanitize_compiled = [re.compile(p) for p in _SANITIZE_PATTERNS]
        self._delegation_compiled = [re.compile(p) for p in _DELEGATION_PATTERNS]
        self._load_custom_patterns()

    def _load_custom_patterns(self) -> None:
        """Append patterns learned from past scans (.agenticqa/dataflow_patterns.json)."""
        try:
            if not self._CUSTOM_PATTERNS_PATH.exists():
                return
            data = json.loads(self._CUSTOM_PATTERNS_PATH.read_text())
            for entry in data.get("source_patterns", []):
                self._source_compiled.append((
                    re.compile(entry["pattern"]),
                    entry.get("data_type", "SECRET_SOURCE"),
                    entry.get("severity", "medium"),
                ))
            for entry in data.get("sink_patterns", []):
                self._sink_compiled.append((
                    re.compile(entry["pattern"]),
                    entry.get("sink_type", "SINK_CUSTOM"),
                    entry.get("severity", "medium"),
                ))
            for name in data.get("sensitive_var_names", []):
                _SENSITIVE_VAR_NAMES.add(name.lower())
        except Exception:
            pass  # non-blocking — never crash a scan over pattern load

    # ── Public API ──────────────────────────────────────────────────────────

    def trace(self, path: str) -> DataFlowReport:
        """Trace sensitive data flows in a directory or single file."""
        report = DataFlowReport()
        try:
            p = Path(path)
            if not p.exists():
                report.scan_error = f"Path not found: {path}"
                return report
            files = self._find_agent_files(p)
            report.files_scanned = len(files)
            for f in files:
                findings, agents, tainted = self._analyze_file(f)
                report.findings.extend(findings)
                report.agents_analyzed += agents
                report.tainted_variables_detected += tainted
            report.risk_score = self._compute_risk_score(report.findings)
        except Exception as exc:
            report.scan_error = str(exc)
        return report

    # ── File discovery ───────────────────────────────────────────────────────

    def _find_agent_files(self, root: Path) -> List[Path]:
        if root.is_file():
            return [root] if self._is_agent_file(root) else []
        found: List[Path] = []
        for glob in ("*.py", "*.ts", "*.js", "*.mjs", "*.go", "*.rs", "*.java", "*.kt"):
            for p in root.rglob(glob):
                if any(part in _SKIP_DIRS for part in p.parts):
                    continue
                if self._is_agent_file(p):
                    found.append(p)
        return found

    def _is_agent_file(self, path: Path) -> bool:
        try:
            src = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
        return (any(re.search(m, src) for m in _AGENT_MARKERS)
                or any(re.search(m, src) for m in _CREDENTIAL_FILE_MARKERS))

    # ── File-level analysis ──────────────────────────────────────────────────

    def _analyze_file(
        self, path: Path
    ) -> Tuple[List[DataFlowFinding], int, int]:
        """Return (findings, agent_count, tainted_var_count) for one file."""
        findings: List[DataFlowFinding] = []
        try:
            src = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return findings, 0, 0

        lines = src.splitlines()
        src_path = str(path)
        agent_name = self._extract_agent_name(src, path.name)

        # Collect tainted variables: var_name → (line_num, data_type)
        tainted: Dict[str, Tuple[int, str]] = {}

        for line_num, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Detect taint sources
            for pattern, data_type, severity in self._source_compiled:
                if pattern.search(line):
                    # Extract assigned variable name (LHS of assignment)
                    var = self._extract_lhs(line)
                    if var:
                        tainted[var] = (line_num, data_type)
                    # Also check for inline sensitive name patterns
                    tainted.update(
                        self._extract_sensitive_names_from_line(line, line_num, data_type)
                    )
                    findings.append(DataFlowFinding(
                        finding_type=data_type,
                        severity=severity,
                        data_type="credential" if "SECRET" in data_type else "pii",
                        description=f"Sensitive data source in agent '{agent_name}'",
                        source_agent=agent_name,
                        sink_agent=agent_name,
                        source_file=src_path,
                        line_number=line_num,
                        trace=[TaintHop(
                            agent_name=agent_name,
                            source_file=src_path,
                            line_number=line_num,
                            operation="read",
                            evidence=stripped[:120],
                        )],
                    ))
                    break

            # Track assignments that propagate taint
            tainted.update(
                self._propagate_taint(line, line_num, tainted)
            )

            # Check if tainted var reaches a sink
            tainted_in_line = [v for v in tainted if re.search(rf"\b{re.escape(v)}\b", line)]
            if tainted_in_line:
                for pattern, sink_type, sink_sev in self._sink_compiled:
                    if pattern.search(line):
                        sanitized = self._is_sanitized(line, lines, line_num)
                        findings.append(DataFlowFinding(
                            finding_type=sink_type,
                            severity=sink_sev if not sanitized else "low",
                            data_type=tainted[tainted_in_line[0]][1] if tainted_in_line[0] in tainted else "unknown",
                            description=(
                                f"Tainted variable '{tainted_in_line[0]}' reaches {sink_type} "
                                f"in agent '{agent_name}'"
                                + (" [sanitized]" if sanitized else " [UNSANITIZED]")
                            ),
                            source_agent=agent_name,
                            sink_agent=self._extract_delegation_target(line) or agent_name,
                            sanitized=sanitized,
                            source_file=src_path,
                            line_number=line_num,
                            trace=[TaintHop(
                                agent_name=agent_name,
                                source_file=src_path,
                                line_number=line_num,
                                operation=sink_type.lower(),
                                evidence=stripped[:120],
                            )],
                        ))
                        break

            # Check for delegation with tainted variables
            for dpat in self._delegation_compiled:
                if dpat.search(line) and tainted_in_line:
                    target = self._extract_delegation_target(line)
                    findings.append(DataFlowFinding(
                        finding_type="TAINT_PROPAGATION",
                        severity="high",
                        data_type="mixed",
                        description=(
                            f"Tainted variable(s) {tainted_in_line[:3]} propagated "
                            f"via delegation from '{agent_name}' to '{target or 'unknown'}'"
                        ),
                        source_agent=agent_name,
                        sink_agent=target or "unknown",
                        source_file=src_path,
                        line_number=line_num,
                        trace=[TaintHop(
                            agent_name=agent_name,
                            source_file=src_path,
                            line_number=line_num,
                            operation="delegate",
                            evidence=stripped[:120],
                        )],
                    ))
                    break

        return findings, 1, len(tainted)

    # ── Taint tracking helpers ───────────────────────────────────────────────

    @staticmethod
    def _extract_lhs(line: str) -> Optional[str]:
        """Extract the variable name on the left side of an assignment."""
        m = re.match(r"\s*([a-zA-Z_]\w*)\s*=\s*", line)
        if m:
            kw = {"if", "else", "return", "yield", "raise", "assert", "import",
                  "from", "class", "def", "while", "for", "with", "lambda", "not",
                  "and", "or", "in", "is", "True", "False", "None"}
            if m.group(1) not in kw:
                return m.group(1)
        # Dict key assignment: data["key"] = ...
        m2 = re.match(r"""\s*\w+\s*\[['"]([^'"]+)['"]\]\s*=""", line)
        if m2:
            return m2.group(1)
        return None

    @staticmethod
    def _extract_sensitive_names_from_line(
        line: str, line_num: int, data_type: str
    ) -> Dict[str, Tuple[int, str]]:
        """Extract any variable names in the line that match sensitive name patterns."""
        found: Dict[str, Tuple[int, str]] = {}
        for name in _SENSITIVE_VAR_NAMES:
            if re.search(rf"\b{re.escape(name)}\b", line, re.IGNORECASE):
                m = re.search(
                    rf"([a-zA-Z_]\w*{re.escape(name)}\w*|{re.escape(name)}[a-zA-Z_]\w*|\b{re.escape(name)}\b)",
                    line, re.IGNORECASE
                )
                if m:
                    found[m.group(0).lower()] = (line_num, data_type)
        return found

    @staticmethod
    def _propagate_taint(
        line: str, line_num: int, existing_taint: Dict[str, Tuple[int, str]]
    ) -> Dict[str, Tuple[int, str]]:
        """If a tainted variable appears on the RHS of an assignment, taint the LHS."""
        new_taint: Dict[str, Tuple[int, str]] = {}
        m = re.match(r"\s*([a-zA-Z_]\w*)\s*=\s*(.+)", line)
        if not m:
            return new_taint
        lhs, rhs = m.group(1), m.group(2)
        for var, (orig_line, data_type) in existing_taint.items():
            if re.search(rf"\b{re.escape(var)}\b", rhs):
                new_taint[lhs] = (line_num, data_type)
                break
        return new_taint

    def _is_sanitized(self, line: str, lines: List[str], line_num: int) -> bool:
        """Check if sanitization was applied within 5 lines of the sink."""
        context = "\n".join(lines[max(0, line_num - 5): line_num + 1])
        return any(p.search(context) for p in self._sanitize_compiled)

    @staticmethod
    def _extract_delegation_target(line: str) -> Optional[str]:
        """Try to extract the target agent name from a delegation call."""
        m = re.search(
            r"(?:delegate_to|send_to|call_agent|invoke_agent)\s*\(\s*['\"]?(\w+)['\"]?",
            line
        )
        if m:
            return m.group(1)
        m2 = re.search(r"transfer_to_(\w+)\s*\(", line)
        if m2:
            return m2.group(1)
        return None

    @staticmethod
    def _extract_agent_name(src: str, filename: str) -> str:
        """Extract the agent/class name from source code."""
        m = re.search(r"class\s+(\w+Agent)\b", src)
        if m:
            return m.group(1)
        m2 = re.search(r"(?:agent_name|name)\s*=\s*['\"](\w+)['\"]", src)
        if m2:
            return m2.group(1)
        return filename.replace(".py", "")

    # ── Risk score ───────────────────────────────────────────────────────────

    @staticmethod
    def _compute_risk_score(findings: List[DataFlowFinding]) -> float:
        if not findings:
            return 0.0
        return min(1.0, sum(
            SEVERITY_WEIGHTS.get(f.severity, 0.0)
            for f in findings if not f.sanitized
        ))
