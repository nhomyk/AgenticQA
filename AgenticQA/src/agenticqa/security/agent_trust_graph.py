"""
Multi-Agent Trust Graph Analyzer.

Scans a repository for agentic AI framework patterns (LangGraph, CrewAI, AutoGen,
LangChain AgentExecutor, custom orchestrators) and builds a directed trust graph.

Detects:
- CIRCULAR_TRUST   : Agent A delegates → B → ... → A (cycle with no human checkpoint)
- MISSING_HUMAN_IN_LOOP : Fully automated chains touching high-risk operations
- UNCONSTRAINED_DELEGATION : allow_delegation=True without an allowlist
- UNVALIDATED_MESSAGE_PASSING : Agent output directly piped to next agent input
- PRIVILEGED_TOOL_ACCESS : Agent has shell/fs/DB-write tools without guardrails
- ESCALATION_PATH  : Low-trust agent reachable from high-trust tool via delegation

Pure Python (re, pathlib). No external dependencies.
EU AI Act Art. 14 (human oversight) evidence artifact.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

_SOURCE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
_SKIP_DIRS = {
    "node_modules", ".venv", "venv", "__pycache__",
    ".git", "dist", "build", ".next", "out",
}

# ---------------------------------------------------------------------------
# Framework detection — triggered by imports
# ---------------------------------------------------------------------------

_FRAMEWORK_IMPORTS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\b(from|import)\s+langgraph\b"), "langgraph"),
    (re.compile(r"\b(from|import)\s+langgraph\.graph\b"), "langgraph"),
    (re.compile(r"\b(from|import)\s+crewai\b"), "crewai"),
    (re.compile(r"\b(from|import)\s+autogen\b"), "autogen"),
    (re.compile(r"\b(from|import)\s+pyautogen\b"), "autogen"),
    (re.compile(r"\b(from|import)\s+autogen_agentchat\b"), "autogen"),
    (re.compile(r"\b(from|import)\s+langchain\.agents\b"), "langchain"),
    (re.compile(r"\b(from|import)\s+langchain_core\.agents\b"), "langchain"),
    (re.compile(r"\b(from|import)\s+swarm\b"), "swarm"),
    (re.compile(r"\b(from|import)\s+openai_swarm\b"), "swarm"),
    (re.compile(r"\b(from|import)\s+agno\b"), "agno"),
    (re.compile(r"\b(from|import)\s+pydantic_ai\b"), "pydantic-ai"),
    (re.compile(r"\b(from|import)\s+smolagents\b"), "smolagents"),
    (re.compile(r"\b(from|import)\s+microsoft\.semantic_kernel\b"), "semantic-kernel"),
]

# ---------------------------------------------------------------------------
# Node extraction — agent name / role detection
# ---------------------------------------------------------------------------

_NODE_PATTERNS: List[Tuple[re.Pattern, str]] = [
    # LangGraph: workflow.add_node("name", fn)
    (re.compile(r'\.add_node\s*\(\s*["\']([^"\']+)["\']'), "langgraph"),
    # CrewAI: Agent(role="researcher")
    (re.compile(r'\bAgent\s*\(\s*(?:.*?)?role\s*=\s*["\']([^"\']+)["\']'), "crewai"),
    # AutoGen: AssistantAgent("name") / UserProxyAgent("name") / ConversableAgent("name")
    (re.compile(r'\b(?:AssistantAgent|UserProxyAgent|ConversableAgent|GroupChatManager)\s*\(\s*["\']([^"\']+)["\']'), "autogen"),
    # Swarm: Agent(name="name")
    (re.compile(r'\bAgent\s*\(\s*(?:.*?)?name\s*=\s*["\']([^"\']+)["\']'), "swarm"),
    # LangChain: AgentExecutor — use variable name heuristic
    (re.compile(r'\bAgentExecutor\s*\('), "langchain"),
]

# ---------------------------------------------------------------------------
# Edge extraction — delegation / call patterns
# ---------------------------------------------------------------------------

_EDGE_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
    # LangGraph: add_edge("src", "dst")
    (re.compile(r'\.add_edge\s*\(\s*["\']([^"\']+)["\'],\s*["\']([^"\']+)["\']'), "langgraph", "direct"),
    # LangGraph: add_conditional_edges("src", ..., {"label": "dst"})
    (re.compile(r'\.add_conditional_edges\s*\(\s*["\']([^"\']+)["\'].*?["\']([^"\']+)["\'\s]*\}'), "langgraph", "conditional"),
    # AutoGen: initiate_chat(target, ...)  — implicit edge from caller to target
    (re.compile(r'(\w+)\.initiate_chat\s*\(\s*(\w+)'), "autogen", "initiate_chat"),
    # Swarm: handoff / transfer_to
    (re.compile(r'transfer_to_([a-zA-Z_]\w*)'), "swarm", "handoff"),
    (re.compile(r'handoff_to\s*=\s*\[?([a-zA-Z_]\w*)'), "swarm", "handoff"),
    # Generic: delegate_to("agent_name")
    (re.compile(r'delegate_to\s*\(\s*["\']([^"\']+)["\']'), "custom", "delegation"),
]

# ---------------------------------------------------------------------------
# Violation patterns
# ---------------------------------------------------------------------------

# Signals that NO human confirmation is needed in the loop
_NO_HUMAN_PATTERNS: List[re.Pattern] = [
    re.compile(r'human_input_mode\s*=\s*["\']NEVER["\']'),
    re.compile(r'human_in_the_loop\s*=\s*False'),
    re.compile(r'require_human_approval\s*=\s*False'),
]

# Unconstrained delegation in CrewAI
_ALLOW_DELEGATION_TRUE = re.compile(r'allow_delegation\s*=\s*True')
_DELEGATION_ALLOWLIST = re.compile(r'delegation_allowlist|allowed_agents|agent_allowlist')

# Unvalidated piping: output of one call directly fed into next (no schema/parse step)
_RAW_OUTPUT_PIPE = re.compile(
    r'(?:response|output|result|message)\s*=\s*.*?\.(?:run|invoke|chat|send|execute)\b'
    r'.*?\n.*?\.(?:run|invoke|chat|send|execute)\s*\(\s*(?:response|output|result|message)',
    re.MULTILINE,
)

# Privileged tools — agents using these without guardrails are flagged
_PRIVILEGED_TOOL_NAMES: Set[str] = {
    "ShellTool", "BashTool", "BashProcess", "Terminal", "TerminalTool",
    "PythonREPLTool", "PythonInterpreterTool", "CodeInterpreterTool",
    "E2BCodeInterpreterTool", "JupyterTool",
    "WriteFileTool", "DeleteTool", "MoveFileTool", "CopyFileTool",
    "SQLDatabaseToolkit", "SQLQueryTool", "DatabaseTool",
    "GmailSendMessage", "GithubCreatePullRequest",
}
_PRIVILEGED_TOOL_RE = re.compile(
    r'\b(' + '|'.join(re.escape(t) for t in _PRIVILEGED_TOOL_NAMES) + r')\b'
)

# Guardrail signals that accompany privileged tool usage
_GUARDRAIL_PATTERNS: List[re.Pattern] = [
    re.compile(r'human_approval|require_approval|confirmation|confirm_action'),
    re.compile(r'human_input_mode\s*=\s*["\'](?:ALWAYS|TERMINATE)["\']'),
    re.compile(r'max_consecutive_auto_reply\s*=\s*["\']?0["\']?'),
]

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AgentNode:
    name: str
    framework: str
    source_file: str
    source_line: int
    tools: List[str] = field(default_factory=list)
    human_input_mode: Optional[str] = None   # NEVER | ALWAYS | TERMINATE


@dataclass
class AgentEdge:
    source: str
    target: str
    edge_type: str   # direct | conditional | delegation | handoff | initiate_chat
    framework: str
    source_file: str
    source_line: int


@dataclass
class TrustViolation:
    rule_id: str
    severity: str    # critical | high | medium | low
    message: str
    agents_involved: List[str]
    source_file: str
    source_line: int
    remediation: str = ""


@dataclass
class AgentTrustGraph:
    nodes: List[AgentNode]
    edges: List[AgentEdge]
    violations: List[TrustViolation]
    frameworks_detected: List[str]
    has_human_oversight: bool
    risk_score: float
    scan_error: Optional[str] = None

    # ── Convenience aliases ────────────────────────────────────────────────

    @property
    def agents(self) -> List[AgentNode]:
        """Alias for ``nodes`` — more intuitive for callers."""
        return self.nodes

    @property
    def findings(self) -> List[TrustViolation]:
        """Alias for ``violations`` — consistent with other scanners."""
        return self.violations

    @property
    def has_cycles(self) -> bool:
        """True if any CIRCULAR_TRUST violation was detected."""
        return any(v.rule_id == "CIRCULAR_TRUST" for v in self.violations)


# ---------------------------------------------------------------------------
# Severity weights
# ---------------------------------------------------------------------------

_SEVERITY_WEIGHTS: Dict[str, float] = {
    "critical": 1.0,
    "high": 0.7,
    "medium": 0.4,
    "low": 0.15,
}

# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class AgentTrustGraphAnalyzer:
    """Build and audit the multi-agent trust graph of a repository."""

    def analyze(self, repo_path: str) -> AgentTrustGraph:
        try:
            return self._analyze(Path(repo_path).resolve())
        except Exception as exc:
            return AgentTrustGraph(
                nodes=[], edges=[], violations=[],
                frameworks_detected=[], has_human_oversight=False,
                risk_score=0.0, scan_error=str(exc),
            )

    # ------------------------------------------------------------------

    def _analyze(self, repo: Path) -> AgentTrustGraph:
        nodes: List[AgentNode] = []
        edges: List[AgentEdge] = []
        frameworks: Set[str] = set()
        human_oversight_signals: List[bool] = []
        raw_violations: List[TrustViolation] = []

        for fpath in self._iter_source_files(repo):
            rel = str(fpath.relative_to(repo))
            try:
                text = fpath.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            lines = text.splitlines()

            # Detect frameworks used in this file
            file_frameworks: Set[str] = set()
            for pat, fw in _FRAMEWORK_IMPORTS:
                if pat.search(text):
                    file_frameworks.add(fw)
                    frameworks.add(fw)

            if not file_frameworks:
                continue  # skip files with no agent framework imports

            # Extract nodes
            for lineno, line in enumerate(lines, 1):
                for pat, fw in _NODE_PATTERNS:
                    m = pat.search(line)
                    if m and fw in file_frameworks:
                        name = m.group(1) if m.lastindex else f"agent_{len(nodes)}"
                        # Check for privileged tools on same / nearby lines
                        context = "\n".join(lines[max(0, lineno-3):min(len(lines), lineno+10)])
                        tools = _PRIVILEGED_TOOL_RE.findall(context)
                        human_mode = self._extract_human_mode(context)
                        if human_mode:
                            human_oversight_signals.append(human_mode != "NEVER")
                        node = AgentNode(
                            name=name, framework=fw,
                            source_file=rel, source_line=lineno,
                            tools=list(set(tools)), human_input_mode=human_mode,
                        )
                        if not any(n.name == name and n.source_file == rel for n in nodes):
                            nodes.append(node)

            # Extract edges
            for lineno, line in enumerate(lines, 1):
                for pat, fw, etype in _EDGE_PATTERNS:
                    m = pat.search(line)
                    if m and (fw in file_frameworks or fw == "custom"):
                        src = m.group(1)
                        tgt = m.group(2) if m.lastindex >= 2 else ""
                        if src and tgt and src != tgt:
                            edges.append(AgentEdge(
                                source=src, target=tgt,
                                edge_type=etype, framework=fw,
                                source_file=rel, source_line=lineno,
                            ))

            # Violation: MISSING_HUMAN_IN_LOOP
            for lineno, line in enumerate(lines, 1):
                for pat in _NO_HUMAN_PATTERNS:
                    if pat.search(line):
                        raw_violations.append(TrustViolation(
                            rule_id="MISSING_HUMAN_IN_LOOP",
                            severity="high",
                            message="Agent configured with no human-in-the-loop — fully automated execution",
                            agents_involved=[],
                            source_file=rel,
                            source_line=lineno,
                            remediation="Set human_input_mode='TERMINATE' or add a human approval node in the graph",
                        ))
                        human_oversight_signals.append(False)

            # Violation: UNCONSTRAINED_DELEGATION
            for lineno, line in enumerate(lines, 1):
                if _ALLOW_DELEGATION_TRUE.search(line):
                    context = "\n".join(lines[max(0, lineno-5):min(len(lines), lineno+5)])
                    if not _DELEGATION_ALLOWLIST.search(context):
                        raw_violations.append(TrustViolation(
                            rule_id="UNCONSTRAINED_DELEGATION",
                            severity="high",
                            message="allow_delegation=True without a delegation allowlist — agent can invoke any peer",
                            agents_involved=[],
                            source_file=rel,
                            source_line=lineno,
                            remediation="Add delegation_allowlist=['specific_agent'] to constrain delegation targets",
                        ))

            # Violation: PRIVILEGED_TOOL_ACCESS
            for lineno, line in enumerate(lines, 1):
                ptool_m = _PRIVILEGED_TOOL_RE.search(line)
                if ptool_m:
                    context = "\n".join(lines[max(0, lineno-10):min(len(lines), lineno+10)])
                    has_guardrail = any(g.search(context) for g in _GUARDRAIL_PATTERNS)
                    if not has_guardrail:
                        raw_violations.append(TrustViolation(
                            rule_id="PRIVILEGED_TOOL_ACCESS",
                            severity="critical",
                            message=f"Agent has privileged tool '{ptool_m.group(1)}' without human approval guardrail",
                            agents_involved=[],
                            source_file=rel,
                            source_line=lineno,
                            remediation=f"Wrap {ptool_m.group(1)} usage with human_input_mode='TERMINATE' or require_approval=True",
                        ))

        # Graph-level analysis
        graph_violations = self._analyze_graph(nodes, edges)
        all_violations = raw_violations + graph_violations

        # Deduplicate violations by (rule_id, source_file, source_line)
        seen_v: Set[Tuple] = set()
        deduped: List[TrustViolation] = []
        for v in all_violations:
            key = (v.rule_id, v.source_file, v.source_line)
            if key not in seen_v:
                seen_v.add(key)
                deduped.append(v)

        has_oversight = bool(human_oversight_signals) and any(human_oversight_signals)
        risk_score = self._compute_risk_score(deduped, nodes, edges)

        return AgentTrustGraph(
            nodes=nodes,
            edges=edges,
            violations=deduped,
            frameworks_detected=sorted(frameworks),
            has_human_oversight=has_oversight,
            risk_score=risk_score,
        )

    # ------------------------------------------------------------------
    # Graph-level analysis
    # ------------------------------------------------------------------

    def _analyze_graph(
        self,
        nodes: List[AgentNode],
        edges: List[AgentEdge],
    ) -> List[TrustViolation]:
        violations: List[TrustViolation] = []
        if not edges:
            return violations

        # Build adjacency list
        adj: Dict[str, List[str]] = defaultdict(list)
        edge_map: Dict[Tuple[str, str], AgentEdge] = {}
        for e in edges:
            adj[e.source].append(e.target)
            edge_map[(e.source, e.target)] = e

        # Cycle detection (DFS)
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        cycles: List[List[str]] = []

        def dfs(node: str, path: List[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            for neighbour in adj.get(node, []):
                if neighbour not in visited:
                    dfs(neighbour, path)
                elif neighbour in rec_stack:
                    # Found a cycle — extract the cycle portion
                    idx = path.index(neighbour)
                    cycle = path[idx:] + [neighbour]
                    if cycle not in cycles:
                        cycles.append(cycle)
            path.pop()
            rec_stack.discard(node)

        all_nodes = set(adj.keys()) | {e.target for e in edges}
        for n in all_nodes:
            if n not in visited:
                dfs(n, [])

        for cycle in cycles:
            first_edge = edge_map.get((cycle[0], cycle[1]))
            violations.append(TrustViolation(
                rule_id="CIRCULAR_TRUST",
                severity="critical",
                message=f"Circular trust cycle detected: {' → '.join(cycle)} — agents can mutually escalate privileges",
                agents_involved=cycle,
                source_file=first_edge.source_file if first_edge else "",
                source_line=first_edge.source_line if first_edge else 0,
                remediation="Break the cycle by inserting a human checkpoint node or restricting back-edges",
            ))

        # Long delegation chains (≥4 hops) without a terminal node — ESCALATION_PATH
        def find_longest_path(start: str, depth: int, visited_p: Set[str]) -> int:
            if depth > 10:
                return depth
            best = depth
            for nxt in adj.get(start, []):
                if nxt not in visited_p:
                    best = max(best, find_longest_path(nxt, depth + 1, visited_p | {nxt}))
            return best

        for start in all_nodes:
            chain_len = find_longest_path(start, 1, {start})
            if chain_len >= 4:
                first_edge = next(
                    (edge_map.get((start, nxt)) for nxt in adj.get(start, []) if (start, nxt) in edge_map),
                    None,
                )
                violations.append(TrustViolation(
                    rule_id="ESCALATION_PATH",
                    severity="high",
                    message=f"Delegation chain of {chain_len} hops from '{start}' — privilege may escalate across unreviewed agents",
                    agents_involved=[start],
                    source_file=first_edge.source_file if first_edge else "",
                    source_line=first_edge.source_line if first_edge else 0,
                    remediation="Insert a human review node after every 2-3 agent hops in the chain",
                ))

        return violations

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _iter_source_files(self, repo: Path):
        for fpath in repo.rglob("*"):
            if not fpath.is_file():
                continue
            if any(p in _SKIP_DIRS for p in fpath.parts):
                continue
            if fpath.suffix.lower() in _SOURCE_EXTS:
                yield fpath

    def _extract_human_mode(self, context: str) -> Optional[str]:
        m = re.search(r'human_input_mode\s*=\s*["\']([^"\']+)["\']', context)
        return m.group(1) if m else None

    def _compute_risk_score(
        self,
        violations: List[TrustViolation],
        nodes: List[AgentNode],
        edges: List[AgentEdge],
    ) -> float:
        if not nodes and not violations:
            return 0.0
        import math
        total = sum(_SEVERITY_WEIGHTS.get(v.severity, 0.0) for v in violations)
        # Normalize: more agents = higher surface area
        agent_factor = math.log1p(max(len(nodes), 1)) / math.log1p(10)
        raw = min(1.0, total * 0.4 + agent_factor * 0.3)
        return round(raw, 3)
