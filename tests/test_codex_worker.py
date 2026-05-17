import json

from app.codex_worker import normalize_codex_log


def test_normalize_codex_log_suppresses_known_plugin_warnings() -> None:
    line = (
        "2026-05-17T05:08:19Z WARN codex_core_plugins::manifest: "
        "ignoring interface.defaultPrompt: maximum of 3 prompts is supported"
    )

    assert normalize_codex_log("stderr", line) is None


def test_normalize_codex_log_summarizes_file_changes() -> None:
    line = json.dumps(
        {
            "type": "item.completed",
            "item": {
                "type": "file_change",
                "status": "completed",
                "changes": [{"path": "/tmp/repo/README.md", "kind": "update"}],
            },
        }
    )

    clean = normalize_codex_log("stdout", line)

    assert clean == {
        "stream": "codex",
        "message": "Edited README.md.",
        "level": "info",
        "source_type": "item.completed",
    }


def test_normalize_codex_log_compacts_agent_messages() -> None:
    line = json.dumps(
        {
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "status": "completed",
                "text": "Updated README.md with one short usage sentence.\n\nValidation passed.",
            },
        }
    )

    clean = normalize_codex_log("stdout", line)

    assert clean
    assert clean["message"] == "Updated README.md with one short usage sentence. Validation passed."
