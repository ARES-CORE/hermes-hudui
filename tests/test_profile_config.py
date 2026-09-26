"""Profile config.yaml parsing: indented lists and inline comments."""

from backend.collectors.profiles import _read_config


def test_read_config_handles_indented_lists_and_comments(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "model:\n"
        "  provider: anthropic  # inline comment\n"
        "  default: some-model\n"
        "toolsets:\n"
        "  - terminal\n"
        "  - file\n",
        encoding="utf-8",
    )
    cfg = _read_config(tmp_path)
    assert cfg["model"]["provider"] == "anthropic"
    assert cfg["toolsets"] == ["terminal", "file"]


def test_read_config_missing_file(tmp_path):
    assert _read_config(tmp_path) == {}
