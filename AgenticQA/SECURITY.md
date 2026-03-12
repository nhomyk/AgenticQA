# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | Yes       |

## Reporting a Vulnerability

Please report security vulnerabilities by opening a [GitHub Security Advisory](https://github.com/nhomyk/AgenticQA/security/advisories/new) rather than a public issue.

We aim to respond within 48 hours and release a patch within 7 days for critical findings.

---

## Known CVEs with No Fix Available

The following CVEs affect transitive dependencies where no patched version exists upstream. They are tracked here for transparency.

### CVE-2025-69872 — diskcache 5.6.3 (CRITICAL)

- **Package**: `diskcache`
- **Affected version**: 5.6.3 (latest)
- **Fix version**: None available as of 2026-03-12
- **Dependency path**: `ragas` → `diskcache`, `instructor` → `diskcache`
- **Status**: No upstream fix. Monitored via Dependabot. Will upgrade as soon as a patched version is published.
- **Mitigation**: AgenticQA does not expose diskcache objects directly to user input. RAG inference is performed in isolated CI jobs with read-only access to the vector stores.

---

## Dependency Security Controls

- **Dependabot**: Enabled for `pip` and `github-actions` ecosystems, weekly scans including patch releases.
- **pip-audit**: Runs as a CI step on every push to `main` (see `ci.yml` `pip-audit` job).
- **Pinned transitive CVEs**: Known-vulnerable transitive deps are explicitly floor-pinned in `pyproject.toml` once a fix is available (e.g. `langgraph>=1.0.10` for CVE-2026-28277).
- **pip upgrade**: All CI jobs run `python -m pip install --upgrade pip` before installing dependencies.
