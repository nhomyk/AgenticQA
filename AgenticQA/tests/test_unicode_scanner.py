"""Unit tests for UnicodeThreatScanner."""
import pytest
from agenticqa.security.unicode_scanner import UnicodeThreatScanner


@pytest.fixture
def s():
    return UnicodeThreatScanner()


# ── Clean ASCII ───────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_clean_ascii_no_findings(s):
    assert s.scan("Hello world! This is a normal string.") == []
    assert s.is_safe("admin password test") is True


# ── Invisible chars ───────────────────────────────────────────────────────────

@pytest.mark.unit
def test_zero_width_space_detected(s):
    findings = s.scan("rm\u200b-rf /")  # ZWSP between rm and -rf
    assert any(f.attack_type == "INVISIBLE_CHARS" for f in findings)


@pytest.mark.unit
def test_zero_width_joiner_detected(s):
    findings = s.scan("hello\u200dworld")
    assert any(f.attack_type == "INVISIBLE_CHARS" for f in findings)


@pytest.mark.unit
def test_bom_detected(s):
    findings = s.scan("\ufefffoo bar")
    assert any(f.attack_type == "INVISIBLE_CHARS" for f in findings)


# ── Directional override ──────────────────────────────────────────────────────

@pytest.mark.unit
def test_rtl_override_critical(s):
    findings = s.scan("file\u202egnp.exe")  # U+202E RTL Override
    assert any(f.attack_type == "DIRECTIONAL_OVERRIDE" and f.severity == "critical" for f in findings)


@pytest.mark.unit
def test_ltr_embedding_high(s):
    findings = s.scan("test\u202afile")  # U+202A LTR Embedding
    assert any(f.attack_type == "DIRECTIONAL_OVERRIDE" for f in findings)


# ── Steganographic tags ───────────────────────────────────────────────────────

@pytest.mark.unit
def test_tag_chars_critical(s):
    tag_text = "hello" + "\U000E0068\U000E0065\U000E006C\U000E006C\U000E006F"  # tag 'hello'
    findings = s.scan(tag_text)
    assert any(f.attack_type == "STEGANOGRAPHIC_TAGS" and f.severity == "critical" for f in findings)


# ── Confusable homoglyphs ─────────────────────────────────────────────────────

@pytest.mark.unit
def test_cyrillic_a_detected(s):
    # U+0430 CYRILLIC SMALL LETTER A looks like Latin 'a'
    findings = s.scan("\u0430dmin")  # "аdmin" with Cyrillic а
    assert any(f.attack_type == "CONFUSABLE_HOMOGLYPH" for f in findings)


@pytest.mark.unit
def test_cyrillic_o_detected(s):
    findings = s.scan("hell\u043e")  # Cyrillic o
    assert any(f.attack_type == "CONFUSABLE_HOMOGLYPH" for f in findings)


@pytest.mark.unit
def test_pure_latin_no_homoglyph(s):
    findings = s.scan("admin hello world")
    assert not any(f.attack_type == "CONFUSABLE_HOMOGLYPH" for f in findings)


# ── strip_invisible ───────────────────────────────────────────────────────────

@pytest.mark.unit
def test_strip_invisible_removes_zwsp(s):
    result = s.strip_invisible("rm\u200b-rf /")
    assert "\u200b" not in result
    assert "rm-rf /" == result


@pytest.mark.unit
def test_strip_invisible_removes_rtl(s):
    result = s.strip_invisible("file\u202egnp.exe")
    assert "\u202e" not in result


@pytest.mark.unit
def test_strip_invisible_leaves_normal_text(s):
    text = "hello world"
    assert s.strip_invisible(text) == text


# ── normalize ─────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_normalize_nfkc(s):
    # Fullwidth 'A' (U+FF21) normalizes to ASCII 'A'
    assert s.normalize("\uff21") == "A"


# ── is_safe / risk_score ──────────────────────────────────────────────────────

@pytest.mark.unit
def test_is_safe_false_on_rtl_override(s):
    assert s.is_safe("file\u202egnp.exe") is False


@pytest.mark.unit
def test_is_safe_false_on_tag_chars(s):
    tag_text = "\U000E0068\U000E0065"
    assert s.is_safe(tag_text) is False


@pytest.mark.unit
def test_risk_score_zero_clean(s):
    assert s.risk_score("normal text") == 0.0


@pytest.mark.unit
def test_offset_reported(s):
    findings = s.scan("ab\u200bcd")
    invisible = [f for f in findings if f.attack_type == "INVISIBLE_CHARS"]
    assert invisible[0].offset == 2
