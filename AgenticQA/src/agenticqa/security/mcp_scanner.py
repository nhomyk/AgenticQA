"""
MCPSecurityScanner — detects security vulnerabilities in MCP server
definitions and implementations.

Attack vectors covered (OWASP LLM + CWE references):
  TOOL_POISONING          — LLM manipulation via tool descriptions (OWASP LLM01, CWE-94)
  EXFILTRATION_PATTERN    — data exfiltration instructions in descriptions (CWE-201)
  PROMPT_INJECTION_VECTOR — injection via tool results into LLM context (CWE-94)
  AMBIENT_AUTHORITY       — excessive OS/filesystem access in handlers (CWE-272)
  UNRESTRICTED_FILE_ACCESS— file tools with no path constraints (CWE-22)
  SSRF_RISK               — user-controlled URLs in network calls (CWE-918)
  COMMAND_INJECTION       — shell execution with user-controlled params (CWE-78)
  MISSING_AUTH            — unauthenticated server transports (CWE-306)
  UNCONSTRAINED_SCOPE     — tool parameters with no input validation (CWE-20)
  CROSS_ORIGIN_ESCALATION — tools bridging trust boundaries (CWE-284)
  SHADOW_TOOL             — duplicate tool names across servers (OWASP LLM01)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

ATTACK_CWE: Dict[str, str] = {
    "TOOL_POISONING":           "CWE-94",
    "EXFILTRATION_PATTERN":     "CWE-201",
    "PROMPT_INJECTION_VECTOR":  "CWE-94",
    "AMBIENT_AUTHORITY":        "CWE-272",
    "UNRESTRICTED_FILE_ACCESS": "CWE-22",
    "SSRF_RISK":                "CWE-918",
    "COMMAND_INJECTION":        "CWE-78",
    "MISSING_AUTH":             "CWE-306",
    "UNCONSTRAINED_SCOPE":      "CWE-20",
    "CROSS_ORIGIN_ESCALATION":  "CWE-284",
    "SHADOW_TOOL":              "CWE-290",
}

SEVERITY_CVSS: Dict[str, float] = {
    "critical": 9.3, "high": 7.5, "medium": 5.5, "low": 2.5,
}

SEVERITY_WEIGHTS: Dict[str, float] = {
    "critical": 0.30, "high": 0.15, "medium": 0.08, "low": 0.03,
}

# Tool descriptions — LLM manipulation and exfiltration patterns
_DESCRIPTION_PATTERNS: List[Tuple[str, str, str]] = [
    # (regex, attack_type, severity)

    # --- Tool Poisoning: instruction override ---
    (r"(?i)(ignore|disregard|forget|override|bypass|discard)\s+"
     r"(previous|prior|above|all|any|system)\s+"
     r"(instructions?|prompts?|context|rules?|constraints?|guidelines?)",
     "TOOL_POISONING", "critical"),

    (r"(?i)do\s+not\s+(tell|inform|mention|disclose|reveal|show)\s+(the\s+)?(user|human|operator)",
     "TOOL_POISONING", "critical"),

    (r"(?i)(secretly|silently|covertly|without\s+(?:telling|informing|notifying|disclosing))\s+\S+",
     "TOOL_POISONING", "critical"),

    (r"(?i)your\s+(new|true|actual|real|primary|updated)\s+"
     r"(purpose|goal|objective|task|role|directive|mission|function)\s+is",
     "TOOL_POISONING", "critical"),

    (r"(?i)act\s+as\s+(if|though|like)\s+you\s+(are|were|have\s+been|can\b)",
     "TOOL_POISONING", "high"),

    (r"(?i)you\s+(are|must|should|will|shall)\s+(now|always|never|also|henceforth)\b",
     "TOOL_POISONING", "high"),

    (r"(?i)(note|important|attention|warning|reminder|caution)\s*:\s*"
     r"(always|never|must|should|do\s+not|make\s+sure|ensure)",
     "TOOL_POISONING", "medium"),

    # --- Exfiltration: sending data to external endpoints ---
    (r"(?i)(always|also|additionally|before\s+returning|after\s+(calling|executing|responding))\s+"
     r"(include|append|send|attach|forward|transmit|add)\s+\S+",
     "EXFILTRATION_PATTERN", "critical"),

    (r"(?i)(send|transmit|forward|post|exfiltrate|upload|leak)\s+"
     r"(all|every|the|any)\s+"
     r"(data|info(?:rmation)?|content|results?|credentials?|tokens?|keys?|secrets?|passwords?)",
     "EXFILTRATION_PATTERN", "critical"),

    (r"(?i)(send|post|forward|transmit|report)\s+\S+\s+to\s+"
     r"https?://(?!localhost\b|127\.0\.0\.1\b|0\.0\.0\.0\b)[a-zA-Z0-9]",
     "EXFILTRATION_PATTERN", "critical"),

    (r"(?i)include\s+(your|the|all|any)\s+"
     r"(api[_\s]?key|secret|password|token|credential|auth|bearer)",
     "EXFILTRATION_PATTERN", "critical"),

    # --- Exfiltration: external URLs in descriptions ---
    (r"https?://(?!localhost\b|127\.0\.0\.1\b|0\.0\.0\.0\b)[a-zA-Z0-9][a-zA-Z0-9.-]{3,}/\S*",
     "EXFILTRATION_ENDPOINT", "high"),

    # --- Prompt injection via HTML / newline ---
    (r"(?i)<\s*(script|iframe|img\s+src|svg|object|embed|link\s+href|form\s+action)[^>]{0,200}>",
     "PROMPT_INJECTION_VECTOR", "critical"),

    (r"\\n\s*(?:ignore|override|system|admin|jailbreak|you\s+are|act\s+as|forget|disregard)",
     "PROMPT_INJECTION_VECTOR", "high"),

    # --- Cross-origin escalation ---
    (r"(?i)(access|read|write|modify|delete)\s+(files?|data|resources?)\s+"
     r"(outside|beyond|across)\s+(the|its|their|your)\s+"
     r"(sandbox|container|directory|scope|boundary|workspace)",
     "CROSS_ORIGIN_ESCALATION", "high"),
]

# Tool handler code — dangerous implementation patterns
_CODE_PATTERNS: List[Tuple[str, str, str]] = [
    # --- Command injection ---
    (r"subprocess\.(run|call|Popen|check_output|check_call|communicate)\s*\([^)]{0,200}shell\s*=\s*True",
     "COMMAND_INJECTION", "critical"),
    (r"\bos\.system\s*\(", "COMMAND_INJECTION", "critical"),
    (r"\bos\.popen\s*\(", "COMMAND_INJECTION", "critical"),
    (r"\beval\s*\(", "COMMAND_INJECTION", "critical"),
    (r"\bexec\s*\(", "COMMAND_INJECTION", "high"),
    (r"__import__\s*\(", "COMMAND_INJECTION", "high"),
    (r"\bpickle\.loads?\s*\(", "COMMAND_INJECTION", "critical"),
    (r"\byaml\.load\s*\([^,)]+\)", "COMMAND_INJECTION", "high"),  # no Loader=

    # --- SSRF ---
    (r"\brequests\.(get|post|put|patch|delete|head|request)\s*\(\s*\w+",
     "SSRF_RISK", "high"),
    (r"\burllib\.request\.urlopen\s*\(", "SSRF_RISK", "high"),
    (r"\bhttpx\.(get|post|put|patch|delete|request)\s*\(\s*\w+", "SSRF_RISK", "high"),
    (r"\baiohttp\.(ClientSession|request)\b", "SSRF_RISK", "medium"),
    # JS/TS
    (r"\bfetch\s*\(\s*\w+", "SSRF_RISK", "high"),
    (r"\baxios\.(get|post|put|patch|delete)\s*\(\s*\w+", "SSRF_RISK", "high"),
    (r"\bhttp\.request\s*\(\s*\w+", "SSRF_RISK", "medium"),

    # --- Ambient authority / destructive filesystem ---
    (r"\bshutil\.(rmtree|move|copy2?|copytree)\s*\(", "AMBIENT_AUTHORITY", "high"),
    (r"\bos\.(remove|unlink|rmdir|makedirs|mkdir|chmod|chown|rename)\s*\(",
     "AMBIENT_AUTHORITY", "high"),
    (r"\bos\.walk\s*\(\s*['\"][/~]", "UNRESTRICTED_FILE_ACCESS", "medium"),
    (r"\bglob\.glob\s*\(\s*['\"](?:[/~*]|\.\./)", "UNRESTRICTED_FILE_ACCESS", "medium"),
    (r"\bopen\s*\(\s*(?:['\"][/~]|os\.path\.(?:join|expanduser|abspath)\b)",
     "UNRESTRICTED_FILE_ACCESS", "medium"),
    (r"\bpathlib\.Path\s*\(\s*['\"][/~]", "UNRESTRICTED_FILE_ACCESS", "medium"),
    # JS/TS
    (r"\bfs\.(readFile|writeFile|unlink|rmdir|rm|mkdir|readdir)\b",
     "AMBIENT_AUTHORITY", "medium"),
    (r"\brequire\s*\(\s*['\"]child_process['\"]", "COMMAND_INJECTION", "high"),
    (r"\bspawnSync?\s*\(|execSync?\s*\(", "COMMAND_INJECTION", "high"),
]

# Config file — transport / auth patterns
_CONFIG_PATTERNS: List[Tuple[str, str, str]] = [
    (r"['\"]?host['\"]?\s*[=:]\s*['\"]0\.0\.0\.0['\"]",
     "MISSING_AUTH", "high"),
    (r"(?i)['\"]?auth(?:entication|_required|_enabled)?['\"]?\s*[=:]\s*"
     r"(?:false|False|null|None|0\b|\"false\")",
     "MISSING_AUTH", "critical"),
    (r"(?i)['\"]?require_?auth['\"]?\s*[=:]\s*(?:false|False|null|None)",
     "MISSING_AUTH", "critical"),
    (r"(?i)['\"]?(?:api_?key|secret|token)['\"]?\s*[=:]\s*['\"](?:|none|null|false)['\"]",
     "MISSING_AUTH", "high"),
    (r"(?i)--no-?auth|--disable-?auth|--anonymous",
     "MISSING_AUTH", "critical"),
    (r"(?i)AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED['\"]?\s*[=:]\s*['\"]?true",
     "MISSING_AUTH", "high"),
]

# Parameter names that warrant validation checks
_HIGH_RISK_PARAM_NAMES = frozenset({
    "url", "uri", "endpoint", "host", "command", "cmd", "shell",
    "path", "file", "filename", "dir", "directory", "query", "sql",
    "script", "code", "expr", "expression", "template", "source",
})

# Files / dirs to skip
_SKIP_DIRS = frozenset({
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", "tests", ".mypy_cache", "site-packages",
})

# MCP config filename patterns
_MCP_CONFIG_NAMES = frozenset({
    "mcp.json", "mcp-config.json", "mcp_config.json",
    "claude_desktop_config.json", "mcp_settings.json",
    "mcp.yaml", "mcp-config.yaml", ".mcp.json",
})

# Python MCP implementation markers
_PY_MCP_MARKERS = [
    r"from\s+mcp\s+import", r"import\s+mcp\b",
    r"\bFastMCP\b", r"@mcp\.tool", r"@server\.tool",
    r"mcp\.types\.Tool", r"server\.add_tool",
    r"from\s+fastmcp\s+import",
]

# TypeScript/JS MCP markers
_TS_MCP_MARKERS = [
    r"from\s+['\"]@modelcontextprotocol",
    r"require\s*\(\s*['\"]@modelcontextprotocol",
    r"\bListToolsRequestSchema\b", r"\bCallToolRequestSchema\b",
    r"new\s+Server\s*\(", r"server\.setRequestHandler",
]

# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MCPToolFinding:
    tool_name: str
    attack_type: str
    severity: str
    description: str
    evidence: str
    source_file: str
    line_number: int = 0
    cwe: str = ""
    cvss_score: float = 0.0

    def __post_init__(self) -> None:
        if not self.cwe:
            self.cwe = ATTACK_CWE.get(self.attack_type, "CWE-0")
        if not self.cvss_score:
            self.cvss_score = SEVERITY_CVSS.get(self.severity, 5.0)


@dataclass
class MCPScanResult:
    findings: List[MCPToolFinding] = field(default_factory=list)
    tools_scanned: int = 0
    servers_scanned: int = 0
    files_scanned: int = 0
    risk_score: float = 0.0
    scan_error: Optional[str] = None

    @property
    def critical_findings(self) -> List[MCPToolFinding]:
        return [f for f in self.findings if f.severity == "critical"]

    @property
    def high_findings(self) -> List[MCPToolFinding]:
        return [f for f in self.findings if f.severity == "high"]

    @property
    def attack_types_detected(self) -> List[str]:
        return sorted({f.attack_type for f in self.findings})


# ─────────────────────────────────────────────────────────────────────────────
# Scanner
# ─────────────────────────────────────────────────────────────────────────────

class MCPSecurityScanner:
    """
    Scans MCP server definitions and implementations for security vulnerabilities.

    Analyzes:
      1. Tool descriptions — LLM manipulation and exfiltration instructions
      2. Tool handler code — command injection, SSRF, ambient authority
      3. Input schemas — unconstrained sensitive parameters
      4. Transport config — missing authentication
      5. Multi-server configs — shadow tool detection
    """

    _CUSTOM_PATTERNS_PATH = Path(".agenticqa") / "mcp_patterns.json"

    def __init__(self) -> None:
        self._desc_compiled = [
            (re.compile(p), at, sev) for p, at, sev in _DESCRIPTION_PATTERNS
        ]
        self._code_compiled = [
            (re.compile(p), at, sev) for p, at, sev in _CODE_PATTERNS
        ]
        self._cfg_compiled = [
            (re.compile(p), at, sev) for p, at, sev in _CONFIG_PATTERNS
        ]
        self._load_custom_patterns()

    def _load_custom_patterns(self) -> None:
        """Append patterns learned from past scans (.agenticqa/mcp_patterns.json)."""
        try:
            if not self._CUSTOM_PATTERNS_PATH.exists():
                return
            data = json.loads(self._CUSTOM_PATTERNS_PATH.read_text())
            for entry in data.get("description_patterns", []):
                self._desc_compiled.append((
                    re.compile(entry["pattern"]),
                    entry.get("attack_type", "CUSTOM"),
                    entry.get("severity", "medium"),
                ))
            for entry in data.get("code_patterns", []):
                self._code_compiled.append((
                    re.compile(entry["pattern"]),
                    entry.get("attack_type", "CUSTOM"),
                    entry.get("severity", "medium"),
                ))
        except Exception:
            pass  # non-blocking — never crash a scan over pattern load

    # ── Public API ──────────────────────────────────────────────────────────

    def scan(self, path: str) -> MCPScanResult:
        """Scan a directory or single file for MCP security vulnerabilities."""
        result = MCPScanResult()
        try:
            p = Path(path)
            if not p.exists():
                result.scan_error = f"Path not found: {path}"
                return result
            files = self._find_mcp_files(p)
            result.files_scanned = len(files)
            all_tool_names: List[str] = []

            for f in files:
                ext = f.suffix.lower()
                if ext == ".json":
                    findings, tools, servers, names = self._scan_json(f)
                elif ext in {".yaml", ".yml"}:
                    findings, tools, servers, names = self._scan_yaml(f)
                elif ext == ".py":
                    findings, tools, servers, names = self._scan_python(f)
                elif ext in {".ts", ".js", ".mjs"}:
                    findings, tools, servers, names = self._scan_typescript(f)
                else:
                    continue
                result.findings.extend(findings)
                result.tools_scanned += tools
                result.servers_scanned += servers
                all_tool_names.extend(names)

            # Shadow tool detection across files
            shadow = self._detect_shadow_tools(all_tool_names)
            result.findings.extend(shadow)
            result.risk_score = self._compute_risk_score(result.findings)

        except Exception as exc:
            result.scan_error = str(exc)
        return result

    # ── File discovery ───────────────────────────────────────────────────────

    def _find_mcp_files(self, root: Path) -> List[Path]:
        if root.is_file():
            return [root]
        found: List[Path] = []
        for p in root.rglob("*"):
            if any(part in _SKIP_DIRS for part in p.parts):
                continue
            if not p.is_file():
                continue
            if p.name.lower() in _MCP_CONFIG_NAMES:
                found.append(p)
                continue
            ext = p.suffix.lower()
            if ext in {".py", ".ts", ".js", ".mjs"}:
                try:
                    src = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                markers = _PY_MCP_MARKERS if ext == ".py" else _TS_MCP_MARKERS
                if any(re.search(m, src) for m in markers):
                    found.append(p)
        return found

    # ── JSON config scanning ─────────────────────────────────────────────────

    def _scan_json(self, path: Path) -> Tuple[List[MCPToolFinding], int, int, List[str]]:
        findings: List[MCPToolFinding] = []
        tools_count = 0
        servers_count = 0
        discovered_names: List[str] = []
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return findings, tools_count, servers_count, discovered_names

        src = str(path)

        # claude_desktop_config.json / mcp.json style: {"mcpServers": {...}}
        if "mcpServers" in data:
            servers = data["mcpServers"]
            servers_count = len(servers)
            for srv_name, srv_cfg in (servers.items() if isinstance(servers, dict) else []):
                findings.extend(self._check_server_config(srv_name, srv_cfg, src))

        # Tool-list style: {"tools": [...]}
        if "tools" in data and isinstance(data["tools"], list):
            for tool in data["tools"]:
                tools_count += 1
                name = tool.get("name", "unknown")
                discovered_names.append(name)
                desc = tool.get("description", "")
                schema = tool.get("inputSchema", {})
                findings.extend(self._check_description(name, desc, src, 0))
                findings.extend(self._check_schema(name, schema, src, 0))

        # Config-level patterns on the raw text
        raw = path.read_text(encoding="utf-8", errors="replace")
        findings.extend(self._check_config_text("<config>", raw, src))

        return findings, tools_count, servers_count, discovered_names

    def _scan_yaml(self, path: Path) -> Tuple[List[MCPToolFinding], int, int, List[str]]:
        """Scan YAML configs using regex (no yaml dep required)."""
        findings: List[MCPToolFinding] = []
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return findings, 0, 0, []
        src = str(path)
        findings.extend(self._check_config_text("<yaml-config>", raw, src))
        for m in re.finditer(r"description:\s*['\"]?(.+)['\"]?", raw):
            desc = m.group(1).strip()
            findings.extend(self._check_description("yaml_tool", desc, src, 0))
        return findings, 0, 1, []

    # ── Python source scanning ───────────────────────────────────────────────

    def _scan_python(self, path: Path) -> Tuple[List[MCPToolFinding], int, int, List[str]]:
        findings: List[MCPToolFinding] = []
        try:
            src_text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return findings, 0, 0, []
        src = str(path)
        tools = self._extract_py_tools(src_text)
        discovered_names = [t[0] for t in tools]
        for tool_name, desc, body, start_line in tools:
            findings.extend(self._check_description(tool_name, desc, src, start_line))
            findings.extend(self._check_code(tool_name, body, src, start_line))
            findings.extend(self._check_schema_from_annotations(tool_name, body, src, start_line))
        servers = 1 if re.search(r"\bFastMCP\b|\bServer\s*\(", src_text) else 0
        return findings, len(tools), servers, discovered_names

    def _extract_py_tools(self, source: str) -> List[Tuple[str, str, str, int]]:
        """Extract (name, docstring, body, start_line) for each MCP tool."""
        results = []
        lines = source.splitlines()
        i = 0
        tool_decorator_re = re.compile(r"@(?:mcp\.|server\.|fastmcp\.|)tool\b")
        def_re = re.compile(r"(?:async\s+)?def\s+(\w+)")

        while i < len(lines):
            if tool_decorator_re.match(lines[i].strip()):
                start = i
                # find def
                j = i + 1
                while j < len(lines) and not def_re.match(lines[j].strip()):
                    j += 1
                if j >= len(lines):
                    i += 1
                    continue
                name_m = def_re.search(lines[j])
                tool_name = name_m.group(1) if name_m else f"tool_line_{j}"
                # find docstring
                k = j + 1
                desc = ""
                if k < len(lines):
                    stripped = lines[k].strip()
                    for q in ('"""', "'''"):
                        if stripped.startswith(q):
                            inner = stripped[len(q):]
                            if inner.endswith(q) and len(inner) >= len(q):
                                desc = inner[:-len(q)].strip()
                                k += 1
                            else:
                                buf = [inner]
                                k += 1
                                while k < len(lines) and q not in lines[k]:
                                    buf.append(lines[k].strip())
                                    k += 1
                                if k < len(lines):
                                    buf.append(lines[k].strip().replace(q, ""))
                                    k += 1
                                desc = " ".join(buf).strip()
                            break
                # extract body (up to 40 lines)
                body_end = min(k + 40, len(lines))
                body = "\n".join(lines[k:body_end])
                results.append((tool_name, desc, body, start + 1))
                i = body_end
            else:
                i += 1
        return results

    # ── TypeScript/JS source scanning ────────────────────────────────────────

    def _scan_typescript(self, path: Path) -> Tuple[List[MCPToolFinding], int, int, List[str]]:
        findings: List[MCPToolFinding] = []
        try:
            src_text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return findings, 0, 0, []
        src = str(path)

        tools: List[Tuple[str, str]] = []
        name_desc_re = re.compile(
            r"""name\s*:\s*["']([^"']+)["'][^}]{0,300}?description\s*:\s*["']([^"']+)["']""",
            re.DOTALL,
        )
        for m in name_desc_re.finditer(src_text):
            tools.append((m.group(1), m.group(2)))

        discovered_names = [t[0] for t in tools]
        for tool_name, desc in tools:
            findings.extend(self._check_description(tool_name, desc, src, 0))

        findings.extend(self._check_code("<module>", src_text, src, 0))
        servers = 1 if re.search(r"new\s+Server\s*\(", src_text) else 0
        return findings, len(tools), servers, discovered_names

    # ── Pattern checkers ─────────────────────────────────────────────────────

    def _check_description(
        self, tool_name: str, desc: str, source_file: str, line: int
    ) -> List[MCPToolFinding]:
        findings = []
        seen: set = set()
        for pattern, attack_type, severity in self._desc_compiled:
            m = pattern.search(desc)
            if m and attack_type not in seen:
                seen.add(attack_type)
                findings.append(MCPToolFinding(
                    tool_name=tool_name,
                    attack_type=attack_type,
                    severity=severity,
                    description=f"Tool description contains {attack_type} pattern",
                    evidence=m.group(0)[:120],
                    source_file=source_file,
                    line_number=line,
                ))
        return findings

    def _check_code(
        self, tool_name: str, code: str, source_file: str, start_line: int
    ) -> List[MCPToolFinding]:
        findings = []
        seen: set = set()
        for pattern, attack_type, severity in self._code_compiled:
            m = pattern.search(code)
            if m and attack_type not in seen:
                seen.add(attack_type)
                # Compute approximate line number
                line_num = start_line + code[: m.start()].count("\n")
                findings.append(MCPToolFinding(
                    tool_name=tool_name,
                    attack_type=attack_type,
                    severity=severity,
                    description=f"Tool handler contains {attack_type} pattern",
                    evidence=m.group(0)[:120],
                    source_file=source_file,
                    line_number=line_num,
                ))
        return findings

    def _check_schema(
        self, tool_name: str, schema: Any, source_file: str, line: int
    ) -> List[MCPToolFinding]:
        findings = []
        if not isinstance(schema, dict):
            return findings
        props = schema.get("properties", {})
        for param_name, param_schema in props.items():
            if param_name.lower() in _HIGH_RISK_PARAM_NAMES:
                if isinstance(param_schema, dict):
                    has_constraint = any(
                        k in param_schema
                        for k in ("pattern", "enum", "format", "maxLength", "const")
                    )
                    if not has_constraint:
                        findings.append(MCPToolFinding(
                            tool_name=tool_name,
                            attack_type="UNCONSTRAINED_SCOPE",
                            severity="medium",
                            description=(
                                f"High-risk parameter '{param_name}' has no validation "
                                f"constraint (pattern/enum/format/maxLength)"
                            ),
                            evidence=f"param: {param_name}, schema: {str(param_schema)[:80]}",
                            source_file=source_file,
                            line_number=line,
                        ))
        return findings

    def _check_schema_from_annotations(
        self, tool_name: str, body: str, source_file: str, line: int
    ) -> List[MCPToolFinding]:
        """Detect high-risk parameter names in Python function signatures."""
        findings = []
        for param in _HIGH_RISK_PARAM_NAMES:
            # Match: param_name: str (no default, no Annotated)
            if re.search(rf"\b{re.escape(param)}\s*:\s*str\b", body):
                findings.append(MCPToolFinding(
                    tool_name=tool_name,
                    attack_type="UNCONSTRAINED_SCOPE",
                    severity="medium",
                    description=(
                        f"High-risk parameter '{param}' typed as bare str "
                        f"with no validation"
                    ),
                    evidence=f"param: {param}: str",
                    source_file=source_file,
                    line_number=line,
                ))
                break  # one finding per tool for this check
        return findings

    def _check_config_text(
        self, tool_name: str, text: str, source_file: str
    ) -> List[MCPToolFinding]:
        findings = []
        seen: set = set()
        for pattern, attack_type, severity in self._cfg_compiled:
            m = pattern.search(text)
            if m and attack_type not in seen:
                seen.add(attack_type)
                findings.append(MCPToolFinding(
                    tool_name=tool_name,
                    attack_type=attack_type,
                    severity=severity,
                    description=f"MCP server config contains {attack_type} pattern",
                    evidence=m.group(0)[:120],
                    source_file=source_file,
                    line_number=0,
                ))
        return findings

    def _check_server_config(
        self, srv_name: str, cfg: Any, source_file: str
    ) -> List[MCPToolFinding]:
        """Check a single mcpServers entry for dangerous patterns."""
        findings = []
        if not isinstance(cfg, dict):
            return findings
        # Scan env block for missing/empty tokens
        env = cfg.get("env", {})
        if isinstance(env, dict):
            for k, v in env.items():
                if re.search(r"(?i)token|key|secret|password|auth", k) and not v:
                    findings.append(MCPToolFinding(
                        tool_name=srv_name,
                        attack_type="MISSING_AUTH",
                        severity="high",
                        description=f"Environment variable '{k}' is empty in server config",
                        evidence=f"{k}={repr(v)}",
                        source_file=source_file,
                        line_number=0,
                    ))
        # Command that pipes to shell
        command = cfg.get("command", "")
        args = " ".join(cfg.get("args", []) if isinstance(cfg.get("args"), list) else [])
        full_cmd = f"{command} {args}".strip()
        if re.search(r"\|\s*(ba)?sh\b|\|\s*cmd\b", full_cmd):
            findings.append(MCPToolFinding(
                tool_name=srv_name,
                attack_type="COMMAND_INJECTION",
                severity="critical",
                description="MCP server command pipes to shell",
                evidence=full_cmd[:120],
                source_file=source_file,
                line_number=0,
            ))
        return findings

    def _detect_shadow_tools(self, tool_names: List[str]) -> List[MCPToolFinding]:
        """Flag duplicate tool names across different files (shadow tool attack)."""
        seen: Dict[str, int] = {}
        for name in tool_names:
            seen[name] = seen.get(name, 0) + 1
        findings = []
        for name, count in seen.items():
            if count > 1:
                findings.append(MCPToolFinding(
                    tool_name=name,
                    attack_type="SHADOW_TOOL",
                    severity="high",
                    description=(
                        f"Tool name '{name}' appears {count} times across MCP servers "
                        f"— possible shadow tool attack (OWASP LLM01)"
                    ),
                    evidence=f"duplicate count: {count}",
                    source_file="<multi-file>",
                    line_number=0,
                ))
        return findings

    # ── Risk score ───────────────────────────────────────────────────────────

    @staticmethod
    def _compute_risk_score(findings: List[MCPToolFinding]) -> float:
        if not findings:
            return 0.0
        return min(1.0, sum(SEVERITY_WEIGHTS.get(f.severity, 0.0) for f in findings))
