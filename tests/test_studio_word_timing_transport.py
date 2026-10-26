from pathlib import Path
from types import SimpleNamespace

import pytest

from app.controllers.run_controller import RunController
from app.modules.studio.render_service import StudioRenderService
from app.modules.subtitles.policies.timing import (
    SpeechSegment,
    SubtitleTiming,
    WordTiming,
)
from app.shared.profile_identity import OperationalProfileKey, ProfileComponent
from app.shared.subtitle_profile_identity import SubtitleProfileKey
from app.shared.subtitle_profile_resolver import SubtitleProfileResolver


def _timing():
    return SubtitleTiming(
        source="test",
        segments=(
            SpeechSegment(
                start=0.0,
                end=1.0,
                words=(
                    WordTiming("HOLA", 0.0, 0.4),
                    WordTiming("MUNDO", 0.5, 1.0),
                ),
            ),
        ),
        duration=1.0,
        reliability="test",
    )


def _profile():
    return SimpleNamespace(
        width=1080,
        height=1920,
        fps=30,
        pixel_format="yuv420p",
        audio_sample_rate=48_000,
        codec="libx264",
        preset="medium",
        crf=18,
        audio_codec="aac",
        audio_bitrate="192k",
        audio_channels=2,
        movflags="+faststart",
    )


def _subtitle_profile(effect, family="minimalista"):
    return SubtitleProfileResolver().load(
        SubtitleProfileKey(
            component=ProfileComponent.STUDIO,
            platform="vertical",
            family=family,
            profile_id=f"subtitulo_studio_vertical_{effect}",
        )
    )


def _render_ass(tmp_path, effect, family="minimalista"):
    source = tmp_path / "source.mp4"
    subtitles = tmp_path / "source.srt"
    output = tmp_path / "output.mp4"
    source.write_bytes(b"video")
    subtitles.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHOLA MUNDO\n",
        encoding="utf-8",
    )
    rendered_ass = []

    class Runner:
        def run(self, command):
            graph = command[command.index("-filter_complex") + 1]
            ass_path = graph.split("ass='")[1].split("':fontsdir", 1)[0]
            ass_path = Path(ass_path.replace(r"\:", ":").replace(r"\'", "'"))
            rendered_ass.append(ass_path.read_text(encoding="utf-8"))
            Path(command[-1]).write_bytes(b"rendered")

    class Validator:
        def validate(self, output_path, expected_duration, profile):
            assert Path(output_path).is_file()
            return expected_duration

    service = StudioRenderService(
        runner=Runner(),
        probe=SimpleNamespace(
            inspect=lambda path: SimpleNamespace(duration=1.0, has_audio=True),
        ),
        output_validator=Validator(),
    )
    service.FONTS_DIRECTORY = tmp_path
    service.render(
        video_path=source,
        subtitle_path=subtitles,
        profile_key=OperationalProfileKey(
            component=ProfileComponent.STUDIO,
            platform="vertical",
            profile_id="studio_vertical",
        ),
        profile=_profile(),
        subtitle_profile=_subtitle_profile(effect, family),
        subtitle_timing=_timing(),
        output_path=output,
    )
    return rendered_ass[0]


@pytest.mark.parametrize(
    ("effect", "marker"),
    (
        ("highlight_in_sentence", r"{\1c&H0000FFFF}"),
        ("active_pill", r"\p1"),
        ("pop_in_sentence", r"\fscx125"),
        ("alpha_fade", r"\1a&HFF&"),
    ),
)
def test_studio_transports_word_timing_to_in_sentence_ass_effects(
    tmp_path,
    effect,
    marker,
):
    ass = _render_ass(tmp_path, effect)

    assert marker in ass
    assert ass.count("Dialogue:") > 1


def test_studio_transports_word_timing_to_typewriter_character_progression(tmp_path):
    ass = _render_ass(tmp_path, "typewriter")

    dialogues = [
        line for line in ass.splitlines() if line.startswith("Dialogue:")
    ]

    assert len(dialogues) > 1
    assert dialogues[0].endswith("H_")
    assert any(line.endswith("HO_") for line in dialogues)
    assert any(line.endswith("HOL_") for line in dialogues)
    assert dialogues[-1].endswith("HOLA MUNDO_")


def test_studio_transports_timing_to_continuous_karaoke_syllabic_sweep(tmp_path):
    ass = _render_ass(tmp_path, "continuous_karaoke", family="karaoke")

    assert r"{\kf20}HO{\kf20}LA" in ass
    assert r"{\kf30}MUN{\kf20}DO" in ass


def test_minimalista_keeps_its_technical_family_and_uses_the_visible_label():
    assert RunController._family_label("minimalista") == "MODO MINIMALISTA"
    assert _subtitle_profile("typewriter").key.family == "minimalista"


def test_karaoke_keeps_its_technical_family_and_uses_the_visible_label():
    assert RunController._family_label("karaoke") == "FORMATO KARAOKE"
    assert _subtitle_profile("continuous_karaoke", family="karaoke").key.family == "karaoke"
