"""
ArchitectureScanner — maps every integration point in a codebase.

Problem
-------
Most AI users don't understand distributed systems, data flows, middleware,
or agent architecture.  Before they can trust a product, they need answers to:

  "What external systems does this code talk to?"
  "Where could an attacker inject malicious data?"
  "Which of these dangerous areas have tests?"

Solution
--------
Walk any repo (Python, TypeScript, JavaScript, Swift, Go, Java, YAML, JSON).
For every file, detect 12 integration categories using pre-compiled patterns.
Return plain-English findings any non-engineer can read, cross-referenced with
the test files that cover them.

Integration categories
----------------------
SHELL_EXEC        — runs OS commands           CWE-78  (critical)
EXTERNAL_HTTP     — outbound web requests      CWE-918 (high)
DATABASE          — reads/writes a database    CWE-89  (high)
FILE_SYSTEM       — writes files to disk       CWE-73  (medium)
ENV_SECRETS       — reads environment secrets  CWE-798 (high)
SERIALIZATION     — deserialises external data CWE-502 (high)
NETWORK_SOCKET    — raw TCP/Unix sockets       CWE-601 (high)
CLOUD_SERVICE     — 3rd-party cloud SDK calls  CWE-306 (medium)
AUTH_BOUNDARY     — authentication/authz code  CWE-306 (medium)
MIDDLEWARE        — HTTP middleware/routing     CWE-284 (medium)
EVENT_BUS         — async event / message queue CWE-400 (low)
MCP_TOOL          — MCP server tool exposure   CWE-284 (medium)

Usage
-----
    from agenticqa.security.architecture_scanner import ArchitectureScanner

    result = ArchitectureScanner().scan("/path/to/repo")
    print(result.plain_english_report())
    # Also available: result.to_dict(), result.by_category(),
    #                 result.untested_areas, result.critical_areas
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Skip directories ──────────────────────────────────────────────────────────

_SKIP_DIRS = {
    "node_modules", ".venv", "venv", "__pycache__", ".git",
    "dist", "build", "DerivedData", "vendor", "target",
    ".gradle", ".mvn", ".next", "out", "coverage", ".nyc_output",
}

_SOURCE_EXTENSIONS = {
    ".py", ".ts", ".js", ".tsx", ".jsx", ".mjs", ".cjs",
    ".swift", ".go", ".java", ".kt", ".rs",
    ".yaml", ".yml", ".json",
}

# ── Severity weights (for attack_surface_score 0-100) ─────────────────────────

_SEVERITY_WEIGHTS = {"critical": 20, "high": 10, "medium": 5, "low": 2}

# ── Plain-English category descriptions ───────────────────────────────────────

_PLAIN_ENGLISH: Dict[str, str] = {
    "SHELL_EXEC": (
        "This code runs system commands directly on the server. "
        "If an attacker can control any part of these commands, they can run "
        "arbitrary code and take over the machine (Remote Code Execution)."
    ),
    "EXTERNAL_HTTP": (
        "This code makes outbound web requests to external services. "
        "An attacker could redirect these to internal services to steal data "
        "(Server-Side Request Forgery, SSRF), or intercept sensitive data in transit."
    ),
    "DATABASE": (
        "This code reads from or writes to a database. "
        "Without parameterized queries, attackers can inject SQL commands to "
        "steal, modify, or delete all stored data."
    ),
    "FILE_SYSTEM": (
        "This code writes files to disk. "
        "If an attacker controls the file path or content, they can overwrite "
        "critical files or plant malicious code (Path Traversal)."
    ),
    "ENV_SECRETS": (
        "This code reads secrets from environment variables (API keys, passwords, tokens). "
        "If these are logged, stored in version control, or exposed in errors, "
        "attackers gain access to connected systems."
    ),
    "SERIALIZATION": (
        "This code deserializes (unpacks) external data — pickle, YAML, JSON, binary plists. "
        "Deserializing untrusted data from an attacker can execute arbitrary code "
        "or crash the application (Insecure Deserialization)."
    ),
    "NETWORK_SOCKET": (
        "This code opens raw network or Unix domain sockets. "
        "Poorly configured sockets can be hijacked by attackers on the same machine "
        "or network to intercept or inject data."
    ),
    "CLOUD_SERVICE": (
        "This code calls a third-party cloud service (AWS, GCP, Azure, Sentry, etc.). "
        "Misconfigured credentials or permissions can expose all data in those "
        "cloud accounts to an attacker."
    ),
    "AUTH_BOUNDARY": (
        "This code handles authentication or authorization — verifying who a user is "
        "and what they can do. Bugs here let attackers impersonate other users or "
        "access data they shouldn't."
    ),
    "MIDDLEWARE": (
        "This code is an HTTP server, router, or middleware layer — the front door of "
        "the application. Every request passes through here, making it a high-value "
        "target for injection attacks, rate-limit bypass, and privilege escalation."
    ),
    "EVENT_BUS": (
        "This code uses an asynchronous message queue or event bus (Redis, Kafka, Celery). "
        "Attackers who can publish malicious events can trigger unintended behavior "
        "across every service that consumes them."
    ),
    "MCP_TOOL": (
        "This code registers an MCP (Model Context Protocol) tool that AI agents can "
        "call. Each tool is an attack surface: a prompt-injected agent could invoke "
        "any registered tool with attacker-controlled arguments."
    ),
}

# ── Attack vectors per category ───────────────────────────────────────────────

_ATTACK_VECTORS: Dict[str, List[str]] = {
    "SHELL_EXEC":     ["Remote Code Execution (RCE)", "Command Injection", "Privilege Escalation"],
    "EXTERNAL_HTTP":  ["Server-Side Request Forgery (SSRF)", "Data Exfiltration", "Response Injection"],
    "DATABASE":       ["SQL Injection", "Data Breach", "Data Corruption"],
    "FILE_SYSTEM":    ["Path Traversal", "Arbitrary File Write", "Log Injection"],
    "ENV_SECRETS":    ["Credential Theft", "Secret Leakage", "Lateral Movement"],
    "SERIALIZATION":  ["Insecure Deserialization", "Remote Code Execution", "Denial of Service"],
    "NETWORK_SOCKET": ["Man-in-the-Middle", "Socket Hijacking", "Data Interception"],
    "CLOUD_SERVICE":  ["Credential Abuse", "Cloud Account Takeover", "Data Exfiltration"],
    "AUTH_BOUNDARY":  ["Authentication Bypass", "Privilege Escalation", "Session Hijacking"],
    "MIDDLEWARE":     ["Injection Attacks", "Bypass Rate Limiting", "Privilege Escalation"],
    "EVENT_BUS":      ["Event Poisoning", "Denial of Service", "Cross-Service Attack"],
    "MCP_TOOL":       ["Prompt Injection via Tool", "Indirect Tool Abuse", "Data Exfiltration"],
}

# ── CWE per category ──────────────────────────────────────────────────────────

_CWE: Dict[str, str] = {
    "SHELL_EXEC":     "CWE-78",
    "EXTERNAL_HTTP":  "CWE-918",
    "DATABASE":       "CWE-89",
    "FILE_SYSTEM":    "CWE-73",
    "ENV_SECRETS":    "CWE-798",
    "SERIALIZATION":  "CWE-502",
    "NETWORK_SOCKET": "CWE-601",
    "CLOUD_SERVICE":  "CWE-306",
    "AUTH_BOUNDARY":  "CWE-306",
    "MIDDLEWARE":     "CWE-284",
    "EVENT_BUS":      "CWE-400",
    "MCP_TOOL":       "CWE-284",
}

# ── Pattern definitions ────────────────────────────────────────────────────────
# Each entry: (compiled_regex, category, severity)
# Ordered from most-to-least critical to avoid double-counting priority.

def _p(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


_PYTHON_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
    # SHELL_EXEC — critical
    (_p(r"\bsubprocess\s*\.\s*(run|call|Popen|check_output|check_call|getoutput)"), "SHELL_EXEC", "critical"),
    (_p(r"\bos\s*\.\s*(system|popen|exec[lv]p?e?|execlpe|execvpe)\s*\("), "SHELL_EXEC", "critical"),
    (_p(r"\bshlex\s*\.\s*(split|quote)"), "SHELL_EXEC", "critical"),
    # SERIALIZATION — high (before import socket so pickle wins)
    (_p(r"\bpickle\s*\.\s*(loads?|dumps?|Unpickler)"), "SERIALIZATION", "high"),
    (_p(r"\bimport\s+pickle\b"), "SERIALIZATION", "high"),
    (_p(r"\bimport\s+marshal\b"), "SERIALIZATION", "high"),
    (_p(r"\bimport\s+shelve\b"), "SERIALIZATION", "high"),
    (_p(r"\byaml\s*\.\s*load\s*\("), "SERIALIZATION", "high"),
    (_p(r"\bimport\s+yaml\b"), "SERIALIZATION", "high"),
    # EXTERNAL_HTTP — high
    (_p(r"\brequests\s*\.\s*(get|post|put|delete|patch|head|request)"), "EXTERNAL_HTTP", "high"),
    (_p(r"\bhttpx\s*\."), "EXTERNAL_HTTP", "high"),
    (_p(r"\baiohttp\s*\."), "EXTERNAL_HTTP", "high"),
    (_p(r"\burllib\s*\.\s*request"), "EXTERNAL_HTTP", "high"),
    # DATABASE — high
    (_p(r"\bsqlite3\s*\.\s*connect"), "DATABASE", "high"),
    (_p(r"\bpsycopg2\s*\."), "DATABASE", "high"),
    (_p(r"\bsqlalchemy\s*\."), "DATABASE", "high"),
    (_p(r"\basyncpg\s*\."), "DATABASE", "high"),
    (_p(r"\bmotor\s*\."), "DATABASE", "high"),
    (_p(r"\bpymongo\s*\."), "DATABASE", "high"),
    # ENV_SECRETS — high
    (_p(r"\bos\s*\.\s*environ\s*[\[.]"), "ENV_SECRETS", "high"),
    (_p(r"\bos\s*\.\s*getenv\s*\("), "ENV_SECRETS", "high"),
    (_p(r"\bdotenv\s*\.\s*(load_dotenv|dotenv_values)"), "ENV_SECRETS", "high"),
    # NETWORK_SOCKET — high
    (_p(r"\bimport\s+socket\b"), "NETWORK_SOCKET", "high"),
    (_p(r"\bsocket\s*\.\s*(socket|create_connection|create_server)\s*\("), "NETWORK_SOCKET", "high"),
    # FILE_SYSTEM — medium
    (_p(r"\bopen\s*\([^)]*[\"'][wa][b]?[\"']"), "FILE_SYSTEM", "medium"),
    (_p(r"\bPath\s*\([^)]*\)\s*\.\s*write_(text|bytes)\s*\("), "FILE_SYSTEM", "medium"),
    # CLOUD_SERVICE — medium
    (_p(r"\bboto3\s*\."), "CLOUD_SERVICE", "medium"),
    (_p(r"\bbotocore\s*\."), "CLOUD_SERVICE", "medium"),
    (_p(r"\bgoogle\s*\.\s*cloud\s*\."), "CLOUD_SERVICE", "medium"),
    (_p(r"\bazure\s*\."), "CLOUD_SERVICE", "medium"),
    (_p(r"\bsentry_sdk\s*\."), "CLOUD_SERVICE", "medium"),
    # AUTH_BOUNDARY — medium
    (_p(r"\bjwt\s*\.\s*(encode|decode|verify)"), "AUTH_BOUNDARY", "medium"),
    (_p(r"\bbcrypt\s*\."), "AUTH_BOUNDARY", "medium"),
    (_p(r"@(login_required|requires_auth|permission_required)"), "AUTH_BOUNDARY", "medium"),
    (_p(r"\bverify_token\s*\("), "AUTH_BOUNDARY", "medium"),
    # MIDDLEWARE — medium
    (_p(r"@app\s*\.\s*(route|get|post|put|delete|patch)\s*\("), "MIDDLEWARE", "medium"),
    (_p(r"\bFastAPI\s*\("), "MIDDLEWARE", "medium"),
    (_p(r"\bapp\s*\.\s*add_middleware\s*\("), "MIDDLEWARE", "medium"),
    (_p(r"\bFlask\s*\("), "MIDDLEWARE", "medium"),
    # MCP_TOOL — medium
    (_p(r"@mcp\s*\.\s*tool"), "MCP_TOOL", "medium"),
    (_p(r"\bmcp\s*\.\s*tool\s*\("), "MCP_TOOL", "medium"),
    # EVENT_BUS — low
    (_p(r"\bcelery\s*\."), "EVENT_BUS", "low"),
    (_p(r"\bredis\s*\.\s*(Redis|StrictRedis|from_url)"), "EVENT_BUS", "low"),
    (_p(r"\bpika\s*\."), "EVENT_BUS", "low"),
    (_p(r"\bkafka\s*\."), "EVENT_BUS", "low"),
]

_TS_JS_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
    # SHELL_EXEC — critical
    (_p(r"\bchild_process\b"), "SHELL_EXEC", "critical"),
    (_p(r"\bexecSync\s*\("), "SHELL_EXEC", "critical"),
    (_p(r"\bspawnSync?\s*\("), "SHELL_EXEC", "critical"),
    (_p(r"\bexecFileSync?\s*\("), "SHELL_EXEC", "critical"),
    (_p(r"\b(xcodebuild|xcrun|simctl|xcode-select|lldb)\b"), "SHELL_EXEC", "critical"),
    # SERIALIZATION — high
    (_p(r"\bJSON\s*\.\s*parse\s*\("), "SERIALIZATION", "high"),
    (_p(r"\byaml\s*\.\s*(load|parse)\s*\("), "SERIALIZATION", "high"),
    (_p(r"\bbplist-parser\b"), "SERIALIZATION", "high"),
    (_p(r"require\s*\(\s*[\"']bplist-parser[\"']\s*\)"), "SERIALIZATION", "high"),
    # EXTERNAL_HTTP — high
    (_p(r"\bfetch\s*\("), "EXTERNAL_HTTP", "high"),
    (_p(r"\baxios\s*\."), "EXTERNAL_HTTP", "high"),
    (_p(r"\bhttps?\s*\.\s*(get|request|post)\s*\("), "EXTERNAL_HTTP", "high"),
    (_p(r"require\s*\(\s*[\"'](node-fetch|got|superagent)[\"']\s*\)"), "EXTERNAL_HTTP", "high"),
    # DATABASE — high
    (_p(r"\b(mysql|mysql2|pg|postgres)\s*\.\s*(query|connect|createPool)"), "DATABASE", "high"),
    (_p(r"\bmongoose\s*\.\s*(connect|model|Schema)"), "DATABASE", "high"),
    (_p(r"\bsequelize\s*\."), "DATABASE", "high"),
    (_p(r"\bprisma\s*\."), "DATABASE", "high"),
    (_p(r"\bknex\s*\("), "DATABASE", "high"),
    # ENV_SECRETS — high
    (_p(r"\bprocess\s*\.\s*env\s*[\[.]"), "ENV_SECRETS", "high"),
    (_p(r"require\s*\(\s*[\"']dotenv[\"']\s*\)"), "ENV_SECRETS", "high"),
    (_p(r"import\s+.*\bconfig\b.*from\s+[\"']dotenv"), "ENV_SECRETS", "high"),
    # NETWORK_SOCKET — high
    (_p(r"\bnet\s*\.\s*(createServer|createConnection|Socket)\s*\("), "NETWORK_SOCKET", "high"),
    (_p(r"\bnew\s+WebSocket\s*\("), "NETWORK_SOCKET", "high"),
    (_p(r"\bunixDomainSocket\b"), "NETWORK_SOCKET", "high"),
    (_p(r"createUnixSocketServer"), "NETWORK_SOCKET", "high"),
    # FILE_SYSTEM — medium
    (_p(r"\bfs\s*\.\s*(writeFile|appendFile|createWriteStream|writeSync)"), "FILE_SYSTEM", "medium"),
    (_p(r"\bfs\s*\.\s*promises\s*\.\s*(writeFile|appendFile)"), "FILE_SYSTEM", "medium"),
    # CLOUD_SERVICE — medium
    (_p(r"@aws-sdk\b"), "CLOUD_SERVICE", "medium"),
    (_p(r"require\s*\(\s*[\"']@sentry"), "CLOUD_SERVICE", "medium"),
    (_p(r"import\s+.*from\s+[\"']@sentry"), "CLOUD_SERVICE", "medium"),
    (_p(r"\bGoogleAuth\s*\("), "CLOUD_SERVICE", "medium"),
    (_p(r"@azure/"), "CLOUD_SERVICE", "medium"),
    # AUTH_BOUNDARY — medium
    (_p(r"\bjwt\s*\.\s*(sign|verify|decode)\s*\("), "AUTH_BOUNDARY", "medium"),
    (_p(r"\bbcrypt\s*\.\s*(hash|compare)"), "AUTH_BOUNDARY", "medium"),
    (_p(r"\bpassport\s*\."), "AUTH_BOUNDARY", "medium"),
    (_p(r"\bz\s*\.\s*(object|string|number|array)\s*\("), "AUTH_BOUNDARY", "medium"),  # zod
    # MIDDLEWARE — medium
    (_p(r"\bapp\s*\.\s*use\s*\("), "MIDDLEWARE", "medium"),
    (_p(r"\brouter\s*\.\s*(get|post|put|delete|use)\s*\("), "MIDDLEWARE", "medium"),
    (_p(r"\bexpress\s*\(\s*\)"), "MIDDLEWARE", "medium"),
    (_p(r"\bfastify\s*\(\s*\)"), "MIDDLEWARE", "medium"),
    (_p(r"\bnew\s+McpServer\s*\("), "MIDDLEWARE", "medium"),
    (_p(r"\bStdioServerTransport\b"), "MIDDLEWARE", "medium"),
    # MCP_TOOL — medium
    (_p(r"\bserver\s*\.\s*tool\s*\("), "MCP_TOOL", "medium"),
    (_p(r"\bcreateTypedTool\s*\("), "MCP_TOOL", "medium"),
    (_p(r"\bserver\s*\.\s*addTool\s*\("), "MCP_TOOL", "medium"),
    (_p(r"\bMcpServer\s*\("), "MCP_TOOL", "medium"),
    # EVENT_BUS — low
    (_p(r"\bchokidar\s*\.\s*watch\s*\("), "EVENT_BUS", "low"),
    (_p(r"\bnew\s+EventEmitter\s*\("), "EVENT_BUS", "low"),
    (_p(r"require\s*\(\s*[\"'](kafkajs|amqplib|bull|bullmq)[\"']\s*\)"), "EVENT_BUS", "low"),
    (_p(r"\bRedis\s*\("), "EVENT_BUS", "low"),
]

_SWIFT_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
    (_p(r"\bURLSession\s*\.\s*(shared|data|download|upload)"), "EXTERNAL_HTTP", "high"),
    (_p(r"\bURLRequest\s*\("), "EXTERNAL_HTTP", "high"),
    (_p(r"\bProcess\s*\(\s*\)"), "SHELL_EXEC", "critical"),
    (_p(r"\bFileManager\s*\.\s*default"), "FILE_SYSTEM", "medium"),
    (_p(r"\.write\s*\(to:"), "FILE_SYSTEM", "medium"),
    (_p(r"\bProcessInfo\s*\.\s*processInfo\s*\.\s*environment"), "ENV_SECRETS", "high"),
    (_p(r"\bGRDB\s*\."), "DATABASE", "high"),
    (_p(r"\bCoreData\b"), "DATABASE", "high"),
    (_p(r"\bPropertyListDecoder\s*\(\s*\)"), "SERIALIZATION", "high"),
    (_p(r"\bJSONDecoder\s*\(\s*\)"), "SERIALIZATION", "high"),
]

_GO_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
    (_p(r"\bexec\s*\.\s*Command\s*\("), "SHELL_EXEC", "critical"),
    (_p(r"\bhttp\s*\.\s*(Get|Post|NewRequest)"), "EXTERNAL_HTTP", "high"),
    (_p(r"\bsql\s*\.\s*Open\s*\("), "DATABASE", "high"),
    (_p(r"\bos\s*\.\s*(Getenv|LookupEnv)\s*\("), "ENV_SECRETS", "high"),
    (_p(r"\bnet\s*\.\s*(Listen|Dial)\s*\("), "NETWORK_SOCKET", "high"),
    (_p(r"\bjson\s*\.\s*Unmarshal\s*\("), "SERIALIZATION", "high"),
    (_p(r"\bgob\s*\.\s*NewDecoder"), "SERIALIZATION", "high"),
    (_p(r"\bos\s*\.\s*(Create|OpenFile)\s*\("), "FILE_SYSTEM", "medium"),
]

_YAML_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
    (_p(r"\$\{\s*\w*(SECRET|KEY|TOKEN|PASSWORD|PASS|PWD)\w*\s*\}"), "ENV_SECRETS", "high"),
    (_p(r"\$\(\s*\w+\s*\)"), "SHELL_EXEC", "critical"),  # $(command) in YAML
    (_p(r"curl\s+https?://"), "EXTERNAL_HTTP", "high"),
    (_p(r"wget\s+https?://"), "EXTERNAL_HTTP", "high"),
    (_p(r"mysql\s+-u"), "DATABASE", "high"),
    (_p(r"redis-cli"), "EVENT_BUS", "low"),
]

_JAVA_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
    (_p(r"\bRuntime\s*\.\s*getRuntime\s*\(\s*\)\s*\.\s*exec"), "SHELL_EXEC", "critical"),
    (_p(r"\bProcessBuilder\s*\("), "SHELL_EXEC", "critical"),
    (_p(r"\bnew\s+URL\s*\("), "EXTERNAL_HTTP", "high"),
    (_p(r"\bDriverManager\s*\.\s*getConnection"), "DATABASE", "high"),
    (_p(r"\bObjectInputStream\s*\("), "SERIALIZATION", "high"),
    (_p(r"\bSystem\s*\.\s*getenv\s*\("), "ENV_SECRETS", "high"),
    (_p(r"\bnew\s+ServerSocket\s*\("), "NETWORK_SOCKET", "high"),
    (_p(r"\bFileWriter\s*\("), "FILE_SYSTEM", "medium"),
]

# Map extension → patterns list
_LANG_PATTERNS: Dict[str, List[Tuple[re.Pattern, str, str]]] = {
    ".py":   _PYTHON_PATTERNS,
    ".ts":   _TS_JS_PATTERNS,
    ".tsx":  _TS_JS_PATTERNS,
    ".js":   _TS_JS_PATTERNS,
    ".jsx":  _TS_JS_PATTERNS,
    ".mjs":  _TS_JS_PATTERNS,
    ".cjs":  _TS_JS_PATTERNS,
    ".swift": _SWIFT_PATTERNS,
    ".go":   _GO_PATTERNS,
    ".java": _JAVA_PATTERNS,
    ".kt":   _JAVA_PATTERNS,
    ".yaml": _YAML_PATTERNS,
    ".yml":  _YAML_PATTERNS,
}

# ── Dataclasses ───────────────────────────────────────────────────────────────


@dataclass
class IntegrationArea:
    """A single detected integration point in the codebase."""

    category: str           # e.g. SHELL_EXEC
    source_file: str        # relative path from repo root
    line_number: int
    evidence: str           # matched code snippet (≤120 chars)
    severity: str           # critical | high | medium | low
    plain_english: str      # one-sentence non-technical explanation
    attack_vectors: List[str] = field(default_factory=list)
    test_files: List[str] = field(default_factory=list)   # matched test files
    cwe: str = ""

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "source_file": self.source_file,
            "line_number": self.line_number,
            "evidence": self.evidence,
            "severity": self.severity,
            "plain_english": self.plain_english,
            "attack_vectors": self.attack_vectors,
            "test_files": self.test_files,
            "cwe": self.cwe,
        }


@dataclass
class ArchitectureScanResult:
    """Full architecture scan result for a repository."""

    repo_path: str
    integration_areas: List[IntegrationArea]
    attack_surface_score: float      # 0–100
    test_coverage_confidence: float  # 0–100
    files_scanned: int
    scan_error: Optional[str] = None

    # ── Convenience properties ────────────────────────────────────────────────

    @property
    def critical_areas(self) -> List[IntegrationArea]:
        return [a for a in self.integration_areas if a.severity == "critical"]

    @property
    def untested_areas(self) -> List[IntegrationArea]:
        return [a for a in self.integration_areas if not a.test_files]

    def by_category(self) -> Dict[str, List[IntegrationArea]]:
        out: Dict[str, List[IntegrationArea]] = {}
        for area in self.integration_areas:
            out.setdefault(area.category, []).append(area)
        return out

    # ── Human-readable report ─────────────────────────────────────────────────

    def plain_english_report(self) -> str:
        cats = self.by_category()
        lines = [
            f"Architecture Scan — {self.repo_path}",
            f"{'=' * 60}",
            f"Files scanned:             {self.files_scanned}",
            f"Integration areas found:   {len(self.integration_areas)}",
            f"Attack surface score:      {self.attack_surface_score:.0f}/100",
            f"Test coverage confidence:  {self.test_coverage_confidence:.0f}%",
            f"Untested integration areas:{len(self.untested_areas)}",
            "",
            "INTEGRATION AREAS BY CATEGORY",
            "-" * 60,
        ]
        for cat, areas in sorted(cats.items(), key=lambda x: -len(x[1])):
            sev = areas[0].severity.upper()
            lines.append(f"  [{sev:8s}] {cat} — {len(areas)} location(s)")
            lines.append(f"             {areas[0].plain_english}")
            lines.append(f"             Attack vectors: {', '.join(areas[0].attack_vectors[:3])}")
            for a in areas[:3]:
                tested = " [TESTED]" if a.test_files else " [NO TESTS]"
                lines.append(f"             • {a.source_file}:{a.line_number}{tested}")
            if len(areas) > 3:
                lines.append(f"             … and {len(areas) - 3} more")
            lines.append("")
        if self.untested_areas:
            lines.append("UNTESTED HIGH-RISK AREAS (priority for new tests)")
            lines.append("-" * 60)
            for a in self.untested_areas:
                if a.severity in ("critical", "high"):
                    lines.append(f"  [{a.severity.upper():8s}] {a.source_file}:{a.line_number} — {a.category}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "repo_path": self.repo_path,
            "files_scanned": self.files_scanned,
            "attack_surface_score": self.attack_surface_score,
            "test_coverage_confidence": self.test_coverage_confidence,
            "total_integration_areas": len(self.integration_areas),
            "untested_count": len(self.untested_areas),
            "critical_count": len(self.critical_areas),
            "categories": {k: len(v) for k, v in self.by_category().items()},
            "integration_areas": [a.to_dict() for a in self.integration_areas],
            "scan_error": self.scan_error,
        }


# ── Scanner ───────────────────────────────────────────────────────────────────


class ArchitectureScanner:
    """
    Multi-language integration point mapper.

    Walks a repository, applies language-appropriate regex patterns,
    cross-references with test files, and returns an ArchitectureScanResult.
    """

    def scan(self, repo_path: str = ".") -> ArchitectureScanResult:
        """Scan an entire repository. Returns ArchitectureScanResult."""
        root = Path(repo_path).resolve()
        try:
            source_files = self._find_source_files(root)
            test_files = self._find_test_files(root)
            all_areas: List[IntegrationArea] = []

            for f in source_files:
                areas = self._scan_file(f, root)
                for area in areas:
                    area.test_files = self._match_test_files(area.source_file, test_files, root)
                all_areas.extend(areas)

            # Deduplicate: same (category, file, line)
            seen: set = set()
            deduped: List[IntegrationArea] = []
            for a in all_areas:
                key = (a.category, a.source_file, a.line_number)
                if key not in seen:
                    seen.add(key)
                    deduped.append(a)

            surface, coverage = self._compute_scores(deduped)
            return ArchitectureScanResult(
                repo_path=str(root),
                integration_areas=deduped,
                attack_surface_score=surface,
                test_coverage_confidence=coverage,
                files_scanned=len(source_files),
            )
        except Exception as exc:
            return ArchitectureScanResult(
                repo_path=str(root),
                integration_areas=[],
                attack_surface_score=0.0,
                test_coverage_confidence=0.0,
                files_scanned=0,
                scan_error=str(exc),
            )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _find_source_files(self, root: Path) -> List[Path]:
        files: List[Path] = []
        for f in root.rglob("*"):
            if not f.is_file():
                continue
            if any(part in _SKIP_DIRS for part in f.parts):
                continue
            if f.suffix.lower() in _SOURCE_EXTENSIONS:
                files.append(f)
        return files

    def _find_test_files(self, root: Path) -> List[Path]:
        test_files: List[Path] = []
        for f in root.rglob("*"):
            if not f.is_file():
                continue
            if any(part in _SKIP_DIRS for part in f.parts):
                continue
            name = f.name.lower()
            # Matches: test_foo.py, foo_test.ts, foo.spec.ts, foo.test.js, tests/foo.py
            if (
                name.startswith("test_")
                or name.endswith("_test.py")
                or ".test." in name
                or ".spec." in name
                or "test" in [p.lower() for p in f.parts[:-1]]
                or "__tests__" in [p for p in f.parts]
            ):
                test_files.append(f)
        return test_files

    def _scan_file(self, path: Path, root: Path) -> List[IntegrationArea]:
        ext = path.suffix.lower()
        patterns = _LANG_PATTERNS.get(ext)
        if not patterns:
            return []
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []

        rel = str(path.relative_to(root)).replace("\\", "/")
        areas: List[IntegrationArea] = []
        seen_per_file: set = set()

        for lineno, line in enumerate(source.splitlines(), start=1):
            for pattern, category, severity in patterns:
                m = pattern.search(line)
                if not m:
                    continue
                key = (category, lineno)
                if key in seen_per_file:
                    continue
                seen_per_file.add(key)
                evidence = line.strip()[:120]
                areas.append(IntegrationArea(
                    category=category,
                    source_file=rel,
                    line_number=lineno,
                    evidence=evidence,
                    severity=severity,
                    plain_english=_PLAIN_ENGLISH.get(category, ""),
                    attack_vectors=list(_ATTACK_VECTORS.get(category, [])),
                    cwe=_CWE.get(category, ""),
                ))

        return areas

    def _match_test_files(self, source_file: str, test_files: List[Path], root: Path) -> List[str]:
        """Return relative paths of test files likely covering source_file."""
        # Strip directory and extension from source file to get base stem
        stem = Path(source_file).stem.lower()
        # Remove common prefixes/suffixes that aren't part of the module name
        for prefix in ("src_", "lib_", "utils_"):
            if stem.startswith(prefix):
                stem = stem[len(prefix):]

        matched: List[str] = []
        for tf in test_files:
            tf_name = tf.stem.lower()
            # Match if source stem appears in test filename or vice versa
            if stem in tf_name or tf_name.replace("test_", "").replace("_test", "") in stem:
                matched.append(str(tf.relative_to(root)).replace("\\", "/"))
        return matched

    @staticmethod
    def _compute_scores(areas: List[IntegrationArea]) -> Tuple[float, float]:
        if not areas:
            return 0.0, 100.0
        raw_score = sum(_SEVERITY_WEIGHTS.get(a.severity, 0) for a in areas)
        attack_surface = min(float(raw_score), 100.0)
        tested = sum(1 for a in areas if a.test_files)
        coverage = round(tested / len(areas) * 100, 1)
        return round(attack_surface, 1), coverage
