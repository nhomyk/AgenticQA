"""Unit tests for LegalRiskScanner — @pytest.mark.unit"""
import pytest
from pathlib import Path

from agenticqa.security.legal_risk_scanner import (
    LegalRiskFinding,
    LegalRiskResult,
    LegalRiskScanner,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_scanner() -> LegalRiskScanner:
    return LegalRiskScanner()


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Credential scanning
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCredentialScanning:
    def test_mongodb_uri_detected(self, tmp_path):
        write(tmp_path / "app" / "route.ts",
              'const MONGO_URI = "mongodb+srv://user:secret123@cluster.mongodb.net/";\n')
        result = make_scanner().scan(str(tmp_path))
        creds = [f for f in result.findings if f.rule_id == "CREDENTIAL_EXPOSURE"]
        assert len(creds) >= 1
        assert creds[0].severity == "critical"
        assert "MongoDB" in creds[0].message

    def test_aws_key_detected(self, tmp_path):
        write(tmp_path / "config.py",
              'AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"\n')
        result = make_scanner().scan(str(tmp_path))
        creds = [f for f in result.findings if f.rule_id == "CREDENTIAL_EXPOSURE"]
        assert any(f.severity == "critical" for f in creds)

    def test_openai_key_detected(self, tmp_path):
        write(tmp_path / "app.js",
              'const apiKey = "sk-abcdefghijklmnopqrstuvwxyz1234567890";\n')
        result = make_scanner().scan(str(tmp_path))
        creds = [f for f in result.findings if f.rule_id == "CREDENTIAL_EXPOSURE"]
        assert any(f.severity == "critical" for f in creds)

    def test_hardcoded_password_detected(self, tmp_path):
        write(tmp_path / "settings.py",
              'password = "supersecretpassword"\n')
        result = make_scanner().scan(str(tmp_path))
        creds = [f for f in result.findings if f.rule_id == "CREDENTIAL_EXPOSURE"]
        assert any(f.severity == "high" for f in creds)

    def test_env_example_skipped(self, tmp_path):
        # .env.example with placeholder — should NOT be flagged
        write(tmp_path / ".env.example",
              'DB_PASSWORD=changeme\nMONGO_URI=mongodb+srv://user:changeme@host\n')
        result = make_scanner().scan(str(tmp_path))
        creds = [f for f in result.findings if f.rule_id == "CREDENTIAL_EXPOSURE"]
        assert len(creds) == 0

    def test_private_key_detected(self, tmp_path):
        write(tmp_path / "key.py",
              '# embed key\nKEY = "-----BEGIN RSA PRIVATE KEY-----\\nMIIE...\\n-----END RSA PRIVATE KEY-----"\n')
        result = make_scanner().scan(str(tmp_path))
        creds = [f for f in result.findings if f.rule_id == "CREDENTIAL_EXPOSURE"]
        assert any(f.severity == "critical" for f in creds)

    def test_no_credential_in_clean_file(self, tmp_path):
        write(tmp_path / "utils.py",
              'def add(a, b):\n    return a + b\n')
        result = make_scanner().scan(str(tmp_path))
        creds = [f for f in result.findings if f.rule_id == "CREDENTIAL_EXPOSURE"]
        assert len(creds) == 0


# ---------------------------------------------------------------------------
# SSRF scanning
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSSRFScanning:
    def test_localhost_url_in_fetch(self, tmp_path):
        write(tmp_path / "api" / "proxy.ts",
              'const response = await fetch("http://localhost:8000/analyze", { method: "POST" });\n')
        result = make_scanner().scan(str(tmp_path))
        ssrf = [f for f in result.findings if f.rule_id == "SSRF_RISK"]
        assert len(ssrf) >= 1
        assert ssrf[0].severity == "medium"

    def test_no_ssrf_in_clean_code(self, tmp_path):
        write(tmp_path / "app.ts",
              'const url = process.env.BACKEND_URL;\nconst r = await fetch(url);\n')
        result = make_scanner().scan(str(tmp_path))
        ssrf = [f for f in result.findings if f.rule_id == "SSRF_RISK"]
        assert len(ssrf) == 0


# ---------------------------------------------------------------------------
# PII document scanning
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPIIDocumentScanning:
    def test_employment_agreement_in_public(self, tmp_path):
        pdf = tmp_path / "public" / "Nathaniel - Employment Agreement.pdf"
        pdf.parent.mkdir(parents=True)
        pdf.write_bytes(b"%PDF-1.4 fake content")
        result = make_scanner().scan(str(tmp_path))
        pii = [f for f in result.findings if f.rule_id == "PII_DOCUMENT_PUBLIC"]
        assert len(pii) >= 1
        assert pii[0].severity == "critical"

    def test_nda_in_static_dir(self, tmp_path):
        doc = tmp_path / "static" / "NDA_Template.docx"
        doc.parent.mkdir(parents=True)
        doc.write_bytes(b"PK fake docx")
        result = make_scanner().scan(str(tmp_path))
        pii = [f for f in result.findings if f.rule_id == "PII_DOCUMENT_PUBLIC"]
        assert any(f.severity == "critical" for f in pii)

    def test_generic_pdf_in_public_is_high(self, tmp_path):
        pdf = tmp_path / "public" / "annual-report.pdf"
        pdf.parent.mkdir(parents=True)
        pdf.write_bytes(b"%PDF-1.4 fake")
        result = make_scanner().scan(str(tmp_path))
        pii = [f for f in result.findings if f.rule_id == "PII_DOCUMENT_PUBLIC"]
        assert len(pii) >= 1
        assert pii[0].severity == "high"

    def test_pdf_not_in_public_not_flagged(self, tmp_path):
        pdf = tmp_path / "src" / "docs" / "Employment Agreement.pdf"
        pdf.parent.mkdir(parents=True)
        pdf.write_bytes(b"%PDF-1.4 fake")
        result = make_scanner().scan(str(tmp_path))
        pii = [f for f in result.findings if f.rule_id == "PII_DOCUMENT_PUBLIC"]
        assert len(pii) == 0


# ---------------------------------------------------------------------------
# Privilege exposure scanning
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPrivilegeExposure:
    def test_file_read_then_llm_call_flagged(self, tmp_path):
        write(tmp_path / "app" / "api" / "chat" / "route.ts", """\
import fs from "fs/promises";
import OpenAI from "openai";

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

export async function POST(request) {
  const pdfText = await fs.readFile("public/contract.txt", "utf-8");
  const context = `DOCUMENT CONTENT:\\n${pdfText}`;
  const completion = await openai.chat.completions.create({
    model: "gpt-4o",
    messages: [{ role: "system", content: context }],
  });
  return Response.json({ response: completion.choices[0].message.content });
}
""")
        result = make_scanner().scan(str(tmp_path))
        priv = [f for f in result.findings if f.rule_id == "PRIVILEGE_BREACH"]
        assert len(priv) >= 1
        assert priv[0].severity == "high"

    def test_file_read_without_llm_not_flagged(self, tmp_path):
        write(tmp_path / "utils.ts", """\
import fs from "fs/promises";

export async function loadConfig() {
  const data = await fs.readFile("config.json", "utf-8");
  return JSON.parse(data);
}
""")
        result = make_scanner().scan(str(tmp_path))
        priv = [f for f in result.findings if f.rule_id == "PRIVILEGE_BREACH"]
        assert len(priv) == 0


# ---------------------------------------------------------------------------
# Missing auth scanning
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestMissingAuth:
    def test_unprotected_post_route_flagged(self, tmp_path):
        write(tmp_path / "app" / "api" / "upload" / "route.ts", """\
import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const body = await request.json();
  return NextResponse.json({ ok: true });
}
""")
        result = make_scanner().scan(str(tmp_path))
        auth = [f for f in result.findings if f.rule_id == "NO_AUTH_ROUTE"]
        assert len(auth) >= 1
        assert auth[0].severity == "medium"

    def test_authenticated_route_not_flagged(self, tmp_path):
        write(tmp_path / "app" / "api" / "data" / "route.ts", """\
import { NextRequest, NextResponse } from "next/server";
import { getSession } from "next-auth/react";

export async function GET(request: NextRequest) {
  const session = getSession({ req: request });
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  return NextResponse.json({ data: "secret" });
}
""")
        result = make_scanner().scan(str(tmp_path))
        auth = [f for f in result.findings if f.rule_id == "NO_AUTH_ROUTE"]
        assert len(auth) == 0


# ---------------------------------------------------------------------------
# Risk score calculation
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRiskScore:
    def test_empty_findings_score_zero(self, tmp_path):
        result = make_scanner().scan(str(tmp_path))
        assert result.risk_score == 0.0
        assert len(result.findings) == 0

    def test_all_critical_score_is_one(self):
        scanner = make_scanner()
        findings = [
            LegalRiskFinding("a.ts", 1, "CREDENTIAL_EXPOSURE", "critical", "msg"),
            LegalRiskFinding("b.ts", 2, "CREDENTIAL_EXPOSURE", "critical", "msg"),
            LegalRiskFinding("c.ts", 3, "CREDENTIAL_EXPOSURE", "critical", "msg"),
        ]
        result = scanner._build_result(findings)
        assert result.risk_score == 1.0
        assert len(result.critical_findings) == 3

    def test_mixed_severities_score_between(self):
        scanner = make_scanner()
        findings = [
            LegalRiskFinding("a.ts", 1, "CREDENTIAL_EXPOSURE", "critical", "msg"),  # 1.0
            LegalRiskFinding("b.ts", 2, "NO_AUTH_ROUTE", "medium", "msg"),           # 0.4
        ]
        result = scanner._build_result(findings)
        # mean([1.0, 0.4]) = 0.7
        assert abs(result.risk_score - 0.7) < 0.01

    def test_clean_repo_no_findings(self, tmp_path):
        write(tmp_path / "hello.py", "def greet(): return 'hello'\n")
        result = make_scanner().scan(str(tmp_path))
        assert result.risk_score == 0.0
        assert result.scan_error is None
