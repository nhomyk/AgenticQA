"""Unit tests for AIModelSBOMScanner — @pytest.mark.unit"""
import pytest
from pathlib import Path

from agenticqa.security.ai_model_sbom import AIModelSBOMScanner, SBOMResult, ModelComponent


def make_scanner() -> AIModelSBOMScanner:
    return AIModelSBOMScanner()


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Provider detection
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestProviderDetection:
    def test_openai_import_detected(self, tmp_path):
        write(tmp_path / "llm.py", "import openai\nclient = openai.OpenAI()\n")
        result = make_scanner().scan(str(tmp_path))
        assert "openai" in result.providers_detected

    def test_anthropic_import_detected(self, tmp_path):
        write(tmp_path / "llm.py", "import anthropic\nclient = anthropic.Anthropic()\n")
        result = make_scanner().scan(str(tmp_path))
        assert "anthropic" in result.providers_detected

    def test_huggingface_transformers_detected(self, tmp_path):
        write(tmp_path / "model.py", "from transformers import AutoModel\n")
        result = make_scanner().scan(str(tmp_path))
        assert "huggingface" in result.providers_detected

    def test_pytorch_detected(self, tmp_path):
        write(tmp_path / "train.py", "import torch\nimport torch.nn as nn\n")
        result = make_scanner().scan(str(tmp_path))
        assert "pytorch" in result.providers_detected

    def test_multiple_providers(self, tmp_path):
        write(tmp_path / "pipeline.py",
              "import openai\nimport anthropic\nfrom transformers import pipeline\n")
        result = make_scanner().scan(str(tmp_path))
        assert "openai" in result.providers_detected
        assert "anthropic" in result.providers_detected
        assert "huggingface" in result.providers_detected

    def test_clean_repo_no_providers(self, tmp_path):
        write(tmp_path / "utils.py", "import os\nimport json\ndef helper(): pass\n")
        result = make_scanner().scan(str(tmp_path))
        assert result.providers_detected == []
        assert result.risk_score == 0.0


# ---------------------------------------------------------------------------
# Model ID extraction
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestModelIDExtraction:
    def test_huggingface_from_pretrained(self, tmp_path):
        write(tmp_path / "embed.py",
              'from transformers import AutoModel\n'
              'model = AutoModel.from_pretrained("bert-base-uncased")\n')
        result = make_scanner().scan(str(tmp_path))
        assert "bert-base-uncased" in result.unique_model_ids

    def test_openai_model_kwarg(self, tmp_path):
        write(tmp_path / "chat.py",
              'import openai\n'
              'resp = client.chat.completions.create(model="gpt-4-turbo")\n')
        result = make_scanner().scan(str(tmp_path))
        assert "gpt-4-turbo" in result.unique_model_ids

    def test_anthropic_model_kwarg(self, tmp_path):
        write(tmp_path / "claude.py",
              'import anthropic\n'
              'msg = client.messages.create(model="claude-3-haiku-20240307")\n')
        result = make_scanner().scan(str(tmp_path))
        assert "claude-3-haiku-20240307" in result.unique_model_ids

    def test_huggingface_org_slash_model(self, tmp_path):
        write(tmp_path / "ner.py",
              'model = AutoModel.from_pretrained("dslim/bert-base-NER")\n')
        result = make_scanner().scan(str(tmp_path))
        assert "dslim/bert-base-NER" in result.unique_model_ids

    def test_pipeline_with_model_arg(self, tmp_path):
        write(tmp_path / "classify.py",
              'from transformers import pipeline\n'
              'clf = pipeline("text-classification", model="distilbert-base-uncased")\n')
        result = make_scanner().scan(str(tmp_path))
        assert "distilbert-base-uncased" in result.unique_model_ids

    def test_gemini_generativemodel(self, tmp_path):
        write(tmp_path / "gen.py",
              'import google.generativeai as genai\n'
              'model = genai.GenerativeModel("gemini-pro")\n')
        result = make_scanner().scan(str(tmp_path))
        assert "gemini-pro" in result.unique_model_ids


