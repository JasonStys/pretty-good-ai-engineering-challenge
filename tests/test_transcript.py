"""Realtime history-to-transcript conversion tests."""

from __future__ import annotations

from types import SimpleNamespace

from pgai_voicebot.transcript import history_to_turns


def test_history_maps_realtime_roles_to_conversation_sides() -> None:
    history = [
        SimpleNamespace(role="system", content=[]),
        SimpleNamespace(
            role="user", content=[SimpleNamespace(transcript="How can I help?", text=None)]
        ),
        SimpleNamespace(
            role="assistant", content=[SimpleNamespace(transcript=None, text="I need a visit.")]
        ),
        SimpleNamespace(type="function_call"),
    ]
    turns = history_to_turns(history)
    assert [turn.role for turn in turns] == ["pgai_agent", "patient_bot"]
    assert [turn.sequence for turn in turns] == [1, 2]
    assert turns[0].text == "How can I help?"


def test_history_omits_empty_content() -> None:
    history = [
        SimpleNamespace(role="assistant", content=[SimpleNamespace(transcript="", text=None)])
    ]
    assert history_to_turns(history) == []
