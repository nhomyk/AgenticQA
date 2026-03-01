"""Tests for shadow AI / unauthorized model detection."""
import pytest
from agenticqa.security.shadow_ai_detector import (
    ShadowAIDetector, ShadowAIReport, DEFAULT_APPROVED_MODELS,
)


@pytest.fixture
def detector():
    return ShadowAIDetector()


@pytest.fixture
def permissive_detector():
    """Detector that approves OpenAI too."""
    return ShadowAIDetector(
        approved_providers={"anthropic", "openai"},
        approved_models=set(DEFAULT_APPROVED_MODELS) | {"gpt-4o"},
    )


# ── Model ID detection ──────────────────────────────────────────────────────

class TestModelDetection:
    @pytest.mark.unit
    def test_detect_unapproved_openai_model(self, detector):
        code = 'client.chat.completions.create(model="gpt-4o")'
        report = detector.scan_text(code)
        assert report.has_shadow_ai
        assert any(f.model_id == "gpt-4o" for f in report.findings)
        assert any(f.provider == "openai" for f in report.findings)

    @pytest.mark.unit
    def test_detect_unapproved_gemini(self, detector):
        code = 'model = genai.GenerativeModel("gemini-2.0-flash")'
        report = detector.scan_text(code)
        assert report.has_shadow_ai
        assert any(f.provider == "google" for f in report.findings)

    @pytest.mark.unit
    def test_approved_claude_model_no_finding(self, detector):
        code = 'client.messages.create(model="claude-opus-4-6")'
        report = detector.scan_text(code)
        # Should not flag approved models
        model_findings = [f for f in report.findings if f.rule_id == "UNAPPROVED_MODEL"]
        assert len(model_findings) == 0

    @pytest.mark.unit
    def test_detect_llama(self, detector):
        code = 'model_name = "llama-3-70b"'
        report = detector.scan_text(code)
        assert any(f.provider == "meta" for f in report.findings)

    @pytest.mark.unit
    def test_detect_mistral(self, detector):
        code = 'load_model("mistral-7b-instruct")'
        report = detector.scan_text(code)
        assert any(f.provider == "mistral" for f in report.findings)

    @pytest.mark.unit
    def test_detect_deepseek(self, detector):
        code = 'model = "deepseek-coder-v2"'
        report = detector.scan_text(code)
        assert any(f.provider == "deepseek" for f in report.findings)

    @pytest.mark.unit
    def test_approved_model_in_permissive_config(self, permissive_detector):
        code = 'client.chat.completions.create(model="gpt-4o")'
        report = permissive_detector.scan_text(code)
        model_findings = [f for f in report.findings if f.rule_id == "UNAPPROVED_MODEL"]
        assert len(model_findings) == 0


# ── Provider import detection ────────────────────────────────────────────────

class TestProviderImports:
    @pytest.mark.unit
    def test_detect_openai_import(self, detector):
        code = "import openai\nclient = openai.OpenAI()"
        report = detector.scan_text(code)
        assert any(f.rule_id == "UNAPPROVED_PROVIDER" and f.provider == "openai"
                    for f in report.findings)

    @pytest.mark.unit
    def test_detect_from_openai_import(self, detector):
        code = "from openai import ChatCompletion"
        report = detector.scan_text(code)
        assert any(f.rule_id == "UNAPPROVED_PROVIDER" for f in report.findings)

    @pytest.mark.unit
    def test_detect_google_genai(self, detector):
        code = "import google.generativeai as genai"
        report = detector.scan_text(code)
        assert any(f.provider == "google" for f in report.findings)

    @pytest.mark.unit
    def test_detect_cohere(self, detector):
        code = "import cohere\nco = cohere.Client()"
        report = detector.scan_text(code)
        assert any(f.provider == "cohere" for f in report.findings)

    @pytest.mark.unit
    def test_detect_huggingface(self, detector):
        code = "from transformers import AutoTokenizer"
        report = detector.scan_text(code)
        assert any(f.provider == "huggingface" for f in report.findings)

    @pytest.mark.unit
    def test_approved_provider_not_flagged(self, permissive_detector):
        code = "import openai\nclient = openai.OpenAI()"
        report = permissive_detector.scan_text(code)
        provider_findings = [f for f in report.findings if f.rule_id == "UNAPPROVED_PROVIDER"]
        assert len(provider_findings) == 0


# ── Environment variable detection ──────────────────────────────────────────

class TestEnvVarDetection:
    @pytest.mark.unit
    def test_detect_openai_key_env(self, detector):
        code = 'api_key = os.getenv("OPENAI_API_KEY")'
        report = detector.scan_text(code)
        assert any(f.rule_id == "SHADOW_ENV_VAR" for f in report.findings)

    @pytest.mark.unit
    def test_detect_hf_token(self, detector):
        code = 'token = os.environ["HF_TOKEN"]'
        report = detector.scan_text(code)
        assert any(f.rule_id == "SHADOW_ENV_VAR" and f.provider == "huggingface"
                    for f in report.findings)

    @pytest.mark.unit
    def test_detect_groq_key(self, detector):
        code = 'key = os.getenv("GROQ_API_KEY")'
        report = detector.scan_text(code)
        assert any(f.rule_id == "SHADOW_ENV_VAR" for f in report.findings)


# ── Clean code ───────────────────────────────────────────────────────────────

class TestCleanCode:
    @pytest.mark.unit
    def test_clean_python_code(self, detector):
        code = """
import json
import os

def process_data(items):
    return [x * 2 for x in items]
"""
        report = detector.scan_text(code)
        assert not report.has_shadow_ai

    @pytest.mark.unit
    def test_anthropic_only_code(self, detector):
        code = """
import anthropic
client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-opus-4-6",
    messages=[{"role": "user", "content": "Hello"}]
)
"""
        report = detector.scan_text(code)
        # Anthropic is approved, so no provider findings
        provider_findings = [f for f in report.findings if f.rule_id == "UNAPPROVED_PROVIDER"]
        assert len(provider_findings) == 0


# ── Report properties ────────────────────────────────────────────────────────

class TestReportProperties:
    @pytest.mark.unit
    def test_providers_found(self, detector):
        code = '''
import openai
from transformers import pipeline
model = "gemini-2.0-pro"
'''
        report = detector.scan_text(code)
        providers = report.providers_found
        assert "openai" in providers
        assert "huggingface" in providers

    @pytest.mark.unit
    def test_total_findings(self, detector):
        code = 'model = "gpt-4o"\nimport cohere'
        report = detector.scan_text(code)
        assert report.total_findings >= 2

    @pytest.mark.unit
    def test_files_scanned_for_text(self, detector):
        report = detector.scan_text("hello world")
        assert report.files_scanned == 1