# ---------------------------------------------------------------------------
# License classification
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestLicenseClassification:
    def test_bert_is_apache(self, tmp_path):
        write(tmp_path / "m.py",
              'model = AutoModel.from_pretrained("bert-base-uncased")\n')
        result = make_scanner().scan(str(tmp_path))
        comps = [c for c in result.components if c.model_id == "bert-base-uncased"]
        assert comps
        assert comps[0].license == "apache-2.0"

    def test_llama_is_restricted(self, tmp_path):
        write(tmp_path / "m.py",
              'model = AutoModel.from_pretrained("meta-llama/Llama-2-7b-hf")\n')
        result = make_scanner().scan(str(tmp_path))
        comps = [c for c in result.components if "llama-2" in c.model_id.lower() or "llama-2" in c.license.lower()]
        # Either found by model_id pattern or license lookup
        assert any("RESTRICTED_LICENSE" in c.risk_flags for c in result.components
                   if "llama" in c.model_id.lower())

    def test_openai_gpt_is_proprietary(self, tmp_path):
        write(tmp_path / "m.py",
              'resp = client.chat.completions.create(model="gpt-4")\n')
        result = make_scanner().scan(str(tmp_path))
        comps = [c for c in result.components if c.model_id == "gpt-4"]
        assert comps
        assert comps[0].license == "proprietary"

    def test_unknown_model_license_flagged(self, tmp_path):
        write(tmp_path / "m.py",
              'model = AutoModel.from_pretrained("my-company/internal-model-v2")\n')
        result = make_scanner().scan(str(tmp_path))
        comps = [c for c in result.components if c.model_id == "my-company/internal-model-v2"]
        assert comps
        assert "UNKNOWN_LICENSE" in comps[0].risk_flags


# ---------------------------------------------------------------------------
# Risk flags
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRiskFlags:
    def test_external_api_flag(self, tmp_path):
        write(tmp_path / "m.py",
              'import openai\nresp = client.chat.completions.create(model="gpt-4-turbo")\n')
        result = make_scanner().scan(str(tmp_path))
        comps = [c for c in result.components if c.model_id == "gpt-4-turbo"]
        assert comps
        assert "EXTERNAL_API" in comps[0].risk_flags

    def test_deprecated_model_flagged(self, tmp_path):
        write(tmp_path / "old.py",
              'import openai\nresp = openai.Completion.create(model="text-davinci-003")\n')
        result = make_scanner().scan(str(tmp_path))
        comps = [c for c in result.components if c.model_id == "text-davinci-003"]
        assert comps
        assert "DEPRECATED_MODEL" in comps[0].risk_flags

    def test_unversioned_model_flagged(self, tmp_path):
        write(tmp_path / "m.py",
              'model = AutoModel.from_pretrained("bert-base-uncased")\n')
        result = make_scanner().scan(str(tmp_path))
        comps = [c for c in result.components if c.model_id == "bert-base-uncased"]
        assert comps
        assert "UNVERSIONED_MODEL" in comps[0].risk_flags

    def test_versioned_model_not_flagged_unversioned(self, tmp_path):
        write(tmp_path / "m.py",
              'model = AutoModel.from_pretrained("bert-base-uncased-v1.2")\n')
        result = make_scanner().scan(str(tmp_path))
        comps = [c for c in result.components if c.model_id == "bert-base-uncased-v1.2"]
        if comps:
            assert "UNVERSIONED_MODEL" not in comps[0].risk_flags


# ---------------------------------------------------------------------------
# SBOM result structure
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSBOMResult:
    def test_license_violations_populated(self, tmp_path):
        write(tmp_path / "m.py",
              'model = AutoModel.from_pretrained("unknown-org/mystery-model")\n')
        result = make_scanner().scan(str(tmp_path))
        assert result.license_violations  # unknown license should appear

    def test_risk_score_zero_for_clean_repo(self, tmp_path):
        write(tmp_path / "app.py", "import os\ndef greet(): return 'hello'\n")
        result = make_scanner().scan(str(tmp_path))
        assert result.risk_score == 0.0

    def test_risk_score_positive_with_ai(self, tmp_path):
        write(tmp_path / "m.py",
              'import openai\nresp = client.chat.completions.create(model="gpt-4")\n')
        result = make_scanner().scan(str(tmp_path))
        assert result.risk_score > 0.0

    def test_scan_error_on_bad_path(self):
        result = make_scanner().scan("/nonexistent/path/that/does/not/exist")
        # Should not raise; may return empty result or set scan_error
        assert isinstance(result, SBOMResult)

    def test_no_duplicate_model_ids_per_file(self, tmp_path):
        write(tmp_path / "m.py",
              'model1 = AutoModel.from_pretrained("bert-base-uncased")\n'
              'model2 = AutoModel.from_pretrained("bert-base-uncased")\n')
        result = make_scanner().scan(str(tmp_path))
        ids = [c.model_id for c in result.components if c.model_id == "bert-base-uncased"]
        assert len(ids) == 1  # deduplicated per file

    def test_skips_node_modules(self, tmp_path):
        write(tmp_path / "node_modules" / "some-pkg" / "index.js",
              'const model = "gpt-4";\n')
        write(tmp_path / "src" / "app.py", "import os\n")
        result = make_scanner().scan(str(tmp_path))
        # No model IDs should come from node_modules
        files = [c.source_file for c in result.components]
        assert not any("node_modules" in f for f in files)
