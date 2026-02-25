Nick Homyk
nickhomyk@gmail.com | +1 914 204 2139
linkedin.com/in/nhomyk | github.com/nhomyk | medium.com/@nickhomyk

February 25, 2026

GRC Automation Lead Search
Anthropic

Dear Hiring Team,

I've been building with Claude since it first became available to developers. Anthropic is the company I respect most in the industry, not just for the technology, but for the seriousness with which you approach building it responsibly. So when I came across the GRC Automation Lead role, it felt like an obvious fit worth pursuing.

Over the past year I've built AgenticQA, an open-source compliance and quality automation platform that runs entirely on Claude. It started as a CI/CD quality tool and grew into something much closer to what this role describes: a system that converts written policies into executable rules, monitors compliance continuously across pipeline runs, trends violations over time, attributes risk to individual developers through automated evidence collection, and gates deployments based on learned risk scores. I didn't set out to build a GRC platform, but that's what the problem required.

A few things from your job description are worth addressing directly.

On policy-as-code: AgenticQA includes a Constitutional Gate that takes organizational policies around destructive actions, deployment restrictions, and bulk operations and converts them into code that runs on every agent action. When adversarial red-team scans surface new bypass patterns, the system generates proposals for human review rather than auto-patching constitutional logic. That design choice was intentional. Some decisions shouldn't be automated, and the system knows which ones those are.

On continuous monitoring: the Compliance Agent checks data encryption, PII protection, and audit log status on every pipeline invocation. A separate drift detector persists violation snapshots per repo per run, compares consecutive runs, and surfaces whether compliance is improving, stable, or worsening along with which specific rule types are trending the wrong direction. That's the same analysis a GRC analyst performs manually, running automatically on every commit.

On agentic Claude workflows: the platform runs eight specialized agents (QA, SRE, Compliance, Red Team, SDET, and others) orchestrated through a hybrid RAG layer combining Weaviate, Neo4j, and PostgreSQL. Claude Haiku generates targeted test files for uncovered modules and proposes lint fixes that are validated before being applied. The job description calls agentic AI workflow experience a strong preferred qualification. It's the foundation of what I've been building.

On the engineering integration side: every agent result, from ESLint violations to CVE findings to compliance drift snapshots, is ingested into the learning pipeline through GitHub Actions. Compliance isn't treated as a separate concern; it's wired into the same artifact pipeline as everything else.

On leadership: I ran a 15-person engineering organization at Blue Bite as Interim Head of Engineering, coordinating across product, QA, and infrastructure. I'm currently training engineering teams at Paychex on agentic AI practices. Building and enabling a team is work I've done and enjoy.

I'll be honest about the gaps: I don't have years of Vanta or Drata configuration experience, and I haven't held a formal GRC title. What I do have is a working compliance automation system built on Claude, strong Python engineering skills, firsthand experience wiring GRC outputs into CI/CD pipelines, and a real investment in Anthropic's mission that predates this application. I think those things matter for a role that's building the function from scratch.

I'd welcome the opportunity to discuss further.

Sincerely,

Nick Homyk
