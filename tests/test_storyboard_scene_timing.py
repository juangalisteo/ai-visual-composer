"""The storyboard cuts its scenes at sentence ends, on the voice's times."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.modules.storyboard.storyboard_builder import StoryboardBuilder
from app.shared.format_catalog import FormatCatalog


SCRIPT = (
    "Primera frase de prueba con varias palabras. "
    "Segunda frase. "
    "Tercera frase de prueba, bastante más larga que la segunda."
)


def _visual_scene(number):
    return {
        "scene": number,
        "visible_subject": f"sujeto {number}",
        "visible_action": f"accion {number}",
        "visible_environment": f"entorno {number}",
        "time_context": "dia",
        "key_objects": [f"objeto {number}"],
        "spatial_relationships": ["relacion espacial"],
        "continuity_links": ["continuidad"],
        "abstract_source": "idea",
        "filmable_interpretation": f"escena filmable {number}",
        "visual_constraints": ["sin texto legible"],
        "visual_truth_status": "structured",
    }


class _FakeStoryboardAI:
    prompts = []

    def __init__(self, ai_config):
        del ai_config

    def build(self, prompt):
        _FakeStoryboardAI.prompts.append(prompt)
        count = prompt.count("ESCENA ")
        return json.dumps([
            _visual_scene(number)
            for number in range(1, count + 1)
        ])


def _whisper_words(*sentences):
    """Whisper words of ``(text, start, end)`` sentences, each word taking an
    equal share of its sentence."""
    words = []
    for text, start, end in sentences:
        texts = text.split()
        share = (end - start) / len(texts)
        words.extend(
            {
                "word": f" {word}",
                "start": start + share * index,
                "end": start + share * (index + 1),
                "probability": 0.9,
            }
            for index, word in enumerate(texts)
        )
    return words


def _build(tmp_path, audio_duration, **build_options):
    catalog_path = tmp_path / "formats.json"
    catalog_path.write_text(
        json.dumps({
            "formats": {
                "vertical": {
                    "display_name": "Formato técnico",
                    "order": 1,
                    "scene_seconds": {
                        "min": 5,
                        "target_min": 6,
                        "target_max": 8,
                        "max": 9,
                    },
                },
            },
        }),
        encoding="utf-8",
    )
    script_path = tmp_path / "guion.txt"
    script_path.write_text(SCRIPT, encoding="utf-8")
    audio_path = tmp_path / "voz.mp3"
    audio_path.write_bytes(b"audio")
    output_path = tmp_path / "storyboard.json"
    project = SimpleNamespace(
        final_audio_path=lambda: tmp_path / "audio_final.mp3",
        audio_path=lambda: audio_path,
        script_path=lambda: script_path,
        storyboard_path=lambda: output_path,
    )
    config = SimpleNamespace(
        get_ai_config=lambda: {"model": "fake-storyboard-model"},
        get_profile_config=lambda: {
            "tone": "modo_conciencia",
            "format": "vertical",
        },
    )
    _FakeStoryboardAI.prompts = []

    with patch(
        "app.modules.storyboard.storyboard_builder.MediaProbe.get_duration",
        return_value=audio_duration,
    ), patch(
        "app.modules.storyboard.storyboard_builder.StoryboardAIBuilder",
        _FakeStoryboardAI,
    ), patch(
        "app.modules.storyboard.storyboard_builder.ProgressLogger.detail",
    ) as info:
        StoryboardBuilder(
            config_manager=config,
            project=project,
            format_catalog=FormatCatalog(catalog_path),
        ).build(**build_options)

    scenes = json.loads(output_path.read_text(encoding="utf-8"))
    messages = [call.args[0] for call in info.call_args_list]
    return scenes, messages


def test_scenes_take_whisper_times_and_whole_sentences(tmp_path):
    subtitle_path = tmp_path / "subtitulos.srt"
    subtitle_path.write_text(
        "1\n00:00:00,000 --> 00:00:14,000\ntexto\n",
        encoding="utf-8",
    )
    (tmp_path / "subtitulos_whisper.json").write_text(
        json.dumps({
            "segments": [{
                "start": 0.2,
                "end": 13.6,
                "words": _whisper_words(
                    ("Primera frase de prueba con varias palabras.", 0.2, 4.0),
                    ("Segunda frase.", 4.6, 6.0),
                    (
                        "Tercera frase de prueba, bastante más larga que la "
                        "segunda.",
                        6.6,
                        13.6,
                    ),
                ),
            }],
        }),
        encoding="utf-8",
    )

    scenes, messages = _build(
        tmp_path,
        14.0,
        subtitle_path=subtitle_path,
    )

    assert [scene["text"] for scene in scenes] == [
        "Primera frase de prueba con varias palabras. Segunda frase.",
        "Tercera frase de prueba, bastante más larga que la segunda.",
    ]
    assert [scene["duration"] for scene in scenes] == [6.3, 7.7]
    assert "Tiempos de las escenas: Whisper" in messages
    assert (
        "ESCENA 1:\nPrimera frase de prueba con varias palabras. "
        "Segunda frase.\n\nESCENA 2:\nTercera frase"
    ) in _FakeStoryboardAI.prompts[0]


def test_without_whisper_sentences_end_in_the_pauses_of_the_voice(tmp_path):
    scenes, messages = _build(
        tmp_path,
        14.0,
        voice_pauses=((3.0, 3.5), (6.0, 6.5)),
    )

    assert [scene["text"] for scene in scenes] == [
        "Primera frase de prueba con varias palabras. Segunda frase.",
        "Tercera frase de prueba, bastante más larga que la segunda.",
    ]
    assert [scene["duration"] for scene in scenes] == [6.25, 7.75]
    assert (
        "Tiempos de las escenas: estimados por letras y pausas de la voz "
        "(sin Whisper)"
    ) in messages


def test_unusable_whisper_times_fall_back_to_the_estimate(tmp_path):
    subtitle_path = tmp_path / "subtitulos.srt"
    subtitle_path.write_text("1\n00:00:00,000 --> 00:00:14,000\nx\n", encoding="utf-8")

    scenes, messages = _build(
        tmp_path,
        14.0,
        subtitle_path=subtitle_path,
        voice_pauses=((3.0, 3.5), (6.0, 6.5)),
    )

    assert [scene["duration"] for scene in scenes] == [6.25, 7.75]
    assert any("sin Whisper" in message for message in messages)


def test_storyboard_needs_the_scene_seconds_of_its_format(tmp_path):
    catalog_path = tmp_path / "formats.json"
    catalog_path.write_text(json.dumps({"formats": {}}), encoding="utf-8")

    with pytest.raises(Exception, match="scene_seconds"):
        StoryboardBuilder(
            format_catalog=FormatCatalog(catalog_path),
        )._scene_seconds({"format": "test_format"})

    assert Path(catalog_path).exists()
