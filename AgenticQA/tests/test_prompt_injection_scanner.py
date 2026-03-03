"""Unit tests for PromptInjectionScanner — @pytest.mark.unit"""
import pytest
from pathlib import Path

from agenticqa.security.prompt_injection_scanner import (
    InjectionFinding,
    InjectionScanResult,
    PromptInjectionScanner,
)


def make_scanner() -> PromptInjectionScanner:
    return PromptInjectionScanner()


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Direct concatenation
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDirectConcatenation:
    def test_fstring_user_input_flagged(self, tmp_path):
        write(tmp_path / "api" / "chat.py",
              'system = f"You are a helpful assistant. User says: {user_input}"\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PROMPT_INJECTION_SURFACE"]
        assert len(hits) >= 1
        assert hits[0].severity == "critical"

    def test_template_literal_user_message(self, tmp_path):
        write(tmp_path / "route.ts",
              'const system = `You are helpful. Context: ${userMessage}`;\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PROMPT_INJECTION_SURFACE"]
        assert len(hits) >= 1

    def test_hardcoded_prompt_no_finding(self, tmp_path):
        write(tmp_path / "agent.py",
              'system = "You are a helpful assistant. Answer concisely."\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PROMPT_INJECTION_SURFACE"]
        assert len(hits) == 0

    def test_env_var_prompt_no_finding(self, tmp_path):
        write(tmp_path / "app.ts",
              'const system = process.env.SYSTEM_PROMPT;\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PROMPT_INJECTION_SURFACE"]
        assert len(hits) == 0


# ---------------------------------------------------------------------------
# Template injection
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestTemplateInjection:
    def test_format_call_on_prompt_flagged(self, tmp_path):
        write(tmp_path / "llm.py",
              'prompt = TEMPLATE.format(query=user_query)\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "TEMPLATE_INJECTION"]
        assert len(hits) >= 1
        assert hits[0].severity == "high"

    def test_hardcoded_format_no_finding(self, tmp_path):
        write(tmp_path / "util.py",
              'msg = "Hello {}".format("world")\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "TEMPLATE_INJECTION"]
        assert len(hits) == 0


# ---------------------------------------------------------------------------
# Unvalidated LLM output
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestUnvalidatedOutput:
    def test_eval_llm_output_flagged(self, tmp_path):
        write(tmp_path / "executor.py",
              'result = eval(llm_output)\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "UNVALIDATED_LLM_OUTPUT"]
        assert len(hits) >= 1
        assert hits[0].severity == "medium"

    def test_subprocess_with_response_flagged(self, tmp_path):
        write(tmp_path / "runner.py",
              'subprocess.run(response, shell=True)\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "UNVALIDATED_LLM_OUTPUT"]
        assert len(hits) >= 1

    def test_safe_eval_call_no_finding(self, tmp_path):
        write(tmp_path / "math_util.py",
              'result = eval("2 + 2")\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "UNVALIDATED_LLM_OUTPUT"]
        assert len(hits) == 0


# ---------------------------------------------------------------------------
# System prompt override
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSystemPromptOverride:
    def test_user_controls_role_flagged(self, tmp_path):
        write(tmp_path / "api.ts",
              '{ role: "system", content: userInput }\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "SYSTEM_PROMPT_OVERRIDE"]
        assert len(hits) >= 1
        assert hits[0].severity == "high"

    def test_fixed_role_no_finding(self, tmp_path):
        write(tmp_path / "llm.ts",
              '{ role: "user", content: message }\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "SYSTEM_PROMPT_OVERRIDE"]
        assert len(hits) == 0


# ---------------------------------------------------------------------------
# Surface score + clean repo
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSurfaceScore:
    def test_clean_repo_zero_score(self, tmp_path):
        result = make_scanner().scan(str(tmp_path))
        assert result.surface_score == 0.0
        assert len(result.findings) == 0

    def test_all_critical_score_is_one(self):
        scanner = make_scanner()
        findings = [
            InjectionFinding("a.ts", 1, "PROMPT_INJECTION_SURFACE", "critical", "msg"),
            InjectionFinding("b.ts", 2, "PROMPT_INJECTION_SURFACE", "critical", "msg"),
            InjectionFinding("c.ts", 3, "PROMPT_INJECTION_SURFACE", "critical", "msg"),
        ]
        result = scanner._build_result(findings)
        assert result.surface_score == 1.0

    def test_mixed_severities_score_between(self):
        scanner = make_scanner()
        findings = [
            InjectionFinding("a.ts", 1, "PROMPT_INJECTION_SURFACE", "critical", "msg"),  # 1.0
            InjectionFinding("b.ts", 2, "UNVALIDATED_LLM_OUTPUT", "medium", "msg"),       # 0.4
        ]
        result = scanner._build_result(findings)
        # mean([1.0, 0.4]) = 0.7
        assert abs(result.surface_score - 0.7) < 0.01

    def test_clean_file_no_findings(self, tmp_path):
        write(tmp_path / "utils.py", "def add(a, b):\n    return a + b\n")
        result = make_scanner().scan(str(tmp_path))
        assert result.surface_score == 0.0
        assert result.scan_error is None


# ---------------------------------------------------------------------------
# Go language patterns
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGoDirectConcatenation:
    def test_go_sprintf_into_prompt(self, tmp_path):
        write(tmp_path / "llm.go",
              'prompt := fmt.Sprintf("You are a bot. User said: %s", userInput)\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PROMPT_INJECTION_SURFACE"]
        assert len(hits) >= 1
        assert hits[0].severity == "critical"

    def test_go_string_concat_into_prompt(self, tmp_path):
        write(tmp_path / "handler.go",
              'prompt += "Context: " + userMessage\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PROMPT_INJECTION_SURFACE"]
        assert len(hits) >= 1

    def test_go_strings_join_into_prompt(self, tmp_path):
        write(tmp_path / "agent.go",
              'system := strings.Join(parts, "\\n")\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PROMPT_INJECTION_SURFACE"]
        assert len(hits) >= 1

    def test_go_hardcoded_prompt_no_finding(self, tmp_path):
        write(tmp_path / "bot.go",
              'prompt := "You are a helpful assistant"\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PROMPT_INJECTION_SURFACE"]
        assert len(hits) == 0


@pytest.mark.unit
class TestGoTemplateInjection:
    def test_go_template_execute_with_user_data(self, tmp_path):
        write(tmp_path / "render.go",
              'err := tmpl.Execute(buf, userInput)\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "TEMPLATE_INJECTION"]
        assert len(hits) >= 1

    def test_go_strings_replace_on_prompt(self, tmp_path):
        write(tmp_path / "prompt.go",
              'result := strings.ReplaceAll(prompt, "{{USER}}", userMsg)\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "TEMPLATE_INJECTION"]
        assert len(hits) >= 1

    def test_go_sprintf_with_user_var(self, tmp_path):
        write(tmp_path / "chat.go",
              'msg := fmt.Sprintf("System: %s\\nUser: %s", sysPrompt, userInput)\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "TEMPLATE_INJECTION"]
        assert len(hits) >= 1


@pytest.mark.unit
class TestGoUnsafeOutput:
    def test_go_exec_command_with_response(self, tmp_path):
        write(tmp_path / "runner.go",
              'cmd := exec.Command("bash", "-c", response)\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "UNVALIDATED_LLM_OUTPUT"]
        assert len(hits) >= 1

    def test_go_db_exec_with_completion(self, tmp_path):
        write(tmp_path / "store.go",
              'db.Exec(completion)\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "UNVALIDATED_LLM_OUTPUT"]
        assert len(hits) >= 1

    def test_go_safe_exec_no_finding(self, tmp_path):
        write(tmp_path / "safe.go",
              'cmd := exec.Command("ls", "-la")\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "UNVALIDATED_LLM_OUTPUT"]
        assert len(hits) == 0


@pytest.mark.unit
class TestGoChatAPIInjection:
    def test_go_openai_message_with_user_input(self, tmp_path):
        write(tmp_path / "openai.go",
              'msg := openai.ChatCompletionMessage{Role: "system", Content: userInput}\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "CHAT_API_INJECTION"]
        assert len(hits) >= 1

    def test_go_append_messages_with_body(self, tmp_path):
        write(tmp_path / "chat.go",
              'messages = append(messages, Message{Role: "user", Content: body})\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "CHAT_API_INJECTION"]
        assert len(hits) >= 1

    def test_go_hardcoded_message_no_finding(self, tmp_path):
        write(tmp_path / "fixed.go",
              'msg := Message{Role: "system", Content: "You are helpful"}\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "CHAT_API_INJECTION"]
        assert len(hits) == 0


@pytest.mark.unit
class TestGoRAGInjection:
    def test_go_sprintf_with_context(self, tmp_path):
        write(tmp_path / "rag.go",
              'prompt := fmt.Sprintf("Context: %s\\nQuestion: %s", context, question)\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "RAG_CONTEXT_INJECTION"]
        assert len(hits) >= 1

    def test_go_prompt_concat_with_chunks(self, tmp_path):
        write(tmp_path / "search.go",
              'prompt += "\\nRelevant documents: " + chunks\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "RAG_CONTEXT_INJECTION"]
        assert len(hits) >= 1


@pytest.mark.unit
class TestGoRoleOverride:
    def test_go_role_from_variable(self, tmp_path):
        write(tmp_path / "msg.go",
              'msg := Message{Role: userRole, Content: text}\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "SYSTEM_PROMPT_OVERRIDE"]
        assert len(hits) >= 1

    def test_go_fixed_role_no_finding(self, tmp_path):
        write(tmp_path / "safe.go",
              'msg := Message{Role: "assistant", Content: text}\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "SYSTEM_PROMPT_OVERRIDE"]
        assert len(hits) == 0


@pytest.mark.unit
class TestGoFileExtension:
    def test_go_files_are_scanned(self, tmp_path):
        write(tmp_path / "main.go",
              'system := fmt.Sprintf("You are helpful. User: %s", userInput)\n')
        result = make_scanner().scan(str(tmp_path))
        assert result.total_findings >= 1

    def test_clean_go_file_no_findings(self, tmp_path):
        write(tmp_path / "main.go",
              'package main\n\nfunc main() {\n\tfmt.Println("hello")\n}\n')
        result = make_scanner().scan(str(tmp_path))
        assert result.total_findings == 0


# ---------------------------------------------------------------------------
# Ruby language patterns
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRubyDirectConcatenation:
    def test_ruby_interpolation_into_prompt(self, tmp_path):
        write(tmp_path / "chat.rb",
              'prompt = "You are a helper. User says: #{user_input}"\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PROMPT_INJECTION_SURFACE"]
        assert len(hits) >= 1
        assert hits[0].severity == "critical"

    def test_ruby_shovel_concat_into_prompt(self, tmp_path):
        write(tmp_path / "handler.rb",
              'prompt << "Context: " + params[:message]\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PROMPT_INJECTION_SURFACE"]
        assert len(hits) >= 1

    def test_ruby_plus_equals_into_prompt(self, tmp_path):
        write(tmp_path / "agent.rb",
              'instruction += user_input\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PROMPT_INJECTION_SURFACE"]
        assert len(hits) >= 1

    def test_ruby_hardcoded_prompt_no_finding(self, tmp_path):
        write(tmp_path / "bot.rb",
              'prompt = "You are a helpful assistant"\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "PROMPT_INJECTION_SURFACE"]
        assert len(hits) == 0


@pytest.mark.unit
class TestRubyTemplateInjection:
    def test_ruby_erb_with_user_data(self, tmp_path):
        write(tmp_path / "view.rb",
              'template = ERB.new(prompt_template).render(user_input)\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "TEMPLATE_INJECTION"]
        assert len(hits) >= 1

    def test_ruby_gsub_on_prompt(self, tmp_path):
        write(tmp_path / "prompt.rb",
              'result = prompt.gsub("{{USER}}", user_input)\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "TEMPLATE_INJECTION"]
        assert len(hits) >= 1


@pytest.mark.unit
class TestRubyUnsafeOutput:
    def test_ruby_system_with_response(self, tmp_path):
        write(tmp_path / "executor.rb",
              'system(response)\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "UNVALIDATED_LLM_OUTPUT"]
        assert len(hits) >= 1

    def test_ruby_exec_with_completion(self, tmp_path):
        write(tmp_path / "runner.rb",
              'exec(completion)\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "UNVALIDATED_LLM_OUTPUT"]
        assert len(hits) >= 1

    def test_ruby_find_by_sql_with_llm_output(self, tmp_path):
        write(tmp_path / "model.rb",
              'User.find_by_sql(llm_output)\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "UNVALIDATED_LLM_OUTPUT"]
        assert len(hits) >= 1

    def test_ruby_safe_system_no_finding(self, tmp_path):
        write(tmp_path / "safe.rb",
              'system("ls -la")\n')
        result = make_scanner().scan(str(tmp_path))
        hits = [f for f in result.findings if f.rule_id == "UNVALIDATED_LLM_OUTPUT"]
        assert len(hits) == 0


@pytest.mark.unit
class TestRubyFileExtension:
    def test_rb_files_are_scanned(self, tmp_path):
        write(tmp_path / "app.rb",
              'prompt = "You are a bot. User says: #{user_input}"\n')
        result = make_scanner().scan(str(tmp_path))
        assert result.total_findings >= 1

    def test_clean_rb_file_no_findings(self, tmp_path):
        write(tmp_path / "clean.rb",
              'class Greeter\n  def hello\n    puts "hello"\n  end\nend\n')
        result = make_scanner().scan(str(tmp_path))
        assert result.total_findings == 0
