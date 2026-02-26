"""Unit tests for HIPAAPHIScanner — @pytest.mark.unit"""
import pytest
from pathlib import Path

from agenticqa.security.hipaa_phi_scanner import (
    PHIFinding,
    HIPAAResult,
    HIPAAPHIScanner,
)


def make_scanner() -> HIPAAPHIScanner:
    return HIPAAPHIScanner()


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Hardcoded PHI
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestHardcodedPHI:
    def test_ssn_literal_detected(self, tmp_path):
        write(tmp_path / "seed.py", 'test_ssn = "123-45-6789"\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PHI_HARDCODED"]
        assert len(hits) >= 1
        assert hits[0].severity == "critical"

    def test_ssn_assignment_detected(self, tmp_path):
        write(tmp_path / "fixtures.ts",
              'const ssn = "987-65-4321";\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PHI_HARDCODED"]
        assert any(f.severity == "critical" for f in hits)

    def test_dob_assignment_detected(self, tmp_path):
        write(tmp_path / "patient.py",
              'date_of_birth = "1985-03-22"\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PHI_HARDCODED"]
        assert len(hits) >= 1
        assert hits[0].severity == "critical"

    def test_mrn_assignment_detected(self, tmp_path):
        write(tmp_path / "db_seed.ts",
              'const mrn = "MRN-00123456";\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PHI_HARDCODED"]
        assert len(hits) >= 1

    def test_clean_file_no_phi(self, tmp_path):
        write(tmp_path / "utils.py", "def add(a, b):\n    return a + b\n")
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PHI_HARDCODED"]
        assert len(hits) == 0


# ---------------------------------------------------------------------------
# PHI in logs
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPHIInLogs:
    def test_phi_var_in_console_log(self, tmp_path):
        write(tmp_path / "api.ts",
              'console.log("Patient data:", patient_id, diagnosis);\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PHI_IN_LOGS"]
        assert len(hits) >= 1
        assert hits[0].severity == "high"

    def test_phi_var_in_python_logging(self, tmp_path):
        write(tmp_path / "service.py",
              'logger.info(f"Processing patient_id={patient_id}")\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PHI_IN_LOGS"]
        assert len(hits) >= 1

    def test_non_phi_log_no_finding(self, tmp_path):
        write(tmp_path / "server.py",
              'logger.info("Server started on port 8080")\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PHI_IN_LOGS"]
        assert len(hits) == 0


# ---------------------------------------------------------------------------
# PHI to LLM
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPHIToLLM:
    def test_phi_then_llm_call_flagged(self, tmp_path):
        write(tmp_path / "app" / "api" / "chat" / "route.ts", """\
import OpenAI from "openai";
const openai = new OpenAI();

export async function POST(request) {
  const diagnosis = await getDiagnosis(patientId);
  const context = `Patient diagnosis: ${diagnosis}`;
  const completion = await openai.chat.completions.create({
    model: "gpt-4o",
    messages: [{ role: "system", content: context }],
  });
  return Response.json({ response: completion.choices[0].message.content });
}
""")
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PHI_TO_LLM"]
        assert len(hits) >= 1
        assert hits[0].severity == "critical"

    def test_phi_var_without_llm_not_flagged(self, tmp_path):
        write(tmp_path / "service.py", """\
def get_patient_summary(patient_id):
    patient_data = db.query(patient_id)
    return {"id": patient_data.id, "name": patient_data.name}
""")
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PHI_TO_LLM"]
        assert len(hits) == 0


# ---------------------------------------------------------------------------
# HIPAA audit missing
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestHIPAAAudit:
    def test_patient_route_without_audit_flagged(self, tmp_path):
        write(tmp_path / "app" / "api" / "patient" / "route.ts", """\
import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const patientData = await db.getPatient(request.params.id);
  return NextResponse.json(patientData);
}
""")
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "HIPAA_AUDIT_MISSING"]
        assert len(hits) >= 1
        assert hits[0].severity == "high"

    def test_patient_route_with_audit_ok(self, tmp_path):
        write(tmp_path / "app" / "api" / "patient" / "route.ts", """\
import { NextRequest, NextResponse } from "next/server";
import { audit_log } from "@/lib/hipaa";

export async function GET(request: NextRequest) {
  await audit_log("patient_read", request);
  const patientData = await db.getPatient(request.params.id);
  return NextResponse.json(patientData);
}
""")
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "HIPAA_AUDIT_MISSING"]
        assert len(hits) == 0


# ---------------------------------------------------------------------------
# PHI documents in public
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPHIDocuments:
    def test_hl7_in_public_flagged(self, tmp_path):
        hl7 = tmp_path / "public" / "patient_record.hl7"
        hl7.parent.mkdir(parents=True)
        hl7.write_bytes(b"MSH|^~\\&|...")
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PHI_DOCUMENT_PUBLIC"]
        assert len(hits) >= 1
        assert hits[0].severity == "critical"

    def test_patient_csv_in_public_flagged(self, tmp_path):
        csv = tmp_path / "static" / "patient_data.csv"
        csv.parent.mkdir(parents=True)
        csv.write_text("patient_id,name,dob\n001,Jane Doe,1990-01-01\n")
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PHI_DOCUMENT_PUBLIC"]
        assert len(hits) >= 1

    def test_phi_doc_not_in_public_ok(self, tmp_path):
        csv = tmp_path / "src" / "fixtures" / "patient_data.csv"
        csv.parent.mkdir(parents=True)
        csv.write_text("patient_id,name\n001,Test\n")
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PHI_DOCUMENT_PUBLIC"]
        assert len(hits) == 0


# ---------------------------------------------------------------------------
# Risk score + clean repo
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRiskScore:
    def test_clean_repo_zero(self, tmp_path):
        result = make_scanner().scan(str(tmp_path))
        assert result.risk_score == 0.0
        assert result.scan_error is None

    def test_all_critical_score_one(self):
        scanner = make_scanner()
        findings = [
            PHIFinding("a.ts", 1, "PHI_HARDCODED", "critical", "msg"),
            PHIFinding("b.ts", 2, "PHI_TO_LLM", "critical", "msg"),
            PHIFinding("c.ts", 3, "PHI_HARDCODED", "critical", "msg"),
        ]
        result = scanner._build_result(findings)
        assert result.risk_score == 1.0
        assert len(result.critical_findings) == 3

    def test_mixed_severities(self):
        scanner = make_scanner()
        findings = [
            PHIFinding("a.ts", 1, "PHI_HARDCODED", "critical", "msg"),  # 1.0
            PHIFinding("b.ts", 2, "PHI_IN_LOGS", "high", "msg"),        # 0.7
        ]
        result = scanner._build_result(findings)
        # mean([1.0, 0.7]) = 0.85
        assert abs(result.risk_score - 0.85) < 0.01
